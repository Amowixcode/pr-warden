from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from core.ingest_service import IngestResult, ingest_repository

_PATCH = "core.ingest_service.{}"


def _make_patches(
    *,
    n_issues: int = 2,
    n_prs: int = 3,
    n_commits: int = 5,
    index_issues: int = 2,
    index_prs: int = 3,
    index_commits: int = 5,
):
    """Return a dict of patch kwargs for the full ingest_repository surface."""
    return {
        "fetch_issues": AsyncMock(return_value=[MagicMock()] * n_issues),
        "fetch_merged_prs": AsyncMock(return_value=[MagicMock()] * n_prs),
        "fetch_recent_commits": AsyncMock(return_value=[MagicMock()] * n_commits),
        "issues_to_documents": MagicMock(return_value=[MagicMock()] * n_issues),
        "merged_prs_to_documents": MagicMock(return_value=[MagicMock()] * n_prs),
        "commits_to_documents": MagicMock(return_value=[MagicMock()] * n_commits),
        "build_chroma_collection": MagicMock(return_value=MagicMock()),
        "get_embed_model": MagicMock(return_value=MagicMock()),
        "build_vector_store_index": MagicMock(return_value=MagicMock()),
        "index_documents": AsyncMock(side_effect=[index_issues, index_prs, index_commits]),
        "GitHubClient": MagicMock(),
    }


async def test_ingest_repository_returns_correct_counts() -> None:
    mocks = _make_patches(index_issues=2, index_prs=3, index_commits=5)

    with (
        patch(_PATCH.format("fetch_issues"), mocks["fetch_issues"]),
        patch(_PATCH.format("fetch_merged_prs"), mocks["fetch_merged_prs"]),
        patch(_PATCH.format("fetch_recent_commits"), mocks["fetch_recent_commits"]),
        patch(_PATCH.format("issues_to_documents"), mocks["issues_to_documents"]),
        patch(_PATCH.format("merged_prs_to_documents"), mocks["merged_prs_to_documents"]),
        patch(_PATCH.format("commits_to_documents"), mocks["commits_to_documents"]),
        patch(_PATCH.format("build_chroma_collection"), mocks["build_chroma_collection"]),
        patch(_PATCH.format("get_embed_model"), mocks["get_embed_model"]),
        patch(_PATCH.format("build_vector_store_index"), mocks["build_vector_store_index"]),
        patch(_PATCH.format("index_documents"), mocks["index_documents"]),
        patch(_PATCH.format("GitHubClient"), mocks["GitHubClient"]),
    ):
        result = await ingest_repository("owner", "repo")

    assert isinstance(result, IngestResult)
    assert result.issues_indexed == 2
    assert result.prs_indexed == 3
    assert result.commits_indexed == 5
    assert result.total_newly_indexed == 10


async def test_ingest_repository_empty_repo() -> None:
    mocks = _make_patches(n_issues=0, n_prs=0, n_commits=0, index_issues=0, index_prs=0, index_commits=0)

    with (
        patch(_PATCH.format("fetch_issues"), mocks["fetch_issues"]),
        patch(_PATCH.format("fetch_merged_prs"), mocks["fetch_merged_prs"]),
        patch(_PATCH.format("fetch_recent_commits"), mocks["fetch_recent_commits"]),
        patch(_PATCH.format("issues_to_documents"), mocks["issues_to_documents"]),
        patch(_PATCH.format("merged_prs_to_documents"), mocks["merged_prs_to_documents"]),
        patch(_PATCH.format("commits_to_documents"), mocks["commits_to_documents"]),
        patch(_PATCH.format("build_chroma_collection"), mocks["build_chroma_collection"]),
        patch(_PATCH.format("get_embed_model"), mocks["get_embed_model"]),
        patch(_PATCH.format("build_vector_store_index"), mocks["build_vector_store_index"]),
        patch(_PATCH.format("index_documents"), mocks["index_documents"]),
        patch(_PATCH.format("GitHubClient"), mocks["GitHubClient"]),
    ):
        result = await ingest_repository("owner", "repo")

    assert result == IngestResult(0, 0, 0, 0)


