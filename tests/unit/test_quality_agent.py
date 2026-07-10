from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from llama_index.core.schema import NodeWithScore, TextNode

from agents.quality_agent import (
    _SYSTEM_PROMPT,
    _build_input,
    _call_openai,
    _parse_response,
    quality_agent,
)
from agents.state import AgentResult, ReviewState
from config.settings import settings
from gh.pr_fetcher import PRData
from gh.repo_fetcher import CommitData, IssueData
from retrieval.context_builder import PersistedAgentResult, PRContext, ReviewRecord

_PATCH = "agents.quality_agent.{}"
_NOW = datetime(2024, 6, 1, tzinfo=UTC)

_VALID_JSON = json.dumps(
    {
        "summary": "Missing type hints and a docstring on the new function.",
        "verdict": "COMMENT",
        "issues": ["fetch_data() has no type hints"],
        "suggestions": ["Add a docstring and return type annotation"],
    }
)


def _make_pr(
    number: int = 7,
    title: str = "Add data fetch helper",
    body: str = "Adds a helper to fetch remote data.",
    diff: str = "diff --git a/util.py b/util.py\n+def fetch_data(x):\n+    return x",
    commits: list[CommitData] | None = None,
) -> PRData:
    return PRData(
        number=number,
        title=title,
        body=body,
        state="open",
        author="dev",
        base_branch="main",
        head_branch="feature/fetch-helper",
        created_at=_NOW,
        updated_at=_NOW,
        changed_files=[],
        diff=diff,
        commits=commits or [],
    )


def _make_commit(message: str, sha: str = "abc123") -> CommitData:
    return CommitData(sha=sha, message=message, author="dev", committed_at=_NOW, url="")


def _make_issue(number: int = 1, title: str = "Linked bug", body: str = "Repro steps") -> IssueData:
    return IssueData(
        number=number,
        title=title,
        body=body,
        state="open",
        labels=["bug"],
        author="reporter",
        created_at=_NOW,
        updated_at=_NOW,
        closed_at=None,
    )


def _make_node(text: str) -> NodeWithScore:
    return NodeWithScore(node=TextNode(text=text), score=0.9)


def _make_review_record(head_sha: str = "abc1234", verdict: str = "COMMENT") -> ReviewRecord:
    agent = PersistedAgentResult(summary="ok", verdict="APPROVE", issues=[], suggestions=[])
    return ReviewRecord(
        head_sha=head_sha,
        verdict=verdict,
        summary="Found a minor naming issue",
        issues=[],
        suggestions=[],
        security_result=agent,
        quality_result=agent,
        test_result=agent,
        reviewed_at=_NOW,
    )


