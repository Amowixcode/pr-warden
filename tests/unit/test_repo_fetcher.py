from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from gh.client import GitHubClient
from gh.repo_fetcher import (
    CommitData,
    IssueData,
    MergedPRData,
    fetch_issues,
    fetch_merged_prs,
    fetch_recent_commits,
)

_NOW = datetime(2024, 6, 1, 12, 0, 0)
_THEN = datetime(2024, 5, 1, 12, 0, 0)


# ---------------------------------------------------------------------------
# Mock builders
# ---------------------------------------------------------------------------


def _make_mock_issue(
    number: int = 1,
    title: str = "Bug: thing is broken",
    body: str | None = "Steps to reproduce...",
    state: str = "open",
    labels: list[str] | None = None,
    is_pr: bool = False,
) -> MagicMock:
    issue = MagicMock()
    issue.number = number
    issue.title = title
    issue.body = body
    issue.state = state
    label_mocks = []
    for label_name in labels or ["bug"]:
        lm = MagicMock()
        lm.name = label_name
        label_mocks.append(lm)
    issue.labels = label_mocks
    issue.user.login = "reporter"
    issue.created_at = _THEN
    issue.updated_at = _NOW
    issue.closed_at = None
    issue.pull_request = MagicMock() if is_pr else None
    return issue


def _make_mock_pr(
    number: int = 10,
    title: str = "Add feature X",
    body: str | None = "This PR adds...",
    merged: bool = True,
    updated_at: datetime = _NOW,
) -> MagicMock:
    pr = MagicMock()
    pr.number = number
    pr.title = title
    pr.body = body
    pr.user.login = "developer"
    pr.base.ref = "main"
    pr.head.ref = "feature/x"
    pr.merged_at = _NOW if merged else None
    pr.updated_at = updated_at
    return pr


def _make_mock_commit(
    sha: str = "abc123",
    message: str = "Fix null pointer exception",
    author: str = "Dev Name",
) -> MagicMock:
    commit = MagicMock()
    commit.sha = sha
    commit.commit.message = message
    commit.commit.author.name = author
    commit.commit.author.date = _NOW
    commit.html_url = f"https://github.com/owner/repo/commit/{sha}"
    return commit


def _make_mock_client(items: list[MagicMock], method: str = "get_issues") -> MagicMock:
    repo = MagicMock()
    getattr(repo, method).return_value = iter(items)
    client = MagicMock(spec=GitHubClient)
    client.get_repo.return_value = repo
    return client


# ---------------------------------------------------------------------------
# fetch_issues
# ---------------------------------------------------------------------------


async def test_fetch_issues_returns_correct_data() -> None:
    pure_issue = _make_mock_issue(number=1, is_pr=False)
    pr_issue = _make_mock_issue(number=2, is_pr=True)
    mock_client = _make_mock_client([pure_issue, pr_issue], method="get_issues")

    results = await fetch_issues(mock_client, "owner", "repo")

    assert len(results) == 1
    issue = results[0]
    assert isinstance(issue, IssueData)
    assert issue.number == 1
    assert issue.title == "Bug: thing is broken"
    assert issue.body == "Steps to reproduce..."
    assert issue.state == "open"
    assert issue.labels == ["bug"]
    assert issue.author == "reporter"
    assert issue.created_at == _THEN
    assert issue.updated_at == _NOW
    assert issue.closed_at is None


async def test_fetch_issues_none_body_coerced() -> None:
    issue = _make_mock_issue(body=None)
    mock_client = _make_mock_client([issue], method="get_issues")

    results = await fetch_issues(mock_client, "o", "r")

    assert results[0].body == ""


async def test_fetch_issues_forwards_since_kwarg() -> None:
    mock_client = _make_mock_client([], method="get_issues")

    await fetch_issues(mock_client, "o", "r", since=_THEN)

    kwargs = mock_client.get_repo.return_value.get_issues.call_args.kwargs
    assert kwargs["since"] == _THEN


async def test_fetch_issues_omits_since_kwarg_by_default() -> None:
    mock_client = _make_mock_client([], method="get_issues")

    await fetch_issues(mock_client, "o", "r")

    kwargs = mock_client.get_repo.return_value.get_issues.call_args.kwargs
    assert "since" not in kwargs


