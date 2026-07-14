from __future__ import annotations

from contextlib import ExitStack
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from core.ingest_history import IngestRecord
from core.ingest_service import IngestResult, ingest_repository

_PATCH = "core.ingest_service.{}"
_NOW = datetime(2024, 6, 1, tzinfo=UTC)

_PATCH_TARGETS = {
    "fetch_issues": "fetch_issues",
    "fetch_merged_prs": "fetch_merged_prs",
    "fetch_recent_commits": "fetch_recent_commits",
    "issues_to_documents": "issues_to_documents",
    "merged_prs_to_documents": "merged_prs_to_documents",
    "commits_to_documents": "commits_to_documents",
    "build_chroma_collection": "build_chroma_collection",
    "get_embed_model": "get_embed_model",
    "build_vector_store_index": "build_vector_store_index",
    "index_documents": "index_documents",
    "load_ingest_record": "load_ingest_record",
    "save_ingest_record": "save_ingest_record",
    "GitHubClient": "GitHubClient",
}

# core.supabase_history.save_ingest lives outside core.ingest_service's own module, so it can't
# use the _PATCH.format() shorthand above — mocked separately in _apply() below. Without this,
# ingest_repository()'s real supabase_history.save_ingest call would fire against a real
# Supabase project whenever SUPABASE_URL/SUPABASE_KEY happen to be set in the environment
# running these "unit" tests.
_SUPABASE_SAVE_INGEST_TARGET = "core.supabase_history.save_ingest"


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
        "load_ingest_record": MagicMock(return_value=None),
        "save_ingest_record": MagicMock(),
        "GitHubClient": MagicMock(),
        "save_ingest_to_supabase": MagicMock(),
    }


def _apply(mocks: dict) -> ExitStack:
    """Enter every mocked dependency's patch as one combined context manager.

    Mirrors tests/unit/test_review_service.py's _apply() — collapses what would otherwise be
    13 separately-listed patch() context managers per test into one `with _apply(mocks):`.
    """
    stack = ExitStack()
    for key, target in _PATCH_TARGETS.items():
        stack.enter_context(patch(_PATCH.format(target), mocks[key]))
    stack.enter_context(patch(_SUPABASE_SAVE_INGEST_TARGET, mocks["save_ingest_to_supabase"]))
    return stack


async def test_ingest_repository_returns_correct_counts() -> None:
    mocks = _make_patches(index_issues=2, index_prs=3, index_commits=5)

    with _apply(mocks):
        result = await ingest_repository("owner", "repo")

    assert isinstance(result, IngestResult)
    assert result.issues_indexed == 2
    assert result.prs_indexed == 3
    assert result.commits_indexed == 5
    assert result.total_newly_indexed == 10


async def test_ingest_repository_empty_repo() -> None:
    mocks = _make_patches(
        n_issues=0, n_prs=0, n_commits=0, index_issues=0, index_prs=0, index_commits=0
    )

    with _apply(mocks):
        result = await ingest_repository("owner", "repo")

    assert result.issues_indexed == 0
    assert result.prs_indexed == 0
    assert result.commits_indexed == 0
    assert result.total_newly_indexed == 0


async def test_ingest_repository_partial_deduplication() -> None:
    # Repo has data but some already indexed — counts reflect only newly indexed.
    mocks = _make_patches(
        n_issues=5, n_prs=4, n_commits=10, index_issues=1, index_prs=0, index_commits=3
    )

    with _apply(mocks):
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

    mocks = _make_patches(
        n_issues=0, n_prs=0, n_commits=0, index_issues=0, index_prs=0, index_commits=0
    )
    mocks["fetch_issues"] = AsyncMock(side_effect=_fetch_issues)
    mocks["fetch_merged_prs"] = AsyncMock(side_effect=_fetch_prs)
    mocks["fetch_recent_commits"] = AsyncMock(side_effect=_fetch_commits)

    with _apply(mocks):
        await ingest_repository("owner", "repo")

    assert set(call_order) == {"issues", "prs", "commits"}


async def test_ingest_repository_uses_owner_repo_in_documents() -> None:
    mocks = _make_patches()

    with _apply(mocks):
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


# ── incremental ingest ───────────────────────────────────────────────────────


async def test_ingest_repository_first_ingest_is_full() -> None:
    """No prior record: since=None reaches all three fetchers, not marked incremental."""
    mocks = _make_patches()
    mocks["load_ingest_record"] = MagicMock(return_value=None)

    with _apply(mocks):
        result = await ingest_repository("owner", "repo")

    assert mocks["fetch_issues"].call_args.kwargs["since"] is None
    assert mocks["fetch_merged_prs"].call_args.kwargs["since"] is None
    assert mocks["fetch_recent_commits"].call_args.kwargs["since"] is None
    assert result.incremental is False
    mocks["save_ingest_record"].assert_called_once()


async def test_ingest_repository_second_ingest_is_incremental() -> None:
    """A prior record: its last_ingested_at reaches all three fetchers as since=, and the
    result is marked incremental.
    """
    prior = IngestRecord(last_ingested_at=_NOW)
    mocks = _make_patches()
    mocks["load_ingest_record"] = MagicMock(return_value=prior)

    with _apply(mocks):
        result = await ingest_repository("owner", "repo")

    assert mocks["fetch_issues"].call_args.kwargs["since"] == _NOW
    assert mocks["fetch_merged_prs"].call_args.kwargs["since"] == _NOW
    assert mocks["fetch_recent_commits"].call_args.kwargs["since"] == _NOW
    assert result.incremental is True


async def test_ingest_repository_full_flag_ignores_history() -> None:
    """full=True: load_ingest_record is never even called, so history can't influence the
    fetch regardless of what it would have returned.
    """
    mocks = _make_patches()
    mocks["load_ingest_record"] = MagicMock(
        return_value=IngestRecord(last_ingested_at=_NOW)
    )  # would be used if consulted

    with _apply(mocks):
        result = await ingest_repository("owner", "repo", full=True)

    mocks["load_ingest_record"].assert_not_called()
    assert mocks["fetch_issues"].call_args.kwargs["since"] is None
    assert mocks["fetch_merged_prs"].call_args.kwargs["since"] is None
    assert mocks["fetch_recent_commits"].call_args.kwargs["since"] is None
    assert result.incremental is False


async def test_ingest_repository_saves_record_after_completion() -> None:
    mocks = _make_patches()

    with _apply(mocks):
        await ingest_repository("owner", "repo")

    mocks["save_ingest_record"].assert_called_once()
    args = mocks["save_ingest_record"].call_args.args
    assert args[0] == "owner"
    assert args[1] == "repo"
    saved_record = args[2]
    assert isinstance(saved_record, IngestRecord)
    assert isinstance(saved_record.last_ingested_at, datetime)
