from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from llama_index.core.schema import NodeWithScore, TextNode

from agents.state import AgentResult, ReviewState
from agents.test_agent import (
    _SYSTEM_PROMPT,
    _build_input,
    _call_openai,
    _parse_response,
)
from agents.test_agent import (
    test_agent as run_test_agent,
)
from config.settings import settings
from gh.pr_fetcher import PRData
from retrieval.context_builder import PRContext

_PATCH = "agents.test_agent.{}"
_NOW = datetime(2024, 6, 1, tzinfo=UTC)

_VALID_JSON = json.dumps(
    {
        "summary": "New retry logic has no tests covering the exhausted-retries path.",
        "verdict": "REQUEST_CHANGES",
        "issues": ["No test for the case where all retries are exhausted"],
        "suggestions": ["Add a test asserting the exception raised after max_retries"],
    }
)


def _make_pr(
    number: int = 7,
    title: str = "Add retry logic",
    body: str = "Adds retry-with-backoff for transient errors.",
    diff: str = "diff --git a/client.py b/client.py\n+def _retry():\n+    pass",
) -> PRData:
    return PRData(
        number=number,
        title=title,
        body=body,
        state="open",
        author="dev",
        base_branch="main",
        head_branch="feature/retry",
        created_at=_NOW,
        updated_at=_NOW,
        changed_files=[],
        diff=diff,
    )


def _make_node(text: str) -> NodeWithScore:
    return NodeWithScore(node=TextNode(text=text), score=0.9)


def _make_context(
    issues: list[str] | None = None,
    prs: list[str] | None = None,
    commits: list[str] | None = None,
) -> PRContext:
    return PRContext(
        similar_issues=[_make_node(t) for t in (issues or [])],
        similar_prs=[_make_node(t) for t in (prs or [])],
        related_commits=[_make_node(t) for t in (commits or [])],
    )


def _make_state(pr: PRData, context: PRContext) -> ReviewState:
    return {
        "pr": pr,
        "context": context,
        "security_result": None,
        "quality_result": None,
        "test_result": None,
        "final_verdict": None,
    }


# ── _build_input ─────────────────────────────────────────────────────────────


def test_build_input_contains_title() -> None:
    pr = _make_pr(title="Unique PR title XYZ")
    ctx = _make_context()
    assert "Unique PR title XYZ" in _build_input(pr, ctx)


def test_build_input_contains_diff() -> None:
    pr = _make_pr(diff="unique-diff-marker-abc123")
    ctx = _make_context()
    assert "unique-diff-marker-abc123" in _build_input(pr, ctx)


def test_build_input_contains_issue_node_text() -> None:
    pr = _make_pr()
    ctx = _make_context(issues=["Issue #1: Missing test for null input"])
    assert "Missing test for null input" in _build_input(pr, ctx)


def test_build_input_contains_pr_node_text() -> None:
    pr = _make_pr()
    ctx = _make_context(prs=["Merged PR #5: Add integration tests"])
    assert "Add integration tests" in _build_input(pr, ctx)


def test_build_input_contains_commit_node_text() -> None:
    pr = _make_pr()
    ctx = _make_context(commits=["Commit abc123: Cover edge case in parser"])
    assert "Cover edge case in parser" in _build_input(pr, ctx)


def test_build_input_empty_context_renders_none() -> None:
    pr = _make_pr()
    ctx = _make_context()
    result = _build_input(pr, ctx)
    assert result.count("(none)") == 3


# ── _call_openai ─────────────────────────────────────────────────────────────


def test_call_openai_uses_configured_max_retries() -> None:
    mock_client = MagicMock()
    mock_client.responses.create.return_value = MagicMock(output_text="ok")

    with patch(_PATCH.format("OpenAI"), return_value=mock_client) as mock_openai_cls:
        _call_openai("some prompt")

    mock_openai_cls.assert_called_once_with(
        api_key=settings.openai_api_key, max_retries=settings.openai_max_retries
    )


