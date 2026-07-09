from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agents.state import AgentResult, ReviewState
from agents.summarizer import _merge_verdict, summarizer
from gh.pr_fetcher import PRData
from retrieval.context_builder import PRContext

_NOW = datetime(2024, 6, 1, tzinfo=UTC)


def _make_pr() -> PRData:
    return PRData(
        number=7,
        title="Add retry logic",
        body="Fixes flaky CI",
        state="open",
        author="dev",
        base_branch="main",
        head_branch="feature/retry",
        created_at=_NOW,
        updated_at=_NOW,
        changed_files=[],
        diff="diff --git a/gh/client.py b/gh/client.py",
    )


def _result(
    verdict: str = "APPROVE",
    summary: str = "Looks fine",
    issues: list[str] | None = None,
    suggestions: list[str] | None = None,
) -> AgentResult:
    return AgentResult(
        summary=summary, verdict=verdict, issues=issues or [], suggestions=suggestions or []
    )


def _make_state(security: AgentResult, quality: AgentResult, test: AgentResult) -> ReviewState:
    return {
        "pr": _make_pr(),
        "context": PRContext(similar_issues=[], similar_prs=[], related_commits=[]),
        "security_result": security,
        "quality_result": quality,
        "test_result": test,
        "final_verdict": None,
    }


# ── _merge_verdict — all combinations from the acceptance criteria ─────────────


def test_merge_verdict_all_approve() -> None:
    assert _merge_verdict(["APPROVE", "APPROVE", "APPROVE"]) == "APPROVE"


def test_merge_verdict_one_requests_changes() -> None:
    assert _merge_verdict(["APPROVE", "REQUEST_CHANGES", "APPROVE"]) == "REQUEST_CHANGES"


def test_merge_verdict_one_comment_only() -> None:
    assert _merge_verdict(["APPROVE", "COMMENT", "APPROVE"]) == "COMMENT"


def test_merge_verdict_mixed_comment_and_request_changes() -> None:
    assert _merge_verdict(["COMMENT", "REQUEST_CHANGES", "APPROVE"]) == "REQUEST_CHANGES"


def test_merge_verdict_all_request_changes() -> None:
    assert _merge_verdict(["REQUEST_CHANGES", "REQUEST_CHANGES", "REQUEST_CHANGES"]) == (
        "REQUEST_CHANGES"
    )


def test_merge_verdict_all_comment() -> None:
    assert _merge_verdict(["COMMENT", "COMMENT", "COMMENT"]) == "COMMENT"


# ── summarizer (node) ────────────────────────────────────────────────────────


def test_summarizer_returns_final_verdict_key_only() -> None:
    state = _make_state(_result(), _result(), _result())

    update = summarizer(state)

    assert set(update.keys()) == {"final_verdict"}


def test_summarizer_all_approve_yields_approve() -> None:
    state = _make_state(
        _result(verdict="APPROVE"), _result(verdict="APPROVE"), _result(verdict="APPROVE")
    )

    result = summarizer(state)["final_verdict"]

    assert result.verdict == "APPROVE"


def test_summarizer_one_requests_changes_yields_request_changes() -> None:
    state = _make_state(
        _result(verdict="REQUEST_CHANGES", issues=["Hardcoded secret"]),
        _result(verdict="APPROVE"),
        _result(verdict="APPROVE"),
    )

    result = summarizer(state)["final_verdict"]

    assert result.verdict == "REQUEST_CHANGES"


def test_summarizer_one_comment_only_yields_comment() -> None:
    state = _make_state(
        _result(verdict="APPROVE"),
        _result(verdict="COMMENT", suggestions=["Add a docstring"]),
        _result(verdict="APPROVE"),
    )

    result = summarizer(state)["final_verdict"]

    assert result.verdict == "COMMENT"


def test_summarizer_mixed_verdicts_yields_request_changes() -> None:
    state = _make_state(
        _result(verdict="COMMENT"),
        _result(verdict="REQUEST_CHANGES"),
        _result(verdict="APPROVE"),
    )

    result = summarizer(state)["final_verdict"]

    assert result.verdict == "REQUEST_CHANGES"


def test_summarizer_combines_issues_from_all_agents() -> None:
    state = _make_state(
        _result(issues=["Hardcoded secret"]),
        _result(issues=["Missing type hints"]),
        _result(issues=["No test for empty input"]),
    )

    result = summarizer(state)["final_verdict"]

    assert result.issues == ["Hardcoded secret", "Missing type hints", "No test for empty input"]


def test_summarizer_combines_suggestions_from_all_agents() -> None:
    state = _make_state(
        _result(suggestions=["Use env vars for secrets"]),
        _result(suggestions=["Add a docstring"]),
        _result(suggestions=["Add an edge-case test"]),
    )

    result = summarizer(state)["final_verdict"]

    assert result.suggestions == [
        "Use env vars for secrets",
        "Add a docstring",
        "Add an edge-case test",
    ]


def test_summarizer_empty_issues_and_suggestions_when_all_clean() -> None:
    state = _make_state(_result(), _result(), _result())

    result = summarizer(state)["final_verdict"]

    assert result.issues == []
    assert result.suggestions == []


def test_summarizer_summary_includes_each_agent_summary() -> None:
    state = _make_state(
        _result(summary="No secrets found"),
        _result(summary="Naming is inconsistent"),
        _result(summary="Missing edge-case tests"),
    )

    result = summarizer(state)["final_verdict"]

    assert "No secrets found" in result.summary
    assert "Naming is inconsistent" in result.summary
    assert "Missing edge-case tests" in result.summary


@pytest.mark.parametrize(
    "verdicts",
    [
        ("APPROVE", "APPROVE", "APPROVE"),
        ("REQUEST_CHANGES", "APPROVE", "APPROVE"),
        ("APPROVE", "COMMENT", "APPROVE"),
        ("COMMENT", "REQUEST_CHANGES", "COMMENT"),
    ],
)
def test_summarizer_verdict_matches_merge_policy(verdicts: tuple[str, str, str]) -> None:
    security_v, quality_v, test_v = verdicts
    state = _make_state(
        _result(verdict=security_v), _result(verdict=quality_v), _result(verdict=test_v)
    )

    result = summarizer(state)["final_verdict"]

    assert result.verdict == _merge_verdict(list(verdicts))
