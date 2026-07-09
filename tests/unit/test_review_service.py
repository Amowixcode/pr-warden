from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from llama_index.core.schema import NodeWithScore, TextNode

from agents.state import AgentResult
from core.review_service import ReviewResult, review_pr
from gh.pr_fetcher import PRData
from retrieval.context_builder import PRContext

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


def _make_patches(
    pr: PRData, context: PRContext, final_verdict: AgentResult = _VALID_FINAL_VERDICT
) -> dict:
    return {
        "fetch_pull_request": AsyncMock(return_value=pr),
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
    }


def _apply(mocks: dict):
    return (
        patch(_PATCH.format("fetch_pull_request"), mocks["fetch_pull_request"]),
        patch(_PATCH.format("build_pr_context"), mocks["build_pr_context"]),
        patch(_PATCH.format("build_chroma_collection"), mocks["build_chroma_collection"]),
        patch(_PATCH.format("build_vector_store_index"), mocks["build_vector_store_index"]),
        patch(_PATCH.format("get_embed_model"), mocks["get_embed_model"]),
        patch(_PATCH.format("graph.ainvoke"), mocks["graph_ainvoke"]),
        patch(_PATCH.format("GitHubClient"), mocks["GitHubClient"]),
    )


# ── review_pr orchestration ──────────────────────────────────────────────────


async def test_review_pr_returns_review_result() -> None:
    pr = _make_pr()
    mocks = _make_patches(pr, _make_context())

    with (
        _apply(mocks)[0],
        _apply(mocks)[1],
        _apply(mocks)[2],
        _apply(mocks)[3],
        _apply(mocks)[4],
        _apply(mocks)[5],
        _apply(mocks)[6],
    ):
        result = await review_pr("owner", "repo", 7)

    assert isinstance(result, ReviewResult)


async def test_review_pr_pr_number_matches_input() -> None:
    pr = _make_pr(number=42)
    mocks = _make_patches(pr, _make_context())

    with (
        _apply(mocks)[0],
        _apply(mocks)[1],
        _apply(mocks)[2],
        _apply(mocks)[3],
        _apply(mocks)[4],
        _apply(mocks)[5],
        _apply(mocks)[6],
    ):
        result = await review_pr("owner", "repo", 42)

    assert result.pr_number == 42


async def test_review_pr_fields_from_final_verdict() -> None:
    pr = _make_pr()
    mocks = _make_patches(pr, _make_context())

    with (
        _apply(mocks)[0],
        _apply(mocks)[1],
        _apply(mocks)[2],
        _apply(mocks)[3],
        _apply(mocks)[4],
        _apply(mocks)[5],
        _apply(mocks)[6],
    ):
        result = await review_pr("owner", "repo", 7)

    assert result.summary == "Looks good overall."
    assert result.verdict == "APPROVE"
    assert result.issues == ["Missing type hint on line 5"]
    assert result.suggestions == ["Add a docstring"]


async def test_review_pr_passes_pr_to_graph() -> None:
    pr = _make_pr(title="Unique PR title XYZ", diff="unique-diff-marker-abc123")
    mocks = _make_patches(pr, _make_context())

    with (
        _apply(mocks)[0],
        _apply(mocks)[1],
        _apply(mocks)[2],
        _apply(mocks)[3],
        _apply(mocks)[4],
        _apply(mocks)[5],
        _apply(mocks)[6],
    ):
        await review_pr("owner", "repo", 7)

    initial_state = mocks["graph_ainvoke"].call_args.args[0]
    assert initial_state["pr"].title == "Unique PR title XYZ"
    assert initial_state["pr"].diff == "unique-diff-marker-abc123"


async def test_review_pr_passes_context_to_graph() -> None:
    pr = _make_pr()
    context = _make_context(issues=["Login fails on Safari"])
    mocks = _make_patches(pr, context)

    with (
        _apply(mocks)[0],
        _apply(mocks)[1],
        _apply(mocks)[2],
        _apply(mocks)[3],
        _apply(mocks)[4],
        _apply(mocks)[5],
        _apply(mocks)[6],
    ):
        await review_pr("owner", "repo", 7)

    initial_state = mocks["graph_ainvoke"].call_args.args[0]
    assert initial_state["context"] is context


async def test_review_pr_carries_per_agent_results_through() -> None:
    pr = _make_pr()
    mocks = _make_patches(pr, _make_context())

    with (
        _apply(mocks)[0],
        _apply(mocks)[1],
        _apply(mocks)[2],
        _apply(mocks)[3],
        _apply(mocks)[4],
        _apply(mocks)[5],
        _apply(mocks)[6],
    ):
        result = await review_pr("owner", "repo", 7)

    assert result.security_result == _SECURITY_RESULT
    assert result.quality_result == _QUALITY_RESULT
    assert result.test_result == _TEST_RESULT


async def test_review_pr_initial_state_has_no_agent_results_yet() -> None:
    pr = _make_pr()
    mocks = _make_patches(pr, _make_context())

    with (
        _apply(mocks)[0],
        _apply(mocks)[1],
        _apply(mocks)[2],
        _apply(mocks)[3],
        _apply(mocks)[4],
        _apply(mocks)[5],
        _apply(mocks)[6],
    ):
        await review_pr("owner", "repo", 7)

    initial_state = mocks["graph_ainvoke"].call_args.args[0]
    assert initial_state["security_result"] is None
    assert initial_state["quality_result"] is None
    assert initial_state["test_result"] is None
    assert initial_state["final_verdict"] is None
