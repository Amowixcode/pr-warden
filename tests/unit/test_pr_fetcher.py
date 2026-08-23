from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from github import GithubException

from gh.client import GitHubClient
from gh.pr_fetcher import (
    OpenPRData,
    PRData,
    PRFile,
    fetch_diff_since,
    fetch_linked_issues,
    fetch_open_prs,
    fetch_pull_request,
    parse_linked_issue_numbers,
)
from gh.repo_fetcher import IssueData

_CREATED = datetime(2024, 1, 1, 12, 0, 0)
_UPDATED = datetime(2024, 1, 2, 12, 0, 0)


# ---------------------------------------------------------------------------
# Mock builders
# ---------------------------------------------------------------------------


def _make_mock_file(
    filename: str = "src/main.py",
    status: str = "modified",
    additions: int = 10,
    deletions: int = 2,
    patch: str | None = "@@ -1,2 +1,3 @@\n context\n-old line\n+new line",
) -> MagicMock:
    f = MagicMock()
    f.filename = filename
    f.status = status
    f.additions = additions
    f.deletions = deletions
    f.patch = patch
    return f


def _make_mock_commit(
    sha: str = "abc123",
    message: str = "Fix null pointer exception",
    author: str = "Dev Name",
    committed_at: datetime = _CREATED,
) -> MagicMock:
    commit = MagicMock()
    commit.sha = sha
    commit.commit.message = message
    commit.commit.author.name = author
    commit.commit.author.date = committed_at
    commit.html_url = f"https://github.com/owner/repo/commit/{sha}"
    return commit


def _make_mock_issue(
    number: int = 1,
    title: str = "Bug: thing is broken",
    body: str | None = "Steps to reproduce...",
    state: str = "open",
    is_pr: bool = False,
) -> MagicMock:
    issue = MagicMock()
    issue.number = number
    issue.title = title
    issue.body = body
    issue.state = state
    label = MagicMock()
    label.name = "bug"
    issue.labels = [label]
    issue.user.login = "reporter"
    issue.created_at = _CREATED
    issue.updated_at = _UPDATED
    issue.closed_at = None
    issue.pull_request = MagicMock() if is_pr else None
    return issue


def _make_mock_pr(
    files: list[MagicMock],
    body: str | None = "Fixes the thing",
    commits: list[MagicMock] | None = None,
    head_sha: str = "headsha123",
) -> MagicMock:
    pr = MagicMock()
    pr.number = 42
    pr.title = "Fix the bug"
    pr.body = body
    pr.state = "open"
    pr.user.login = "johndoe"
    pr.base.ref = "main"
    pr.head.ref = "fix-the-bug"
    pr.head.sha = head_sha
    pr.created_at = _CREATED
    pr.updated_at = _UPDATED
    pr.get_files.return_value = files
    pr.get_commits.return_value = commits or []
    return pr


def _make_mock_client(mock_pr: MagicMock, mock_repo: MagicMock | None = None) -> MagicMock:
    repo = mock_repo or MagicMock()
    repo.get_pull.return_value = mock_pr
    client = MagicMock(spec=GitHubClient)
    client.get_repo.return_value = repo
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_fetch_pull_request_returns_correct_prdata() -> None:
    mock_file = _make_mock_file()
    mock_pr = _make_mock_pr(files=[mock_file])
    mock_client = _make_mock_client(mock_pr)

    result = await fetch_pull_request(mock_client, "owner", "repo", 42)

    assert isinstance(result, PRData)
    assert result.number == 42
    assert result.title == "Fix the bug"
    assert result.body == "Fixes the thing"
    assert result.state == "open"
    assert result.author == "johndoe"
    assert result.base_branch == "main"
    assert result.head_branch == "fix-the-bug"
    assert result.created_at == _CREATED
    assert result.updated_at == _UPDATED
    assert result.head_sha == "headsha123"
    assert len(result.changed_files) == 1

    pr_file = result.changed_files[0]
    assert isinstance(pr_file, PRFile)
    assert pr_file.filename == "src/main.py"
    assert pr_file.status == "modified"
    assert pr_file.additions == 10
    assert pr_file.deletions == 2
    assert pr_file.patch is not None

    assert "diff --git a/src/main.py b/src/main.py" in result.diff
    assert "@@ -1,2 +1,3 @@" in result.diff

    mock_client.get_repo.assert_called_once_with("owner", "repo")
    mock_client.get_repo.return_value.get_pull.assert_called_once_with(42)


