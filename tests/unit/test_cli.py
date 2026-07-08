from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
import typer
from github import GithubException
from openai import OpenAIError
from typer.testing import CliRunner

from cli.main import _parse_repo, app
from core.ingest_service import IngestResult
from core.review_service import ReviewResult

runner = CliRunner()


def test_ingest_success(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=IngestResult(
            issues_indexed=3, prs_indexed=2, commits_indexed=10, total_newly_indexed=15
        )
    )
    monkeypatch.setattr("core.ingest_service.ingest_repository", mock)

    result = runner.invoke(app, ["ingest", "octocat/Hello-World"])

    assert result.exit_code == 0
    assert "Hello-World" in result.stdout
    assert "15" in result.stdout
    mock.assert_awaited_once_with("octocat", "Hello-World")


def test_review_approve_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=ReviewResult(
            pr_number=7,
            summary="Looks good",
            verdict="APPROVE",
            issues=[],
            suggestions=["Add tests"],
        )
    )
    monkeypatch.setattr("core.review_service.review_pr", mock)

    result = runner.invoke(app, ["review", "octocat/Hello-World", "7"])

    assert result.exit_code == 0
    assert "APPROVE" in result.stdout
    assert "Add tests" in result.stdout
    mock.assert_awaited_once_with("octocat", "Hello-World", 7)


def test_review_request_changes_lists_issues(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=ReviewResult(
            pr_number=9,
            summary="Needs work",
            verdict="REQUEST_CHANGES",
            issues=["bug A", "bug B"],
            suggestions=[],
        )
    )
    monkeypatch.setattr("core.review_service.review_pr", mock)

    result = runner.invoke(app, ["review", "octocat/Hello-World", "9"])

    assert result.exit_code == 0
    assert "REQUEST_CHANGES" in result.stdout
    assert "bug A" in result.stdout
    assert "bug B" in result.stdout


def test_invalid_repo_format_missing_slash() -> None:
    result = runner.invoke(app, ["ingest", "not-a-valid-repo"])

    assert result.exit_code == 2
    assert "owner/repo" in result.output


def test_ingest_github_exception_no_traceback(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(side_effect=GithubException(404, {"message": "Not Found"}, None))
    monkeypatch.setattr("core.ingest_service.ingest_repository", mock)

    result = runner.invoke(app, ["ingest", "octocat/Hello-World"])

    assert result.exit_code == 1
    assert "GitHub API error" in result.output
    assert "Traceback" not in result.output


def test_review_openai_exception_no_traceback(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(side_effect=OpenAIError("rate limited"))
    monkeypatch.setattr("core.review_service.review_pr", mock)

    result = runner.invoke(app, ["review", "octocat/Hello-World", "1"])

    assert result.exit_code == 1
    assert "OpenAI API error" in result.output
    assert "Traceback" not in result.output


def test_review_unexpected_exception_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr("core.review_service.review_pr", mock)

    result = runner.invoke(app, ["review", "octocat/Hello-World", "1"])

    assert result.exit_code == 1
    assert "unexpected error" in result.output
    assert "Traceback" not in result.output


def test_parse_repo_valid() -> None:
    assert _parse_repo("owner/repo") == ("owner", "repo")


@pytest.mark.parametrize("bad", ["noslash", "a/b/c", "/repo", "owner/"])
def test_parse_repo_invalid(bad: str) -> None:
    with pytest.raises(typer.BadParameter):
        _parse_repo(bad)
