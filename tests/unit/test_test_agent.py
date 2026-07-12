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
from gh.repo_fetcher import CommitData, IssueData
from retrieval.context_builder import PersistedAgentResult, PRContext, ReviewRecord

_PATCH = "agents.test_agent.{}"
_NOW = datetime(2024, 6, 1, tzinfo=UTC)

_DEFAULT_DIFF = "diff --git a/client.py b/client.py\n+def _retry():\n+    pass"

_VALID_JSON = json.dumps(
    {
        "summary": "New retry logic has no tests covering the exhausted-retries path.",
        "verdict": "REQUEST_CHANGES",
        "issues": [
            {
                "issue": "No test for the case where all retries are exhausted",
                "evidence": "def _retry():",
            }
        ],
        "suggestions": ["Add a test asserting the exception raised after max_retries"],
    }
)


def _make_pr(
    number: int = 7,
    title: str = "Add retry logic",
    body: str = "Adds retry-with-backoff for transient errors.",
    diff: str = "diff --git a/client.py b/client.py\n+def _retry():\n+    pass",
    commits: list[CommitData] | None = None,
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
        commits=commits or [],
    )


def _make_commit(message: str, sha: str = "abc123") -> CommitData:
    return CommitData(sha=sha, message=message, author="dev", committed_at=_NOW, url="")