async def test_none_body_coerces_to_empty_string() -> None:
    mock_pr = _make_mock_pr(files=[_make_mock_file()], body=None)
    result = await fetch_pull_request(_make_mock_client(mock_pr), "o", "r", 1)

    assert result.body == ""


async def test_binary_file_excluded_from_diff_but_present_in_changed_files() -> None:
    binary = _make_mock_file(
        filename="assets/logo.png",
        status="added",
        additions=0,
        deletions=0,
        patch=None,
    )
    text = _make_mock_file(
        filename="src/app.py",
        status="modified",
        additions=5,
        deletions=1,
        patch="@@ -1 +1,2 @@\n hello\n+world",
    )
    mock_pr = _make_mock_pr(files=[binary, text])
    result = await fetch_pull_request(_make_mock_client(mock_pr), "o", "r", 1)

    filenames = [f.filename for f in result.changed_files]
    assert len(result.changed_files) == 2
    assert "assets/logo.png" in filenames
    assert "src/app.py" in filenames

    assert "assets/logo.png" not in result.diff
    assert "diff --git a/src/app.py b/src/app.py" in result.diff


# ---------------------------------------------------------------------------
# commits
# ---------------------------------------------------------------------------


async def test_fetch_pull_request_includes_commits_of_varying_quality() -> None:
    detailed = _make_mock_commit(
        sha="aaa111",
        message="Fix null pointer when the cache is cold\n\nThe cache miss path never "
        "initialized the fallback value, causing a NullPointerException on first access.",
    )
    terse = _make_mock_commit(sha="bbb222", message="wip")
    mock_pr = _make_mock_pr(files=[_make_mock_file()], commits=[detailed, terse])

    result = await fetch_pull_request(_make_mock_client(mock_pr), "o", "r", 1)

    assert len(result.commits) == 2
    assert result.commits[0].sha == "aaa111"
    assert result.commits[0].message.startswith("Fix null pointer when the cache is cold")
    assert result.commits[1].sha == "bbb222"
    assert result.commits[1].message == "wip"


async def test_fetch_pull_request_no_commits() -> None:
    mock_pr = _make_mock_pr(files=[_make_mock_file()], commits=[])

    result = await fetch_pull_request(_make_mock_client(mock_pr), "o", "r", 1)

    assert result.commits == []


# ---------------------------------------------------------------------------
# parse_linked_issue_numbers
# ---------------------------------------------------------------------------


def test_parse_linked_issue_numbers_fixes() -> None:
    assert parse_linked_issue_numbers("Fixes #12") == [12]


def test_parse_linked_issue_numbers_closes_lowercase() -> None:
    assert parse_linked_issue_numbers("this closes #7 for good") == [7]


def test_parse_linked_issue_numbers_resolves_mixed_case() -> None:
    assert parse_linked_issue_numbers("ReSolVes #99") == [99]


def test_parse_linked_issue_numbers_multiple_references() -> None:
    assert parse_linked_issue_numbers("Fixes #1 and closes #2, Resolves #3") == [1, 2, 3]


def test_parse_linked_issue_numbers_deduplicates() -> None:
    assert parse_linked_issue_numbers("Fixes #5. Also fixes #5 again.") == [5]


def test_parse_linked_issue_numbers_no_match() -> None:
    assert parse_linked_issue_numbers("Just a regular PR description, see #5 for context") == []


def test_parse_linked_issue_numbers_empty_body() -> None:
    assert parse_linked_issue_numbers("") == []


# ---------------------------------------------------------------------------
# fetch_linked_issues
# ---------------------------------------------------------------------------


def _make_mock_client_with_repo(mock_repo: MagicMock) -> MagicMock:
    client = MagicMock(spec=GitHubClient)
    client.get_repo.return_value = mock_repo
    return client


async def test_fetch_linked_issues_found_and_fetchable() -> None:
    mock_repo = MagicMock()
    mock_repo.get_issue.return_value = _make_mock_issue(number=27670, title="Crash on mount")
    client = _make_mock_client_with_repo(mock_repo)

    results = await fetch_linked_issues(client, "o", "r", "Fixes #27670")

    assert len(results) == 1
    assert isinstance(results[0], IssueData)
    assert results[0].number == 27670
    assert results[0].title == "Crash on mount"
    mock_repo.get_issue.assert_called_once_with(27670)


async def test_fetch_linked_issues_no_linked_issue_skips_api_call() -> None:
    mock_repo = MagicMock()
    client = _make_mock_client_with_repo(mock_repo)

    results = await fetch_linked_issues(client, "o", "r", "Just a description, no linking")

    assert results == []
    client.get_repo.assert_not_called()
    mock_repo.get_issue.assert_not_called()


