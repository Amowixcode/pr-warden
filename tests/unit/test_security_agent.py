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
from gh.repo_fetcher import CommitData, IssueData
from retrieval.context_builder import PersistedAgentResult, PRContext, ReviewRecord

_PATCH = "agents.security_agent.{}"
_NOW = datetime(2024, 6, 1, tzinfo=UTC)

_DEFAULT_DIFF = "diff --git a/payments.py b/payments.py\n+API_KEY = 'sk_live_abc123'"

_VALID_JSON = json.dumps(
    {
        "summary": "Found a hardcoded API key.",
        "verdict": "REQUEST_CHANGES",
        "issues": [
            {
                "issue": "Hardcoded API key in config.py line 12",
                "evidence": "API_KEY = 'sk_live_abc123'",
            }
        ],
        "suggestions": ["Move the key to an environment variable"],
    }
)


def _make_pr(
    number: int = 7,
    title: str = "Add payment integration",
    body: str = "Integrates the Stripe API.",
    diff: str = "diff --git a/payments.py b/payments.py\n+API_KEY = 'sk_live_abc123'",
    commits: list[CommitData] | None = None,
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
        commits=commits or [],
    )


def _make_commit(message: str, sha: str = "abc123") -> CommitData:
    return CommitData(sha=sha, message=message, author="dev", committed_at=_NOW, url="")


def _make_issue(
    number: int = 1, title: str = "Leaked credential report", body: str = "Repro steps"
) -> IssueData:
    return IssueData(
        number=number,
        title=title,
        body=body,
        state="open",
        labels=["security"],
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
        summary="Found a hardcoded secret",
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
    assert result.count("(none)") == 5


def test_build_input_contains_commit_messages_of_varying_quality() -> None:
    detailed = _make_commit(sha="aaa111", message="Rotate the leaked Stripe secret key")
    terse = _make_commit(sha="bbb222", message="fix")
    pr = _make_pr(commits=[detailed, terse])
    ctx = _make_context()

    result = _build_input(pr, ctx)

    assert "Rotate the leaked Stripe secret key" in result
    assert "fix" in result


def test_build_input_shows_no_commits_placeholder_when_empty() -> None:
    pr = _make_pr(commits=[])
    ctx = _make_context()
    result = _build_input(pr, ctx)
    assert "### Commit Messages\n(none)" in result


def test_build_input_contains_linked_issue_content() -> None:
    issue = _make_issue(number=27670, title="API key leaked in logs", body="Steps to reproduce...")
    pr = _make_pr()
    ctx = _make_context(linked_issues=[issue])

    result = _build_input(pr, ctx)

    assert "#27670: API key leaked in logs" in result
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
    assert "Found a hardcoded secret" in result


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


def test_system_prompt_requests_terse_structured_findings() -> None:
    lowered = _SYSTEM_PROMPT.lower()
    assert "terse" in lowered
    assert "file" in lowered and "line" in lowered
    assert "at most 3 suggestions" in lowered
    assert "single short line" in lowered


def test_system_prompt_requires_evidence_field() -> None:
    lowered = _SYSTEM_PROMPT.lower()
    assert '"evidence"' in lowered
    assert "copied verbatim from the diff" in lowered
    assert "automatically discarded" in lowered


# ── _parse_response ──────────────────────────────────────────────────────────


def test_parse_response_maps_all_fields() -> None:
    diff = "diff --git a/app.py b/app.py\n+eval(user_input)"
    raw = json.dumps(
        {
            "summary": "Uses eval() on user input",
            "verdict": "REQUEST_CHANGES",
            "issues": [{"issue": "Command injection via eval()", "evidence": "eval(user_input)"}],
            "suggestions": ["Replace eval() with ast.literal_eval()"],
        }
    )
    result = _parse_response(raw, diff)

    assert isinstance(result, AgentResult)
    assert result.summary == "Uses eval() on user input"
    assert result.verdict == "REQUEST_CHANGES"
    assert result.issues == ["Command injection via eval()"]
    assert result.suggestions == ["Replace eval() with ast.literal_eval()"]


def test_parse_response_strips_json_code_fence() -> None:
    raw = "```json\n" + _VALID_JSON + "\n```"
    result = _parse_response(raw, _DEFAULT_DIFF)
    assert result.verdict == "REQUEST_CHANGES"


def test_parse_response_strips_plain_code_fence() -> None:
    raw = "```\n" + _VALID_JSON + "\n```"
    result = _parse_response(raw, _DEFAULT_DIFF)
    assert result.verdict == "REQUEST_CHANGES"


def test_parse_response_issues_defaults_to_empty_list() -> None:
    raw = json.dumps({"summary": "No concerns found.", "verdict": "APPROVE"})
    result = _parse_response(raw, _DEFAULT_DIFF)
    assert result.issues == []


def test_parse_response_suggestions_defaults_to_empty_list() -> None:
    raw = json.dumps({"summary": "No concerns found.", "verdict": "APPROVE"})
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
                    "issue": "Hardcoded API key in config.py line 12",
                    "evidence": "API_KEY = os.environ['STRIPE_KEY']",
                }
            ],
            "suggestions": [],
        }
    )
    result = _parse_response(raw, _DEFAULT_DIFF)
    assert result.issues == []


def test_parse_response_keeps_issue_with_verified_evidence() -> None:
    result = _parse_response(_VALID_JSON, _DEFAULT_DIFF)
    assert result.issues == ["Hardcoded API key in config.py line 12"]


def test_parse_response_drops_issue_missing_evidence_field() -> None:
    raw = json.dumps(
        {
            "summary": "Found a problem.",
            "verdict": "REQUEST_CHANGES",
            "issues": [{"issue": "Hardcoded API key in config.py line 12"}],
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
            "issues": ["Hardcoded API key in config.py line 12"],
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
                    "is commented out",
                    "evidence": "// bridge?.shutdown();",
                }
            ],
            "suggestions": [],
        }
    )
    result = _parse_response(raw, diff)
    assert result.issues == []


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


def test_security_agent_drops_issues_with_evidence_not_in_diff() -> None:
    """Confirms end-to-end that verification runs against state["pr"].diff specifically —
    not the full prompt (which also contains commit messages, linked issues, historical
    context) or some other text.
    """
    pr = _make_pr(diff="diff --git a/payments.py b/payments.py\n+charge(amount)")
    state = _make_state(pr, _make_context())
    fabricated_json = json.dumps(
        {
            "summary": "Found a problem.",
            "verdict": "REQUEST_CHANGES",
            "issues": [
                {"issue": "Hardcoded secret found", "evidence": "API_KEY = 'sk_live_abc123'"}
            ],
            "suggestions": [],
        }
    )
    mock_client = MagicMock()
    mock_client.responses.create.return_value = MagicMock(output_text=fabricated_json)

    with patch(_PATCH.format("OpenAI"), return_value=mock_client):
        update = security_agent(state)

    assert update["security_result"].issues == []