def _make_issue(
    number: int = 1, title: str = "Missing edge-case coverage", body: str = "Repro steps"
) -> IssueData:
    return IssueData(
        number=number,
        title=title,
        body=body,
        state="open",
        labels=["testing"],
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
        summary="Missing edge-case coverage",
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
    assert result.count("(none)") == 5


def test_build_input_contains_commit_messages_of_varying_quality() -> None:
    detailed = _make_commit(sha="aaa111", message="Add test coverage for the retry exhaustion path")
    terse = _make_commit(sha="bbb222", message="tests")
    pr = _make_pr(commits=[detailed, terse])
    ctx = _make_context()

    result = _build_input(pr, ctx)

    assert "Add test coverage for the retry exhaustion path" in result
    assert "tests" in result


def test_build_input_shows_no_commits_placeholder_when_empty() -> None:
    pr = _make_pr(commits=[])
    ctx = _make_context()
    result = _build_input(pr, ctx)
    assert "### Commit Messages\n(none)" in result


def test_build_input_contains_linked_issue_content() -> None:
    issue = _make_issue(
        number=27670, title="Missing edge-case coverage", body="Steps to reproduce..."
    )
    pr = _make_pr()
    ctx = _make_context(linked_issues=[issue])

    result = _build_input(pr, ctx)

    assert "#27670: Missing edge-case coverage" in result
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
    assert "Missing edge-case coverage" in result


def test_build_input_omits_incremental_review_block_when_no_prior_review() -> None:
    pr = _make_pr()
    ctx = _make_context(prior_review=None)

    result = _build_input(pr, ctx)

    assert "## Incremental Review" not in result


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


def test_system_prompt_requires_evidence_field() -> None:
    lowered = _SYSTEM_PROMPT.lower()
    assert '"evidence"' in lowered
    assert "copied verbatim from the diff" in lowered
    assert "automatically discarded" in lowered


# ── _parse_response ──────────────────────────────────────────────────────────


def test_parse_response_maps_all_fields() -> None:
    diff = "diff --git a/util.py b/util.py\n+def divide(a, b):\n+    return a / b"
    raw = json.dumps(
        {
            "summary": "No tests for the new error path.",
            "verdict": "REQUEST_CHANGES",
            "issues": [{"issue": "No test for empty-list input", "evidence": "def divide(a, b):"}],
            "suggestions": ["Add a test for the empty-list edge case"],
        }
    )
    result = _parse_response(raw, diff)

    assert isinstance(result, AgentResult)
    assert result.summary == "No tests for the new error path."
    assert result.verdict == "REQUEST_CHANGES"
    assert result.issues == ["No test for empty-list input"]
    assert result.suggestions == ["Add a test for the empty-list edge case"]


def test_parse_response_strips_json_code_fence() -> None:
    raw = "```json\n" + _VALID_JSON + "\n```"
    result = _parse_response(raw, _DEFAULT_DIFF)
    assert result.verdict == "REQUEST_CHANGES"


def test_parse_response_strips_plain_code_fence() -> None:
    raw = "```\n" + _VALID_JSON + "\n```"
    result = _parse_response(raw, _DEFAULT_DIFF)
    assert result.verdict == "REQUEST_CHANGES"


def test_parse_response_issues_defaults_to_empty_list() -> None:
    raw = json.dumps({"summary": "Well covered.", "verdict": "APPROVE"})
    result = _parse_response(raw, _DEFAULT_DIFF)
    assert result.issues == []


def test_parse_response_suggestions_defaults_to_empty_list() -> None:
    raw = json.dumps({"summary": "Well covered.", "verdict": "APPROVE"})
    result = _parse_response(raw, _DEFAULT_DIFF)
    assert result.suggestions == []


def test_parse_response_drops_issue_with_fabricated_evidence() -> None:
    """The acceptance criteria's required test: an issue whose evidence isn't a verbatim
    substring of the diff must be filtered out, not shown.
    """
    raw = json.dumps(
        {
            "summary": "Found a problem.",
            "verdict": "REQUEST_CHANGES",
            "issues": [
                {
                    "issue": "No test for the case where all retries are exhausted",
                    "evidence": "def _retry(max_attempts=3):",
                }
            ],
            "suggestions": [],
        }
    )
    result = _parse_response(raw, _DEFAULT_DIFF)
    assert result.issues == []


def test_parse_response_keeps_issue_with_verified_evidence() -> None:
    result = _parse_response(_VALID_JSON, _DEFAULT_DIFF)
    assert result.issues == ["No test for the case where all retries are exhausted"]


def test_parse_response_drops_issue_missing_evidence_field() -> None:
    raw = json.dumps(
        {
            "summary": "Found a problem.",
            "verdict": "REQUEST_CHANGES",
            "issues": [{"issue": "No test for the case where all retries are exhausted"}],
            "suggestions": [],
        }
    )
    result = _parse_response(raw, _DEFAULT_DIFF)
    assert result.issues == []


def test_parse_response_drops_issue_that_is_not_an_object() -> None:
    raw = json.dumps(
        {
            "summary": "Found a problem.",
            "verdict": "REQUEST_CHANGES",
            "issues": ["No test for the case where all retries are exhausted"],
            "suggestions": [],
        }
    )
    result = _parse_response(raw, _DEFAULT_DIFF)
    assert result.issues == []


def test_parse_response_drops_pr_36794_style_hallucination() -> None:
    """Regression test for the actual PR #36794 hallucination: the agent claimed a
    bridge?.shutdown() call was commented out, when the real diff shows it as live code with
    an explanatory comment on the line above. The fabricated evidence (claiming a commented-out
    form) doesn't appear verbatim in the real diff, so the mechanical check must drop it.
    """
    diff = (
        "diff --git a/packages/react-devtools-extensions/src/main/index.js "
        "b/packages/react-devtools-extensions/src/main/index.js\n"
        "+  // Cleanly shut down the bridge so the panel can reconnect on reload.\n"
        "+  bridge?.shutdown();\n"
    )
    raw = json.dumps(
        {
            "summary": "Found a dead code path.",
            "verdict": "COMMENT",
            "issues": [
                {
                    "issue": "index.js:460-475 — the else branch that calls bridge.shutdown() "
                    "is commented out, so it has no test coverage",
                    "evidence": "// bridge?.shutdown();",
                }
            ],
            "suggestions": [],
        }
    )
    result = _parse_response(raw, diff)
    assert result.issues == []


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


def test_test_agent_drops_issues_with_evidence_not_in_diff() -> None:
    """Confirms end-to-end that verification runs against state["pr"].diff specifically —
    not the full prompt (which also contains commit messages, linked issues, historical
    context) or some other text.
    """
    pr = _make_pr(diff="diff --git a/client.py b/client.py\n+def real_call():\n+    pass")
    state = _make_state(pr, _make_context())
    fabricated_json = json.dumps(
        {
            "summary": "Found a problem.",
            "verdict": "REQUEST_CHANGES",
            "issues": [{"issue": "No test for fake_call()", "evidence": "def fake_call():"}],
            "suggestions": [],
        }
    )
    mock_client = MagicMock()
    mock_client.responses.create.return_value = MagicMock(output_text=fabricated_json)

    with patch(_PATCH.format("OpenAI"), return_value=mock_client):
        update = run_test_agent(state)

    assert update["test_result"].issues == []