def _make_context(
    issues: list[str] | None = None,
    prs: list[str] | None = None,
    commits: list[str] | None = None,
    linked_issues: list[IssueData] | None = None,
    prior_review: ReviewRecord | None = None,
) -> PRContext:
    return PRContext(
        similar_issues=[_make_node(t) for t in (issues or [])],
        similar_prs=[_make_node(t) for t in (prs or [])],
        related_commits=[_make_node(t) for t in (commits or [])],
        linked_issues=linked_issues or [],
        prior_review=prior_review,
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
    ctx = _make_context(issues=["Issue #1: Inconsistent naming in prior PR"])
    assert "Inconsistent naming in prior PR" in _build_input(pr, ctx)


def test_build_input_contains_pr_node_text() -> None:
    pr = _make_pr()
    ctx = _make_context(prs=["Merged PR #5: Refactor for readability"])
    assert "Refactor for readability" in _build_input(pr, ctx)


def test_build_input_contains_commit_node_text() -> None:
    pr = _make_pr()
    ctx = _make_context(commits=["Commit abc123: Simplify complex conditional"])
    assert "Simplify complex conditional" in _build_input(pr, ctx)


def test_build_input_empty_context_renders_none() -> None:
    pr = _make_pr()
    ctx = _make_context()
    result = _build_input(pr, ctx)
    assert result.count("(none)") == 5


def test_build_input_contains_commit_messages_of_varying_quality() -> None:
    detailed = _make_commit(
        sha="aaa111", message="Fix the off-by-one error in the pagination cursor"
    )
    terse = _make_commit(sha="bbb222", message="wip")
    pr = _make_pr(commits=[detailed, terse])
    ctx = _make_context()

    result = _build_input(pr, ctx)

    assert "Fix the off-by-one error in the pagination cursor" in result
    assert "wip" in result


def test_build_input_shows_no_commits_placeholder_when_empty() -> None:
    pr = _make_pr(commits=[])
    ctx = _make_context()
    result = _build_input(pr, ctx)
    assert "### Commit Messages\n(none)" in result


def test_build_input_contains_linked_issue_content() -> None:
    issue = _make_issue(number=27670, title="Crash on mount", body="Steps to reproduce...")
    pr = _make_pr()
    ctx = _make_context(linked_issues=[issue])

    result = _build_input(pr, ctx)

    assert "#27670: Crash on mount" in result
    assert "Steps to reproduce..." in result


def test_build_input_shows_no_linked_issues_placeholder_when_empty() -> None:
    pr = _make_pr()
    ctx = _make_context(linked_issues=[])
    result = _build_input(pr, ctx)
    assert "## Linked Issues\n(none)" in result


def test_build_input_includes_incremental_review_block_when_prior_review_present() -> None:
    prior = _make_review_record(head_sha="deadbeef1234", verdict="COMMENT")
    pr = _make_pr()
    ctx = _make_context(prior_review=prior)

    result = _build_input(pr, ctx)

    assert "## Incremental Review" in result
    assert "deadbee" in result
    assert "COMMENT" in result
    assert "Found a minor naming issue" in result


def test_build_input_omits_incremental_review_block_when_no_prior_review() -> None:
    pr = _make_pr()
    ctx = _make_context(prior_review=None)

    result = _build_input(pr, ctx)

    assert "## Incremental Review" not in result


def test_build_input_passes_non_python_diff_through_unchanged() -> None:
    ts_diff = (
        "diff --git a/util.ts b/util.ts\n"
        "+export function fetchData(x: string): string {\n"
        "+  return x;\n"
        "+}"
    )
    pr = _make_pr(diff=ts_diff)
    ctx = _make_context()
    assert ts_diff in _build_input(pr, ctx)


# ── _call_openai ─────────────────────────────────────────────────────────────


def test_call_openai_uses_configured_max_retries() -> None:
    mock_client = MagicMock()
    mock_client.responses.create.return_value = MagicMock(output_text="ok")

    with patch(_PATCH.format("OpenAI"), return_value=mock_client) as mock_openai_cls:
        _call_openai("some prompt")

    mock_openai_cls.assert_called_once_with(
        api_key=settings.openai_api_key, max_retries=settings.openai_max_retries
    )


def test_call_openai_passes_quality_system_prompt() -> None:
    mock_client = MagicMock()
    mock_client.responses.create.return_value = MagicMock(output_text="ok")

    with patch(_PATCH.format("OpenAI"), return_value=mock_client):
        _call_openai("some prompt")

    kwargs = mock_client.responses.create.call_args.kwargs
    assert kwargs["instructions"] == _SYSTEM_PROMPT
    assert kwargs["input"] == "some prompt"


def test_system_prompt_is_scoped_to_quality() -> None:
    lowered = _SYSTEM_PROMPT.lower()
    assert "style" in lowered
    assert "maintainability" in lowered
    assert "naming" in lowered
    assert "documentation and type-annotation conventions" in lowered


def test_system_prompt_infers_language_instead_of_assuming_python() -> None:
    lowered = _SYSTEM_PROMPT.lower()
    assert "infer the language" in lowered
    assert "never assume python conventions apply to non-python code" in lowered
    # Regression guard: the old prompt stated pr-warden's own Python conventions as a
    # universal requirement — that exact phrasing must not come back.
    assert "type hints on all functions, docstrings on public functions" not in lowered


def test_system_prompt_requires_self_check_before_specific_claims() -> None:
    lowered = _SYSTEM_PROMPT.lower()
    assert "re-read the exact diff line" in lowered


def test_system_prompt_requests_terse_structured_findings() -> None:
    lowered = _SYSTEM_PROMPT.lower()
    assert "terse" in lowered
    assert "file" in lowered and "line" in lowered
    assert "at most 3 suggestions" in lowered
    assert "single short line" in lowered


# ── _parse_response ──────────────────────────────────────────────────────────


def test_parse_response_maps_all_fields() -> None:
    raw = json.dumps(
        {
            "summary": "Function is overly complex.",
            "verdict": "REQUEST_CHANGES",
            "issues": ["process() has 8 levels of nesting"],
            "suggestions": ["Extract helper functions to reduce nesting"],
        }
    )
    result = _parse_response(raw)

    assert isinstance(result, AgentResult)
    assert result.summary == "Function is overly complex."
    assert result.verdict == "REQUEST_CHANGES"
    assert result.issues == ["process() has 8 levels of nesting"]
    assert result.suggestions == ["Extract helper functions to reduce nesting"]


def test_parse_response_strips_json_code_fence() -> None:
    raw = "```json\n" + _VALID_JSON + "\n```"
    result = _parse_response(raw)
    assert result.verdict == "COMMENT"


def test_parse_response_strips_plain_code_fence() -> None:
    raw = "```\n" + _VALID_JSON + "\n```"
    result = _parse_response(raw)
    assert result.verdict == "COMMENT"


def test_parse_response_issues_defaults_to_empty_list() -> None:
    raw = json.dumps({"summary": "Looks clean.", "verdict": "APPROVE"})
    result = _parse_response(raw)
    assert result.issues == []


def test_parse_response_suggestions_defaults_to_empty_list() -> None:
    raw = json.dumps({"summary": "Looks clean.", "verdict": "APPROVE"})
    result = _parse_response(raw)
    assert result.suggestions == []


# ── quality_agent (node) ─────────────────────────────────────────────────────


def test_quality_agent_returns_quality_result_key_only() -> None:
    pr = _make_pr()
    state = _make_state(pr, _make_context())
    mock_client = MagicMock()
    mock_client.responses.create.return_value = MagicMock(output_text=_VALID_JSON)

    with patch(_PATCH.format("OpenAI"), return_value=mock_client):
        update = quality_agent(state)

    assert set(update.keys()) == {"quality_result"}


def test_quality_agent_parses_openai_output_into_agent_result() -> None:
    pr = _make_pr()
    state = _make_state(pr, _make_context())
    mock_client = MagicMock()
    mock_client.responses.create.return_value = MagicMock(output_text=_VALID_JSON)

    with patch(_PATCH.format("OpenAI"), return_value=mock_client):
        update = quality_agent(state)

    result = update["quality_result"]
    assert isinstance(result, AgentResult)
    assert result.verdict == "COMMENT"
    assert result.issues == ["fetch_data() has no type hints"]
    assert result.suggestions == ["Add a docstring and return type annotation"]


def test_quality_agent_sends_pr_diff_to_openai() -> None:
    pr = _make_pr(diff="unique-quality-diff-marker")
    state = _make_state(pr, _make_context())
    mock_client = MagicMock()
    mock_client.responses.create.return_value = MagicMock(output_text=_VALID_JSON)

    with patch(_PATCH.format("OpenAI"), return_value=mock_client):
        quality_agent(state)

    prompt = mock_client.responses.create.call_args.kwargs["input"]
    assert "unique-quality-diff-marker" in prompt


def test_quality_agent_handles_non_python_diff_via_same_code_path() -> None:
    """A TypeScript diff should flow through the exact same node logic as Python — there is
    no language-specific branching in the pipeline; conventions are enforced by the prompt
    alone (see _SYSTEM_PROMPT), not by code here."""
    go_diff = (
        "diff --git a/handler.go b/handler.go\n+func FetchData(x string) string {\n+\treturn x\n+}"
    )
    pr = _make_pr(diff=go_diff)
    state = _make_state(pr, _make_context())
    mock_client = MagicMock()
    mock_client.responses.create.return_value = MagicMock(output_text=_VALID_JSON)

    with patch(_PATCH.format("OpenAI"), return_value=mock_client):
        update = quality_agent(state)

    prompt = mock_client.responses.create.call_args.kwargs["input"]
    assert go_diff in prompt
    assert set(update.keys()) == {"quality_result"}
    assert isinstance(update["quality_result"], AgentResult)
