from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from gh.client import GitHubClient
from gh.pr_fetcher import PRData, PRFile, fetch_pull_request

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


def _make_mock_pr(
    files: list[MagicMock],
    body: str | None = "Fixes the thing",
) -> MagicMock:
    pr = MagicMock()
    pr.number = 42
    pr.title = "Fix the bug"
    pr.body = body
    pr.state = "open"
    pr.user.login = "johndoe"
    pr.base.ref = "main"
    pr.head.ref = "fix-the-bug"
    pr.created_at = _CREATED
    pr.updated_at = _UPDATED
    pr.get_files.return_value = files
    return pr


def _make_mock_client(mock_pr: MagicMock) -> MagicMock:
    mock_repo = MagicMock()
    mock_repo.get_pull.return_value = mock_pr
    client = MagicMock(spec=GitHubClient)
    client.get_repo.return_value = mock_repo
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