# ---------------------------------------------------------------------------
# fetch_merged_prs
# ---------------------------------------------------------------------------


async def test_fetch_merged_prs_returns_correct_data() -> None:
    merged_pr = _make_mock_pr(number=10, merged=True)
    unmerged_pr = _make_mock_pr(number=11, merged=False)
    mock_client = _make_mock_client([merged_pr, unmerged_pr], method="get_pulls")

    results = await fetch_merged_prs(mock_client, "owner", "repo")

    assert len(results) == 1
    pr = results[0]
    assert isinstance(pr, MergedPRData)
    assert pr.number == 10
    assert pr.title == "Add feature X"
    assert pr.body == "This PR adds..."
    assert pr.author == "developer"
    assert pr.base_branch == "main"
    assert pr.head_branch == "feature/x"
    assert pr.merged_at == _NOW


async def test_fetch_merged_prs_none_body_coerced() -> None:
    pr = _make_mock_pr(body=None, merged=True)
    mock_client = _make_mock_client([pr], method="get_pulls")

    results = await fetch_merged_prs(mock_client, "o", "r")

    assert results[0].body == ""


async def test_fetch_merged_prs_default_sort_is_created() -> None:
    mock_client = _make_mock_client([], method="get_pulls")

    await fetch_merged_prs(mock_client, "o", "r")

    kwargs = mock_client.get_repo.return_value.get_pulls.call_args.kwargs
    assert kwargs["sort"] == "created"


async def test_fetch_merged_prs_uses_updated_sort_when_since_given() -> None:
    mock_client = _make_mock_client([], method="get_pulls")

    await fetch_merged_prs(mock_client, "o", "r", since=_THEN)

    kwargs = mock_client.get_repo.return_value.get_pulls.call_args.kwargs
    assert kwargs["sort"] == "updated"


async def test_fetch_merged_prs_stops_at_since_cutoff() -> None:
    cutoff = datetime(2024, 6, 1, 12, 0, 0)
    recent = _make_mock_pr(number=20, merged=True, updated_at=datetime(2024, 6, 2, 12, 0, 0))
    old = _make_mock_pr(number=10, merged=True, updated_at=datetime(2024, 5, 1, 12, 0, 0))
    # Sorted updated-desc, as the real API would return when sort="updated".
    mock_client = _make_mock_client([recent, old], method="get_pulls")

    results = await fetch_merged_prs(mock_client, "o", "r", since=cutoff)

    assert [pr.number for pr in results] == [20]


# ---------------------------------------------------------------------------
# fetch_recent_commits
# ---------------------------------------------------------------------------


async def test_fetch_recent_commits_returns_correct_data() -> None:
    commit = _make_mock_commit()
    mock_client = _make_mock_client([commit], method="get_commits")

    results = await fetch_recent_commits(mock_client, "owner", "repo")

    assert len(results) == 1
    c = results[0]
    assert isinstance(c, CommitData)
    assert c.sha == "abc123"
    assert c.message == "Fix null pointer exception"
    assert c.author == "Dev Name"
    assert c.committed_at == _NOW
    assert c.url == "https://github.com/owner/repo/commit/abc123"


async def test_fetch_recent_commits_respects_limit() -> None:
    commits = [_make_mock_commit(sha=str(i)) for i in range(10)]
    mock_client = _make_mock_client(commits, method="get_commits")

    results = await fetch_recent_commits(mock_client, "o", "r", limit=3)

    assert len(results) == 3
    assert [c.sha for c in results] == ["0", "1", "2"]


async def test_fetch_recent_commits_forwards_since_kwarg() -> None:
    mock_client = _make_mock_client([], method="get_commits")

    await fetch_recent_commits(mock_client, "o", "r", since=_THEN)

    kwargs = mock_client.get_repo.return_value.get_commits.call_args.kwargs
    assert kwargs["since"] == _THEN


async def test_fetch_recent_commits_omits_since_kwarg_by_default() -> None:
    mock_client = _make_mock_client([], method="get_commits")

    await fetch_recent_commits(mock_client, "o", "r")

    kwargs = mock_client.get_repo.return_value.get_commits.call_args.kwargs
    assert "since" not in kwargs
