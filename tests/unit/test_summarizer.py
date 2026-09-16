from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agents.state import AgentResult, ReviewState
from agents.summarizer import _merge_verdict, _synthesize_summary, summarizer
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
    assert _merge_verdict(["APPROVE", "APPROVE", "APPROVE"], has_issues=False) == "APPROVE"


def test_merge_verdict_one_requests_changes() -> None:
    """REQUEST_CHANGES with no surviving issues degrades to COMMENT — the agent set that
    verdict before evidence verification ran, and every issue backing it got dropped.
    """
    verdicts = ["APPROVE", "REQUEST_CHANGES", "APPROVE"]
    assert _merge_verdict(verdicts, has_issues=False) == "COMMENT"


def test_merge_verdict_one_comment_only() -> None:
    assert _merge_verdict(["APPROVE", "COMMENT", "APPROVE"], has_issues=False) == "COMMENT"


def test_merge_verdict_mixed_comment_and_request_changes() -> None:
    """Same degrade rule applies even alongside another agent's COMMENT verdict."""
    verdicts = ["COMMENT", "REQUEST_CHANGES", "APPROVE"]
    assert _merge_verdict(verdicts, has_issues=False) == "COMMENT"


def test_merge_verdict_mixed_comment_and_request_changes_with_issue() -> None:
    """Same verdict combination as above, but with a surviving issue — REQUEST_CHANGES still
    wins, confirming the degrade rule only fires when has_issues is False.
    """
    verdicts = ["COMMENT", "REQUEST_CHANGES", "APPROVE"]
    assert _merge_verdict(verdicts, has_issues=True) == "REQUEST_CHANGES"


def test_merge_verdict_all_request_changes() -> None:
    """Even when every agent says REQUEST_CHANGES, zero surviving issues still degrades to
    COMMENT — the raw per-agent verdicts alone are never trusted over has_issues.
    """
    verdicts = ["REQUEST_CHANGES", "REQUEST_CHANGES", "REQUEST_CHANGES"]
    assert _merge_verdict(verdicts, has_issues=False) == "COMMENT"


def test_merge_verdict_all_request_changes_with_issues() -> None:
    verdicts = ["REQUEST_CHANGES", "REQUEST_CHANGES", "REQUEST_CHANGES"]
    assert _merge_verdict(verdicts, has_issues=True) == "REQUEST_CHANGES"


def test_merge_verdict_all_comment() -> None:
    assert _merge_verdict(["COMMENT", "COMMENT", "COMMENT"], has_issues=False) == "COMMENT"


def test_merge_verdict_bumps_approve_to_comment_when_has_issues() -> None:
    """Safety net: even if every agent's own verdict says APPROVE, a non-empty merged issues
    list must never surface as an APPROVE verdict.
    """
    verdicts = ["APPROVE", "APPROVE", "APPROVE"]
    assert _merge_verdict(verdicts, has_issues=True) == "COMMENT"


def test_merge_verdict_request_changes_still_wins_when_has_issues() -> None:
    """REQUEST_CHANGES survives the merge as long as a real issue backs it up — has_issues=True
    must not downgrade it to COMMENT.
    """
    verdicts = ["REQUEST_CHANGES", "APPROVE", "APPROVE"]
    assert _merge_verdict(verdicts, has_issues=True) == "REQUEST_CHANGES"


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


def test_summarizer_mixed_verdicts_no_issues_degrades_to_comment() -> None:
    """None of the three agents has any surviving issues, so even though one said
    REQUEST_CHANGES, the merge degrades it to COMMENT.
    """
    state = _make_state(
        _result(verdict="COMMENT"),
        _result(verdict="REQUEST_CHANGES"),
        _result(verdict="APPROVE"),
    )

    result = summarizer(state)["final_verdict"]

    assert result.verdict == "COMMENT"


