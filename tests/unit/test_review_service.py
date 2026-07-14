from __future__ import annotations

from contextlib import ExitStack
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from llama_index.core.schema import NodeWithScore, TextNode

from agents.state import AgentResult
from core.review_service import ReviewResult, review_pr
from gh.pr_fetcher import PRData
from retrieval.context_builder import PersistedAgentResult, PRContext, ReviewRecord

_PATCH = "core.review_service.{}"
_NOW = datetime(2024, 6, 1, tzinfo=UTC)

_VALID_FINAL_VERDICT = AgentResult(
    summary="Looks good overall.",
    verdict="APPROVE",
    issues=["Missing type hint on line 5"],
    suggestions=["Add a docstring"],
)
_SECURITY_RESULT = AgentResult(
    summary="No secrets found", verdict="APPROVE", issues=[], suggestions=[]
)
_QUALITY_RESULT = AgentResult(
    summary="Missing type hint",
    verdict="APPROVE",
    issues=["Missing type hint on line 5"],
    suggestions=["Add a docstring"],
)
_TEST_RESULT = AgentResult(summary="Well covered", verdict="APPROVE", issues=[], suggestions=[])


def _make_pr(
    number: int = 7,
    title: str = "Fix login bug",
    body: str = "Resolves auth issue.",
    diff: str = "diff --git a/auth.py b/auth.py\n+fix",
    head_sha: str = "current-head-sha",
) -> PRData:
    return PRData(
        number=number,
        title=title,
        body=body,
        state="open",
        author="dev",
        base_branch="main",
        head_branch="fix/login",
        created_at=_NOW,
        updated_at=_NOW,
        changed_files=[],
        diff=diff,
        head_sha=head_sha,
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


def _make_persisted(summary: str = "cached summary") -> PersistedAgentResult:
    return PersistedAgentResult(summary=summary, verdict="APPROVE", issues=[], suggestions=[])


def _make_review_record(
    head_sha: str = "prior-head-sha",
    verdict: str = "COMMENT",
    summary: str = "Prior review summary",
) -> ReviewRecord:
    return ReviewRecord(
        head_sha=head_sha,
        verdict=verdict,
        summary=summary,
        issues=[],
        suggestions=[],
        security_result=_make_persisted("cached security summary"),
        quality_result=_make_persisted("cached quality summary"),
        test_result=_make_persisted("cached test summary"),
        reviewed_at=_NOW,
    )


_PATCH_TARGETS = {
    "fetch_pull_request": "fetch_pull_request",
    "fetch_linked_issues": "fetch_linked_issues",
    "fetch_diff_since": "fetch_diff_since",
    "load_review_record": "load_review_record",
    "save_review_record": "save_review_record",
    "build_pr_context": "build_pr_context",
    "build_chroma_collection": "build_chroma_collection",
    "build_vector_store_index": "build_vector_store_index",
    "get_embed_model": "get_embed_model",
    "graph_ainvoke": "graph.ainvoke",
    "GitHubClient": "GitHubClient",
}

# core.supabase_history.save_review lives outside core.review_service's own module, so it can't
# use the _PATCH.format() shorthand above — mocked separately in _apply() below. Without this,
# review_pr()'s real supabase_history.save_review call would fire against a real Supabase
# project whenever SUPABASE_URL/SUPABASE_KEY happen to be set in the environment running these
# "unit" tests.
_SUPABASE_SAVE_REVIEW_TARGET = "core.supabase_history.save_review"


def _make_patches(
    pr: PRData, context: PRContext, final_verdict: AgentResult = _VALID_FINAL_VERDICT
) -> dict:
    return {
        "fetch_pull_request": AsyncMock(return_value=pr),
        "fetch_linked_issues": AsyncMock(return_value=[]),
        "fetch_diff_since": AsyncMock(return_value=""),
        "load_review_record": MagicMock(return_value=None),
        "save_review_record": MagicMock(),
        "build_pr_context": AsyncMock(return_value=context),
        "build_chroma_collection": MagicMock(return_value=MagicMock()),
        "build_vector_store_index": MagicMock(return_value=MagicMock()),
        "get_embed_model": MagicMock(return_value=MagicMock()),
        "graph_ainvoke": AsyncMock(
            return_value={
                "final_verdict": final_verdict,
                "security_result": _SECURITY_RESULT,
                "quality_result": _QUALITY_RESULT,
                "test_result": _TEST_RESULT,
            }
        ),
        "GitHubClient": MagicMock(),
        "save_review_to_supabase": MagicMock(),
    }


def _apply(mocks: dict) -> ExitStack:
    """Enter every mocked dependency's patch as one combined context manager.

    Positionally indexing a growing tuple of separately-called patch() context managers
    (the previous convention here) stopped being readable once this test file needed to mock
    11 dependencies — ExitStack collapses that to a single `with _apply(mocks):`.
    """
    stack = ExitStack()
    for key, target in _PATCH_TARGETS.items():
        stack.enter_context(patch(_PATCH.format(target), mocks[key]))
    stack.enter_context(patch(_SUPABASE_SAVE_REVIEW_TARGET, mocks["save_review_to_supabase"]))
    return stack


# ── review_pr orchestration ──────────────────────────────────────────────────


async def test_review_pr_returns_review_result() -> None:
    pr = _make_pr()
    mocks = _make_patches(pr, _make_context())

    with _apply(mocks):
        result = await review_pr("owner", "repo", 7)

    assert isinstance(result, ReviewResult)


async def test_review_pr_pr_number_matches_input() -> None:
    pr = _make_pr(number=42)
    mocks = _make_patches(pr, _make_context())

    with _apply(mocks):
        result = await review_pr("owner", "repo", 42)

    assert result.pr_number == 42


async def test_review_pr_fields_from_final_verdict() -> None:
    pr = _make_pr()
    mocks = _make_patches(pr, _make_context())

    with _apply(mocks):
        result = await review_pr("owner", "repo", 7)

    assert result.summary == "Looks good overall."
    assert result.verdict == "APPROVE"
    assert result.issues == ["Missing type hint on line 5"]
    assert result.suggestions == ["Add a docstring"]


async def test_review_pr_passes_pr_to_graph() -> None:
    pr = _make_pr(title="Unique PR title XYZ", diff="unique-diff-marker-abc123")
    mocks = _make_patches(pr, _make_context())

    with _apply(mocks):
        await review_pr("owner", "repo", 7)

    initial_state = mocks["graph_ainvoke"].call_args.args[0]
    assert initial_state["pr"].title == "Unique PR title XYZ"
    assert initial_state["pr"].diff == "unique-diff-marker-abc123"


async def test_review_pr_passes_context_to_graph() -> None:
    pr = _make_pr()
    context = _make_context(issues=["Login fails on Safari"])
    mocks = _make_patches(pr, context)

    with _apply(mocks):
        await review_pr("owner", "repo", 7)

    initial_state = mocks["graph_ainvoke"].call_args.args[0]
    assert initial_state["context"] is context


async def test_review_pr_carries_per_agent_results_through() -> None:
    pr = _make_pr()
    mocks = _make_patches(pr, _make_context())

    with _apply(mocks):
        result = await review_pr("owner", "repo", 7)

    assert result.security_result == _SECURITY_RESULT
    assert result.quality_result == _QUALITY_RESULT
    assert result.test_result == _TEST_RESULT


async def test_review_pr_initial_state_has_no_agent_results_yet() -> None:
    pr = _make_pr()
    mocks = _make_patches(pr, _make_context())

    with _apply(mocks):
        await review_pr("owner", "repo", 7)

    initial_state = mocks["graph_ainvoke"].call_args.args[0]
    assert initial_state["security_result"] is None
    assert initial_state["quality_result"] is None
    assert initial_state["test_result"] is None
    assert initial_state["final_verdict"] is None


async def test_review_pr_fetches_linked_issues_from_pr_body_and_threads_into_context() -> None:
    pr = _make_pr(body="Fixes #27670 — the thing was crashing")
    context = _make_context()
    mocks = _make_patches(pr, context)
    mocks["fetch_linked_issues"] = AsyncMock(return_value=["linked-issue-marker"])

    with _apply(mocks):
        await review_pr("owner", "repo", 7)

    mocks["fetch_linked_issues"].assert_awaited_once()
    call_args = mocks["fetch_linked_issues"].call_args.args
    assert call_args[-1] == "Fixes #27670 — the thing was crashing"

    build_context_kwargs = mocks["build_pr_context"].call_args.kwargs
    assert build_context_kwargs["linked_issues"] == ["linked-issue-marker"]


# ── incremental review ───────────────────────────────────────────────────────


async def test_review_pr_first_review_is_full() -> None:
    """No prior record: fetch_diff_since is never called, full diff reaches the graph, and
    the result is not marked incremental — the acceptance criteria's "first review" case.
    """
    pr = _make_pr(diff="full-pr-diff")
    mocks = _make_patches(pr, _make_context())
    mocks["load_review_record"] = MagicMock(return_value=None)

    with _apply(mocks):
        result = await review_pr("owner", "repo", 7)

    mocks["fetch_diff_since"].assert_not_called()
    initial_state = mocks["graph_ainvoke"].call_args.args[0]
    assert initial_state["pr"].diff == "full-pr-diff"
    assert result.incremental is False
    assert result.cached is False
    mocks["save_review_record"].assert_called_once()


async def test_review_pr_second_review_is_incremental() -> None:
    """A prior record with a different head_sha: fetch_diff_since is called with the prior
    and current SHAs, and the incremental diff (not the full diff) reaches the graph.
    """
    pr = _make_pr(diff="full-pr-diff", head_sha="new-sha")
    context = _make_context()
    mocks = _make_patches(pr, context)
    prior = _make_review_record(head_sha="old-sha", verdict="COMMENT", summary="Prior notes")
    mocks["load_review_record"] = MagicMock(return_value=prior)
    mocks["fetch_diff_since"] = AsyncMock(return_value="only-the-new-commit-diff")

    with _apply(mocks):
        result = await review_pr("owner", "repo", 7)

    assert mocks["fetch_diff_since"].call_args.args[1:] == ("owner", "repo", "old-sha", "new-sha")

    initial_state = mocks["graph_ainvoke"].call_args.args[0]
    assert initial_state["pr"].diff == "only-the-new-commit-diff"

    build_context_kwargs = mocks["build_pr_context"].call_args.kwargs
    assert build_context_kwargs["prior_review"] is prior

    assert result.incremental is True
    assert result.cached is False
    assert result.prior_verdict == "COMMENT"
    assert result.prior_head_sha == "old-sha"


async def test_review_pr_no_new_commits_returns_cached_result_without_calling_agents() -> None:
    """The stored SHA equals the current HEAD SHA: no LLM calls, no RAG setup — the cached
    per-agent results from the prior record are returned directly.
    """
    pr = _make_pr(head_sha="same-sha")
    mocks = _make_patches(pr, _make_context())
    prior = _make_review_record(head_sha="same-sha", verdict="APPROVE", summary="All good")
    mocks["load_review_record"] = MagicMock(return_value=prior)

    with _apply(mocks):
        result = await review_pr("owner", "repo", 7)

    mocks["fetch_linked_issues"].assert_not_called()
    mocks["fetch_diff_since"].assert_not_called()
    mocks["build_chroma_collection"].assert_not_called()
    mocks["build_pr_context"].assert_not_called()
    mocks["graph_ainvoke"].assert_not_called()
    mocks["save_review_record"].assert_not_called()

    assert result.cached is True
    assert result.incremental is True
    assert result.verdict == "APPROVE"
    assert result.summary == "All good"
    assert result.security_result.summary == "cached security summary"
    assert result.quality_result.summary == "cached quality summary"
    assert result.test_result.summary == "cached test summary"


async def test_review_pr_full_flag_ignores_history() -> None:
    """full=True: load_review_record is never even called, so history can't influence the
    review regardless of what it would have returned.
    """
    pr = _make_pr(diff="full-pr-diff", head_sha="new-sha")
    mocks = _make_patches(pr, _make_context())
    mocks["load_review_record"] = MagicMock(
        return_value=_make_review_record(head_sha="new-sha")
    )  # would be a cache hit if consulted

    with _apply(mocks):
        result = await review_pr("owner", "repo", 7, full=True)

    mocks["load_review_record"].assert_not_called()
    mocks["fetch_diff_since"].assert_not_called()
    initial_state = mocks["graph_ainvoke"].call_args.args[0]
    assert initial_state["pr"].diff == "full-pr-diff"
    assert result.incremental is False
    assert result.cached is False


async def test_review_pr_saves_review_record_after_completion() -> None:
    pr = _make_pr(head_sha="the-new-head-sha")
    mocks = _make_patches(pr, _make_context())

    with _apply(mocks):
        await review_pr("owner", "repo", 7)

    mocks["save_review_record"].assert_called_once()
    args = mocks["save_review_record"].call_args.args
    assert args[0] == "owner"
    assert args[1] == "repo"
    assert args[2] == 7
    saved_record = args[3]
    assert isinstance(saved_record, ReviewRecord)
    assert saved_record.head_sha == "the-new-head-sha"
    assert saved_record.verdict == _VALID_FINAL_VERDICT.verdict
    assert saved_record.summary == _VALID_FINAL_VERDICT.summary
    assert saved_record.security_result.summary == _SECURITY_RESULT.summary