async def test_fetch_linked_issues_skips_unfetchable_issue() -> None:
    mock_repo = MagicMock()
    mock_repo.get_issue.side_effect = GithubException(404, {"message": "Not Found"}, None)
    client = _make_mock_client_with_repo(mock_repo)

    results = await fetch_linked_issues(client, "o", "r", "Fixes #999999")

    assert results == []


async def test_fetch_linked_issues_skips_number_that_is_actually_a_pr() -> None:
    mock_repo = MagicMock()
    mock_repo.get_issue.return_value = _make_mock_issue(number=10, is_pr=True)
    client = _make_mock_client_with_repo(mock_repo)

    results = await fetch_linked_issues(client, "o", "r", "Closes #10")

    assert results == []


async def test_fetch_linked_issues_fetches_all_referenced_numbers() -> None:
    mock_repo = MagicMock()
    mock_repo.get_issue.side_effect = [
        _make_mock_issue(number=1, title="First"),
        _make_mock_issue(number=2, title="Second"),
    ]
    client = _make_mock_client_with_repo(mock_repo)

    results = await fetch_linked_issues(client, "o", "r", "Fixes #1, Closes #2")

    assert [i.number for i in results] == [1, 2]


# ---------------------------------------------------------------------------
# fetch_diff_since
# ---------------------------------------------------------------------------


def _make_mock_comparison(files: list[MagicMock]) -> MagicMock:
    comparison = MagicMock()
    comparison.files = files
    return comparison


async def test_fetch_diff_since_maps_comparison_files_into_diff() -> None:
    changed = _make_mock_file(
        filename="src/new_thing.py",
        status="added",
        additions=3,
        deletions=0,
        patch="@@ -0,0 +1,3 @@\n+def new_thing():\n+    pass",
    )
    mock_repo = MagicMock()
    mock_repo.compare.return_value = _make_mock_comparison([changed])
    client = _make_mock_client_with_repo(mock_repo)

    result = await fetch_diff_since(client, "o", "r", "base-sha", "head-sha")

    assert "diff --git a/src/new_thing.py b/src/new_thing.py" in result
    assert "+def new_thing():" in result
    mock_repo.compare.assert_called_once_with("base-sha", "head-sha")


async def test_fetch_diff_since_empty_comparison_yields_empty_diff() -> None:
    mock_repo = MagicMock()
    mock_repo.compare.return_value = _make_mock_comparison([])
    client = _make_mock_client_with_repo(mock_repo)

    result = await fetch_diff_since(client, "o", "r", "same-sha", "same-sha")

    assert result == ""


# ---------------------------------------------------------------------------
# fetch_open_prs
# ---------------------------------------------------------------------------


def _make_mock_open_pr(number: int, title: str, author: str, created_at: datetime) -> MagicMock:
    pr = MagicMock()
    pr.number = number
    pr.title = title
    pr.user.login = author
    pr.created_at = created_at
    return pr


async def test_fetch_open_prs_maps_fields_correctly() -> None:
    mock_repo = MagicMock()
    mock_repo.get_pulls.return_value = [
        _make_mock_open_pr(12, "Add dark mode", "alice", _CREATED),
    ]
    client = _make_mock_client_with_repo(mock_repo)

    results = await fetch_open_prs(client, "o", "r")

    assert len(results) == 1
    assert isinstance(results[0], OpenPRData)
    assert results[0].number == 12
    assert results[0].title == "Add dark mode"
    assert results[0].author == "alice"
    assert results[0].created_at == _CREATED
    client.get_repo.assert_called_once_with("o", "r")
    mock_repo.get_pulls.assert_called_once_with(state="open", sort="created", direction="desc")


async def test_fetch_open_prs_respects_limit() -> None:
    mock_repo = MagicMock()
    mock_repo.get_pulls.return_value = [
        _make_mock_open_pr(n, f"PR {n}", "someone", _CREATED) for n in range(5)
    ]
    client = _make_mock_client_with_repo(mock_repo)

    results = await fetch_open_prs(client, "o", "r", limit=2)

    assert len(results) == 2


async def test_fetch_open_prs_no_open_prs() -> None:
    mock_repo = MagicMock()
    mock_repo.get_pulls.return_value = []
    client = _make_mock_client_with_repo(mock_repo)

    results = await fetch_open_prs(client, "o", "r")

    assert results == []