def test_call_openai_passes_test_adequacy_system_prompt() -> None:
    mock_client = MagicMock()
    mock_client.responses.create.return_value = MagicMock(output_text="ok")

    with patch(_PATCH.format("OpenAI"), return_value=mock_client):
        _call_openai("some prompt")

    kwargs = mock_client.responses.create.call_args.kwargs
    assert kwargs["instructions"] == _SYSTEM_PROMPT
    assert kwargs["input"] == "some prompt"


def test_system_prompt_is_scoped_to_test_adequacy() -> None:
    lowered = _SYSTEM_PROMPT.lower()
    assert "test" in lowered
    assert "coverage" in lowered
    assert "edge case" in lowered


def test_system_prompt_requires_self_check_before_specific_claims() -> None:
    lowered = _SYSTEM_PROMPT.lower()
    assert "re-read the exact diff line" in lowered


# ── _parse_response ──────────────────────────────────────────────────────────


def test_parse_response_maps_all_fields() -> None:
    raw = json.dumps(
        {
            "summary": "No tests for the new error path.",
            "verdict": "REQUEST_CHANGES",
            "issues": ["No test for empty-list input"],
            "suggestions": ["Add a test for the empty-list edge case"],
        }
    )
    result = _parse_response(raw)

    assert isinstance(result, AgentResult)
    assert result.summary == "No tests for the new error path."
    assert result.verdict == "REQUEST_CHANGES"
    assert result.issues == ["No test for empty-list input"]
    assert result.suggestions == ["Add a test for the empty-list edge case"]


def test_parse_response_strips_json_code_fence() -> None:
    raw = "```json\n" + _VALID_JSON + "\n```"
    result = _parse_response(raw)
    assert result.verdict == "REQUEST_CHANGES"


def test_parse_response_strips_plain_code_fence() -> None:
    raw = "```\n" + _VALID_JSON + "\n```"
    result = _parse_response(raw)
    assert result.verdict == "REQUEST_CHANGES"


def test_parse_response_issues_defaults_to_empty_list() -> None:
    raw = json.dumps({"summary": "Well covered.", "verdict": "APPROVE"})
    result = _parse_response(raw)
    assert result.issues == []


def test_parse_response_suggestions_defaults_to_empty_list() -> None:
    raw = json.dumps({"summary": "Well covered.", "verdict": "APPROVE"})
    result = _parse_response(raw)
    assert result.suggestions == []


# ── test_agent (node) ────────────────────────────────────────────────────────


def test_test_agent_returns_test_result_key_only() -> None:
    pr = _make_pr()
    state = _make_state(pr, _make_context())
    mock_client = MagicMock()
    mock_client.responses.create.return_value = MagicMock(output_text=_VALID_JSON)

    with patch(_PATCH.format("OpenAI"), return_value=mock_client):
        update = run_test_agent(state)

    assert set(update.keys()) == {"test_result"}


def test_test_agent_parses_openai_output_into_agent_result() -> None:
    pr = _make_pr()
    state = _make_state(pr, _make_context())
    mock_client = MagicMock()
    mock_client.responses.create.return_value = MagicMock(output_text=_VALID_JSON)

    with patch(_PATCH.format("OpenAI"), return_value=mock_client):
        update = run_test_agent(state)

    result = update["test_result"]
    assert isinstance(result, AgentResult)
    assert result.verdict == "REQUEST_CHANGES"
    assert result.issues == ["No test for the case where all retries are exhausted"]
    assert result.suggestions == ["Add a test asserting the exception raised after max_retries"]


def test_test_agent_sends_pr_diff_to_openai() -> None:
    pr = _make_pr(diff="unique-test-diff-marker")
    state = _make_state(pr, _make_context())
    mock_client = MagicMock()
    mock_client.responses.create.return_value = MagicMock(output_text=_VALID_JSON)

    with patch(_PATCH.format("OpenAI"), return_value=mock_client):
        run_test_agent(state)

    prompt = mock_client.responses.create.call_args.kwargs["input"]
    assert "unique-test-diff-marker" in prompt
