from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from llama_index.core.schema import NodeWithScore, TextNode

from agents.security_agent import (
    _SYSTEM_PROMPT,
    _build_input,
    _call_openai,
    _parse_response,
    security_agent,
)
from agents.state import AgentResult, ReviewState
from config.settings import settings
from gh.pr_fetcher import PRData
from retrieval.context_builder import PRContext

_PATCH = "agents.security_agent.{}"
_NOW = datetime(2024, 6, 1, tzinfo=UTC)

_VALID_JSON = json.dumps(
    {
        "summary": "Found a hardcoded API key.",
        "verdict": "REQUEST_CHANGES",
        "issues": ["Hardcoded API key in config.py line 12"],
        "suggestions": ["Move the key to an environment variable"],
    }
)


def _make_pr(
    number: int = 7,
    title: str = "Add payment integration",
    body: str = "Integrates the Stripe API.",
    diff: str = "diff --git a/payments.py b/payments.py\n+API_KEY = 'sk_live_abc123'",
) -> PRData:
    return PRData(
        number=number,
        title=title,
        body=body,
        state="open",
        author="dev",
        base_branch="main",
        head_branch="feature/payments",
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
    ctx = _make_context(issues=["Issue #1: Hardcoded secret in prior PR"])
    assert "Hardcoded secret in prior PR" in _build_input(pr, ctx)


def test_build_input_contains_pr_node_text() -> None:
    pr = _make_pr()
    ctx = _make_context(prs=["Merged PR #5: Add auth middleware"])
    assert "Add auth middleware" in _build_input(pr, ctx)


def test_build_input_contains_commit_node_text() -> None:
    pr = _make_pr()
    ctx = _make_context(commits=["Commit abc123: Rotate leaked credentials"])
    assert "Rotate leaked credentials" in _build_input(pr, ctx)


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


def test_call_openai_passes_security_system_prompt() -> None:
    mock_client = MagicMock()
    mock_client.responses.create.return_value = MagicMock(output_text="ok")

    with patch(_PATCH.format("OpenAI"), return_value=mock_client):
        _call_openai("some prompt")

    kwargs = mock_client.responses.create.call_args.kwargs
    assert kwargs["instructions"] == _SYSTEM_PROMPT
    assert kwargs["input"] == "some prompt"


def test_system_prompt_is_scoped_to_security() -> None:
    lowered = _SYSTEM_PROMPT.lower()
    assert "secret" in lowered
    assert "injection" in lowered
    assert "deserialization" in lowered
    assert "authentication" in lowered or "authorization" in lowered
    assert "prompt injection" in lowered


def test_system_prompt_requires_self_check_before_specific_claims() -> None:
    lowered = _SYSTEM_PROMPT.lower()
    assert "re-read the exact diff line" in lowered


# ── _parse_response ──────────────────────────────────────────────────────────


def test_parse_response_maps_all_fields() -> None:
    raw = json.dumps(
        {
            "summary": "Uses eval() on user input",
            "verdict": "REQUEST_CHANGES",
            "issues": ["Command injection via eval()"],
            "suggestions": ["Replace eval() with ast.literal_eval()"],
        }
    )
    result = _parse_response(raw)

    assert isinstance(result, AgentResult)
    assert result.summary == "Uses eval() on user input"
    assert result.verdict == "REQUEST_CHANGES"
    assert result.issues == ["Command injection via eval()"]
    assert result.suggestions == ["Replace eval() with ast.literal_eval()"]


def test_parse_response_strips_json_code_fence() -> None:
    raw = "```json\n" + _VALID_JSON + "\n```"
    result = _parse_response(raw)
    assert result.verdict == "REQUEST_CHANGES"


def test_parse_response_strips_plain_code_fence() -> None:
    raw = "```\n" + _VALID_JSON + "\n```"
    result = _parse_response(raw)
    assert result.verdict == "REQUEST_CHANGES"


def test_parse_response_issues_defaults_to_empty_list() -> None:
    raw = json.dumps({"summary": "No concerns found.", "verdict": "APPROVE"})
    result = _parse_response(raw)
    assert result.issues == []


def test_parse_response_suggestions_defaults_to_empty_list() -> None:
    raw = json.dumps({"summary": "No concerns found.", "verdict": "APPROVE"})
    result = _parse_response(raw)
    assert result.suggestions == []


# ── security_agent (node) ────────────────────────────────────────────────────


def test_security_agent_returns_security_result_key_only() -> None:
    pr = _make_pr()
    state = _make_state(pr, _make_context())
    mock_client = MagicMock()
    mock_client.responses.create.return_value = MagicMock(output_text=_VALID_JSON)

    with patch(_PATCH.format("OpenAI"), return_value=mock_client):
        update = security_agent(state)

    assert set(update.keys()) == {"security_result"}


def test_security_agent_parses_openai_output_into_agent_result() -> None:
    pr = _make_pr()
    state = _make_state(pr, _make_context())
    mock_client = MagicMock()
    mock_client.responses.create.return_value = MagicMock(output_text=_VALID_JSON)

    with patch(_PATCH.format("OpenAI"), return_value=mock_client):
        update = security_agent(state)

    result = update["security_result"]
    assert isinstance(result, AgentResult)
    assert result.verdict == "REQUEST_CHANGES"
    assert result.issues == ["Hardcoded API key in config.py line 12"]
    assert result.suggestions == ["Move the key to an environment variable"]


def test_security_agent_sends_pr_diff_to_openai() -> None:
    pr = _make_pr(diff="unique-security-diff-marker")
    state = _make_state(pr, _make_context())
    mock_client = MagicMock()
    mock_client.responses.create.return_value = MagicMock(output_text=_VALID_JSON)

    with patch(_PATCH.format("OpenAI"), return_value=mock_client):
        security_agent(state)

    prompt = mock_client.responses.create.call_args.kwargs["input"]
    assert "unique-security-diff-marker" in prompt
