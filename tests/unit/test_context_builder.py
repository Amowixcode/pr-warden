from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from llama_index.core import VectorStoreIndex
from llama_index.core.schema import NodeWithScore, TextNode

from gh.pr_fetcher import PRData
from gh.repo_fetcher import IssueData
from retrieval.context_builder import (
    PersistedAgentResult,
    PRContext,
    ReviewRecord,
    build_pr_context,
)

_PATCH = "retrieval.context_builder.retrieve"

_NOW = datetime(2024, 6, 1, tzinfo=UTC)


def _make_pr(title: str = "Fix bug", body: str = "Details here") -> PRData:
    return PRData(
        number=42,
        title=title,
        body=body,
        state="open",
        author="dev",
        base_branch="main",
        head_branch="fix/bug",
        created_at=_NOW,
        updated_at=_NOW,
        changed_files=[],
        diff="",
    )


def _make_node(text: str = "node") -> NodeWithScore:
    return NodeWithScore(node=TextNode(text=text), score=0.9)


def _make_issue(number: int = 1, title: str = "Linked bug") -> IssueData:
    return IssueData(
        number=number,
        title=title,
        body="Reproduction steps...",
        state="open",
        labels=["bug"],
        author="reporter",
        created_at=_NOW,
        updated_at=_NOW,
        closed_at=None,
    )


def _make_review_record(head_sha: str = "abc123") -> ReviewRecord:
    agent = PersistedAgentResult(summary="ok", verdict="APPROVE", issues=[], suggestions=[])
    return ReviewRecord(
        head_sha=head_sha,
        verdict="APPROVE",
        summary="Looks good",
        issues=[],
        suggestions=[],
        security_result=agent,
        quality_result=agent,
        test_result=agent,
        reviewed_at=_NOW,
    )


def _mock_retrieve(
    issues: list[NodeWithScore],
    prs: list[NodeWithScore],
    commits: list[NodeWithScore],
) -> AsyncMock:
    """Return an AsyncMock that yields different node lists per doc_type arg."""

    async def _side_effect(_index, _query, doc_type, *_args, **_kwargs):
        return {"issue": issues, "merged_pr": prs, "commit": commits}[doc_type]

    return AsyncMock(side_effect=_side_effect)


# ── happy path ───────────────────────────────────────────────────────────────


async def test_build_pr_context_returns_pr_context() -> None:
    mock_index = MagicMock(spec=VectorStoreIndex)
    issues = [_make_node("issue")]
    prs = [_make_node("pr")]
    commits = [_make_node("commit")]

    with patch(_PATCH, _mock_retrieve(issues, prs, commits)):
        result = await build_pr_context(_make_pr(), mock_index, "owner", "repo")

    assert isinstance(result, PRContext)
    assert result.similar_issues == issues
    assert result.similar_prs == prs
    assert result.related_commits == commits


async def test_build_pr_context_empty_index() -> None:
    mock_index = MagicMock(spec=VectorStoreIndex)

    with patch(_PATCH, _mock_retrieve([], [], [])):
        result = await build_pr_context(_make_pr(), mock_index, "owner", "repo")

    assert result == PRContext(similar_issues=[], similar_prs=[], related_commits=[])


# ── query text ───────────────────────────────────────────────────────────────


async def test_build_pr_context_query_text_from_pr() -> None:
    mock_index = MagicMock(spec=VectorStoreIndex)
    pr = _make_pr(title="Add feature", body="Implements X")
    mock_retrieve = _mock_retrieve([], [], [])

    with patch(_PATCH, mock_retrieve):
        await build_pr_context(pr, mock_index, "owner", "repo")

    query_texts = {c.args[1] for c in mock_retrieve.call_args_list}
    assert query_texts == {"Add feature\n\nImplements X"}


async def test_build_pr_context_empty_body_in_query() -> None:
    mock_index = MagicMock(spec=VectorStoreIndex)
    pr = _make_pr(title="Refactor", body="")
    mock_retrieve = _mock_retrieve([], [], [])

    with patch(_PATCH, mock_retrieve):
        await build_pr_context(pr, mock_index, "owner", "repo")

    query_texts = {c.args[1] for c in mock_retrieve.call_args_list}
    assert query_texts == {"Refactor\n\n"}


# ── doc types queried ────────────────────────────────────────────────────────


async def test_build_pr_context_queries_all_doc_types() -> None:
    mock_index = MagicMock(spec=VectorStoreIndex)
    mock_retrieve = _mock_retrieve([], [], [])

    with patch(_PATCH, mock_retrieve):
        await build_pr_context(_make_pr(), mock_index, "owner", "repo")

    doc_types = {c.args[2] for c in mock_retrieve.call_args_list}
    assert doc_types == {"issue", "merged_pr", "commit"}


# ── top_k propagation ────────────────────────────────────────────────────────


async def test_build_pr_context_top_k_default() -> None:
    mock_index = MagicMock(spec=VectorStoreIndex)
    mock_retrieve = _mock_retrieve([], [], [])

    with patch(_PATCH, mock_retrieve):
        await build_pr_context(_make_pr(), mock_index, "owner", "repo")

    top_k_values = {c.args[5] for c in mock_retrieve.call_args_list}
    assert top_k_values == {5}


async def test_build_pr_context_top_k_custom() -> None:
    mock_index = MagicMock(spec=VectorStoreIndex)
    mock_retrieve = _mock_retrieve([], [], [])

    with patch(_PATCH, mock_retrieve):
        await build_pr_context(_make_pr(), mock_index, "owner", "repo", top_k=2)

    top_k_values = {c.args[5] for c in mock_retrieve.call_args_list}
    assert top_k_values == {2}


# ── linked_issues passthrough ───────────────────────────────────────────────


async def test_build_pr_context_passes_through_linked_issues() -> None:
    mock_index = MagicMock(spec=VectorStoreIndex)
    issue = _make_issue(number=27670, title="Crash on mount")

    with patch(_PATCH, _mock_retrieve([], [], [])):
        result = await build_pr_context(
            _make_pr(), mock_index, "owner", "repo", linked_issues=[issue]
        )

    assert result.linked_issues == [issue]


async def test_build_pr_context_defaults_linked_issues_to_empty_list() -> None:
    mock_index = MagicMock(spec=VectorStoreIndex)

    with patch(_PATCH, _mock_retrieve([], [], [])):
        result = await build_pr_context(_make_pr(), mock_index, "owner", "repo")

    assert result.linked_issues == []


# ── prior_review passthrough ────────────────────────────────────────────────


async def test_build_pr_context_passes_through_prior_review() -> None:
    mock_index = MagicMock(spec=VectorStoreIndex)
    record = _make_review_record(head_sha="deadbeef")

    with patch(_PATCH, _mock_retrieve([], [], [])):
        result = await build_pr_context(
            _make_pr(), mock_index, "owner", "repo", prior_review=record
        )

    assert result.prior_review == record


async def test_build_pr_context_defaults_prior_review_to_none() -> None:
    mock_index = MagicMock(spec=VectorStoreIndex)

    with patch(_PATCH, _mock_retrieve([], [], [])):
        result = await build_pr_context(_make_pr(), mock_index, "owner", "repo")

    assert result.prior_review is None
