from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from core.pr_service import OpenPR, list_open_prs
from gh.pr_fetcher import OpenPRData

_PATCH = "core.pr_service.{}"


def _open_pr_data(number: int, title: str, author: str, days_old: int) -> OpenPRData:
    created_at = datetime.now(UTC) - timedelta(days=days_old, hours=1)
    return OpenPRData(number=number, title=title, author=author, created_at=created_at)


async def test_list_open_prs_computes_age_days() -> None:
    mocks = {
        "fetch_open_prs": AsyncMock(return_value=[_open_pr_data(1, "Fix bug", "alice", 3)]),
        "GitHubClient": MagicMock(),
    }
    with (
        patch(_PATCH.format("fetch_open_prs"), mocks["fetch_open_prs"]),
        patch(_PATCH.format("GitHubClient"), mocks["GitHubClient"]),
    ):
        result = await list_open_prs("owner", "repo")

    assert len(result) == 1
    assert isinstance(result[0], OpenPR)
    assert result[0].number == 1
    assert result[0].title == "Fix bug"
    assert result[0].author == "alice"
    assert result[0].age_days == 3


async def test_list_open_prs_passes_owner_repo_through() -> None:
    mocks = {
        "fetch_open_prs": AsyncMock(return_value=[]),
        "GitHubClient": MagicMock(),
    }
    with (
        patch(_PATCH.format("fetch_open_prs"), mocks["fetch_open_prs"]),
        patch(_PATCH.format("GitHubClient"), mocks["GitHubClient"]),
    ):
        await list_open_prs("octocat", "Hello-World")

    mocks["fetch_open_prs"].assert_awaited_once_with(
        mocks["GitHubClient"].return_value, "octocat", "Hello-World"
    )


async def test_list_open_prs_no_open_prs_returns_empty() -> None:
    mocks = {
        "fetch_open_prs": AsyncMock(return_value=[]),
        "GitHubClient": MagicMock(),
    }
    with (
        patch(_PATCH.format("fetch_open_prs"), mocks["fetch_open_prs"]),
        patch(_PATCH.format("GitHubClient"), mocks["GitHubClient"]),
    ):
        result = await list_open_prs("owner", "repo")

    assert result == []
