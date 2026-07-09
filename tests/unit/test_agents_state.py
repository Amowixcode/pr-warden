from __future__ import annotations

from datetime import UTC, datetime

from agents.state import AgentResult, ReviewState
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


def _make_context() -> PRContext:
    return PRContext(similar_issues=[], similar_prs=[], related_commits=[])


# ── AgentResult ──────────────────────────────────────────────────────────────


def test_agent_result_fields() -> None:
    result = AgentResult(
        summary="Looks fine",
        verdict="APPROVE",
        issues=[],
        suggestions=["Consider adding a docstring"],
    )

    assert result.summary == "Looks fine"
    assert result.verdict == "APPROVE"
    assert result.issues == []
    assert result.suggestions == ["Consider adding a docstring"]


# ── ReviewState ──────────────────────────────────────────────────────────────


def test_review_state_before_any_agent_runs() -> None:
    state: ReviewState = {
        "pr": _make_pr(),
        "context": _make_context(),
        "security_result": None,
        "quality_result": None,
        "test_result": None,
        "final_verdict": None,
    }

    assert state["pr"].number == 7
    assert state["security_result"] is None
    assert state["final_verdict"] is None


def test_review_state_after_agents_and_summarizer_run() -> None:
    security = AgentResult(summary="No issues found", verdict="APPROVE", issues=[], suggestions=[])
    quality = AgentResult(
        summary="Missing docstring", verdict="COMMENT", issues=[], suggestions=["Add a docstring"]
    )
    test = AgentResult(
        summary="No test coverage", verdict="REQUEST_CHANGES", issues=["No tests"], suggestions=[]
    )
    final = AgentResult(
        summary="Needs tests before merge",
        verdict="REQUEST_CHANGES",
        issues=["No tests"],
        suggestions=["Add a docstring"],
    )

    state: ReviewState = {
        "pr": _make_pr(),
        "context": _make_context(),
        "security_result": security,
        "quality_result": quality,
        "test_result": test,
        "final_verdict": final,
    }

    assert state["security_result"].verdict == "APPROVE"
    assert state["quality_result"].verdict == "COMMENT"
    assert state["test_result"].verdict == "REQUEST_CHANGES"
    assert state["final_verdict"].verdict == "REQUEST_CHANGES"