async def test_ingest_repository_partial_deduplication() -> None:
    # Repo has data but some already indexed — counts reflect only newly indexed.
    mocks = _make_patches(n_issues=5, n_prs=4, n_commits=10, index_issues=1, index_prs=0, index_commits=3)

    with (
        patch(_PATCH.format("fetch_issues"), mocks["fetch_issues"]),
        patch(_PATCH.format("fetch_merged_prs"), mocks["fetch_merged_prs"]),
        patch(_PATCH.format("fetch_recent_commits"), mocks["fetch_recent_commits"]),
        patch(_PATCH.format("issues_to_documents"), mocks["issues_to_documents"]),
        patch(_PATCH.format("merged_prs_to_documents"), mocks["merged_prs_to_documents"]),
        patch(_PATCH.format("commits_to_documents"), mocks["commits_to_documents"]),
        patch(_PATCH.format("build_chroma_collection"), mocks["build_chroma_collection"]),
        patch(_PATCH.format("get_embed_model"), mocks["get_embed_model"]),
        patch(_PATCH.format("build_vector_store_index"), mocks["build_vector_store_index"]),
        patch(_PATCH.format("index_documents"), mocks["index_documents"]),
        patch(_PATCH.format("GitHubClient"), mocks["GitHubClient"]),
    ):
        result = await ingest_repository("owner", "repo")

    assert result.issues_indexed == 1
    assert result.prs_indexed == 0
    assert result.commits_indexed == 3
    assert result.total_newly_indexed == 4


async def test_ingest_repository_fetches_in_parallel() -> None:
    """All three GitHub fetches must be gathered concurrently."""
    call_order: list[str] = []

    async def _fetch_issues(*_a, **_kw):
        call_order.append("issues")
        return []

    async def _fetch_prs(*_a, **_kw):
        call_order.append("prs")
        return []

    async def _fetch_commits(*_a, **_kw):
        call_order.append("commits")
        return []

    mocks = _make_patches(n_issues=0, n_prs=0, n_commits=0, index_issues=0, index_prs=0, index_commits=0)

    with (
        patch(_PATCH.format("fetch_issues"), side_effect=_fetch_issues),
        patch(_PATCH.format("fetch_merged_prs"), side_effect=_fetch_prs),
        patch(_PATCH.format("fetch_recent_commits"), side_effect=_fetch_commits),
        patch(_PATCH.format("issues_to_documents"), mocks["issues_to_documents"]),
        patch(_PATCH.format("merged_prs_to_documents"), mocks["merged_prs_to_documents"]),
        patch(_PATCH.format("commits_to_documents"), mocks["commits_to_documents"]),
        patch(_PATCH.format("build_chroma_collection"), mocks["build_chroma_collection"]),
        patch(_PATCH.format("get_embed_model"), mocks["get_embed_model"]),
        patch(_PATCH.format("build_vector_store_index"), mocks["build_vector_store_index"]),
        patch(_PATCH.format("index_documents"), mocks["index_documents"]),
        patch(_PATCH.format("GitHubClient"), mocks["GitHubClient"]),
    ):
        await ingest_repository("owner", "repo")

    assert set(call_order) == {"issues", "prs", "commits"}


async def test_ingest_repository_uses_owner_repo_in_documents() -> None:
    mocks = _make_patches()

    with (
        patch(_PATCH.format("fetch_issues"), mocks["fetch_issues"]),
        patch(_PATCH.format("fetch_merged_prs"), mocks["fetch_merged_prs"]),
        patch(_PATCH.format("fetch_recent_commits"), mocks["fetch_recent_commits"]),
        patch(_PATCH.format("issues_to_documents"), mocks["issues_to_documents"]),
        patch(_PATCH.format("merged_prs_to_documents"), mocks["merged_prs_to_documents"]),
        patch(_PATCH.format("commits_to_documents"), mocks["commits_to_documents"]),
        patch(_PATCH.format("build_chroma_collection"), mocks["build_chroma_collection"]),
        patch(_PATCH.format("get_embed_model"), mocks["get_embed_model"]),
        patch(_PATCH.format("build_vector_store_index"), mocks["build_vector_store_index"]),
        patch(_PATCH.format("index_documents"), mocks["index_documents"]),
        patch(_PATCH.format("GitHubClient"), mocks["GitHubClient"]),
    ):
        await ingest_repository("myorg", "myrepo")

    mocks["issues_to_documents"].assert_called_once_with(
        mocks["fetch_issues"].return_value, "myorg", "myrepo"
    )
    mocks["merged_prs_to_documents"].assert_called_once_with(
        mocks["fetch_merged_prs"].return_value, "myorg", "myrepo"
    )
    mocks["commits_to_documents"].assert_called_once_with(
        mocks["fetch_recent_commits"].return_value, "myorg", "myrepo"
    )