def test_summarizer_mixed_verdicts_with_issue_yields_request_changes() -> None:
    """Same three-verdict mix, but the REQUEST_CHANGES agent has a real surviving issue — the
    merge keeps REQUEST_CHANGES.
    """
    state = _make_state(
        _result(verdict="COMMENT"),
        _result(verdict="REQUEST_CHANGES", issues=["Hardcoded secret"]),
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


def test_summarizer_all_clean_summary_is_synthesized_not_concatenated() -> None:
    state = _make_state(
        _result(summary="No secrets found"),
        _result(summary="Naming is inconsistent"),
        _result(summary="Missing edge-case tests"),
    )

    result = summarizer(state)["final_verdict"]

    # None of the agents' own summary text should appear verbatim — the summary is a
    # synthesized sentence about the (clean) outcome, not a concatenation of their text.
    assert "No secrets found" not in result.summary
    assert "Naming is inconsistent" not in result.summary
    assert "Missing edge-case tests" not in result.summary
    assert result.summary == "No blocking concerns from security, quality, or test coverage review."


def test_summarizer_flagged_summary_names_agents_and_issue_count() -> None:
    state = _make_state(
        _result(verdict="REQUEST_CHANGES", issues=["Hardcoded secret"]),
        _result(verdict="APPROVE"),
        _result(verdict="COMMENT", issues=["No edge-case test"]),
    )

    result = summarizer(state)["final_verdict"]

    assert result.summary == "REQUEST_CHANGES — 2 issues flagged by security, test coverage."


def test_summarizer_flagged_summary_singular_issue_wording() -> None:
    state = _make_state(
        _result(verdict="REQUEST_CHANGES", issues=["Hardcoded secret"]),
        _result(verdict="APPROVE"),
        _result(verdict="APPROVE"),
    )

    result = summarizer(state)["final_verdict"]

    assert result.summary == "REQUEST_CHANGES — 1 issue flagged by security."


def test_summarizer_caps_total_issues() -> None:
    state = _make_state(
        _result(issues=["a", "b", "c"]),
        _result(issues=["d", "e"]),
        _result(issues=["f", "g"]),
    )

    result = summarizer(state)["final_verdict"]

    # Round-robin interleaved (a,d,f / b,e,g / c,...) then capped at 5 — not a flat
    # concatenation, so security's 3rd item ("c") doesn't get priority over quality/test.
    assert len(result.issues) == 5
    assert result.issues == ["a", "d", "f", "b", "e"]


def test_summarizer_caps_total_suggestions() -> None:
    state = _make_state(
        _result(suggestions=["a", "b"]),
        _result(suggestions=["c", "d"]),
        _result(suggestions=["e", "f"]),
    )

    result = summarizer(state)["final_verdict"]

    # Round-robin interleaved (a,c,e / b,d,f) then capped at 3 — one from each agent, not
    # security's first two crowding out quality's and test's.
    assert len(result.suggestions) == 3
    assert result.suggestions == ["a", "c", "e"]


def test_summarizer_suggestions_include_all_agents_when_one_agent_has_many() -> None:
    """Regression test for the PR #36982 bug: security alone returned enough suggestions to
    fill the total cap, silently dropping quality's and test's suggestions entirely from the
    Final Verdict. Uses distinct, uniquely identifiable per-agent strings so any future
    mix-up (wrong agent's list substituted, or one agent crowding out the others) is caught
    immediately rather than passing by coincidence.
    """
    state = _make_state(
        _result(suggestions=["SECURITY-1", "SECURITY-2", "SECURITY-3"]),
        _result(suggestions=["QUALITY-1"]),
        _result(suggestions=["TEST-1"]),
    )

    result = summarizer(state)["final_verdict"]

    assert any(s.startswith("SECURITY-") for s in result.suggestions)
    assert any(s.startswith("QUALITY-") for s in result.suggestions)
    assert any(s.startswith("TEST-") for s in result.suggestions)
    assert result.suggestions == ["SECURITY-1", "QUALITY-1", "TEST-1"]


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

    assert result.verdict == _merge_verdict(list(verdicts), has_issues=False)


def test_summarizer_bumps_approve_to_comment_when_agent_has_issues() -> None:
    """Regression test for the PR #36994 bug: the quality agent returned verdict APPROVE
    alongside 3 legitimate, non-hallucinated issues, and that inconsistency propagated straight
    through to the Final Verdict. The merge layer must catch this even when every agent's own
    verdict says APPROVE.
    """
    state = _make_state(
        _result(verdict="APPROVE"),
        _result(
            verdict="APPROVE",
            summary="Some minor style points.",
            issues=[
                "Missing comment explaining the numeric check",
                "require() call inside beforeEach instead of at module scope",
                "Test names are too vague to describe what they verify",
            ],
        ),
        _result(verdict="APPROVE"),
    )

    result = summarizer(state)["final_verdict"]

    assert result.verdict == "COMMENT"
    assert len(result.issues) == 3
    assert "Missing comment explaining the numeric check" in result.issues


def test_summarizer_request_changes_with_no_surviving_issues_degrades_to_comment() -> None:
    """Regression test for issue #124: an agent sets REQUEST_CHANGES before evidence
    verification runs. If every finding it reported fails verification, the per-agent issues
    list ends up empty — but the merge layer must not trust the stale REQUEST_CHANGES verdict
    that was set before that filtering happened. The final verdict must degrade to COMMENT with
    no issues, not tell the user to fix something while showing them nothing to fix.
    """
    state = _make_state(
        _result(verdict="REQUEST_CHANGES", issues=[]),
        _result(verdict="APPROVE"),
        _result(verdict="APPROVE"),
    )

    result = summarizer(state)["final_verdict"]

    assert result.verdict == "COMMENT"
    assert result.issues == []


def test_synthesize_summary_no_issues_survived_has_no_dangling_period() -> None:
    """Regression test for issue #124: when nothing survived verification, flagged_by is empty
    and the old format string produced 'COMMENT — 0 issues flagged by .' — a dangling period.
    """
    summary = _synthesize_summary("COMMENT", [], 0)

    assert "flagged by ." not in summary
    assert summary == "COMMENT — no findings survived evidence verification."
