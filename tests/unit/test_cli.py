from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
import typer
from github import GithubException
from openai import OpenAIError
from typer.testing import CliRunner

from agents.state import AgentResult
from cli.main import _parse_repo, _print_agent_section, app
from core.doctor_service import CheckResult, DoctorResult
from core.exceptions import VectorStoreError
from core.ingest_service import IngestResult
from core.review_service import ReviewResult

runner = CliRunner()


def _agent_result(
    verdict: str = "APPROVE",
    summary: str = "Looks fine",
    issues: list[str] | None = None,
    suggestions: list[str] | None = None,
) -> AgentResult:
    return AgentResult(
        summary=summary, verdict=verdict, issues=issues or [], suggestions=suggestions or []
    )


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
            security_result=_agent_result(),
            quality_result=_agent_result(),
            test_result=_agent_result(),
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
            security_result=_agent_result(),
            quality_result=_agent_result(),
            test_result=_agent_result(),
        )
    )
    monkeypatch.setattr("core.review_service.review_pr", mock)

    result = runner.invoke(app, ["review", "octocat/Hello-World", "9"])

    assert result.exit_code == 0
    assert "REQUEST_CHANGES" in result.stdout
    assert "bug A" in result.stdout
    assert "bug B" in result.stdout


def test_review_shows_per_agent_findings(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=ReviewResult(
            pr_number=7,
            summary="Overall needs work",
            verdict="REQUEST_CHANGES",
            issues=["Hardcoded secret", "Missing docstring", "No edge-case test"],
            suggestions=[],
            security_result=_agent_result(
                verdict="REQUEST_CHANGES",
                summary="Found a hardcoded secret",
                issues=["Hardcoded secret"],
            ),
            quality_result=_agent_result(
                verdict="COMMENT", summary="Missing a docstring", issues=["Missing docstring"]
            ),
            test_result=_agent_result(
                verdict="COMMENT",
                summary="No edge-case coverage",
                issues=["No edge-case test"],
            ),
        )
    )
    monkeypatch.setattr("core.review_service.review_pr", mock)

    result = runner.invoke(app, ["review", "octocat/Hello-World", "7"])

    assert result.exit_code == 0
    assert "Per-Agent Findings" in result.stdout
    assert "Security" in result.stdout
    assert "Quality" in result.stdout
    assert "Test Coverage" in result.stdout
    assert "Found a hardcoded secret" in result.stdout
    assert "Missing a docstring" in result.stdout
    assert "No edge-case coverage" in result.stdout
    assert "Final Verdict" in result.stdout


def test_print_agent_section_collapses_approve_with_no_issues(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = _agent_result(verdict="APPROVE", summary="No concerns found.", issues=[])

    _print_agent_section("Security", result)

    captured = capsys.readouterr().out
    assert "APPROVE" in captured
    assert "No concerns found." in captured
    assert "Issues" not in captured
    assert "Suggestions" not in captured
    assert "No issues found." not in captured
    assert "No suggestions." not in captured


def test_print_agent_section_shows_full_panel_when_verdict_not_approve(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = _agent_result(verdict="COMMENT", summary="A minor note.", issues=[])

    _print_agent_section("Quality", result)

    captured = capsys.readouterr().out
    assert "No issues found." in captured
    assert "No suggestions." in captured


def test_print_agent_section_caps_suggestions_shown(capsys: pytest.CaptureFixture[str]) -> None:
    result = _agent_result(
        verdict="COMMENT",
        issues=["one issue"],
        suggestions=["s1", "s2", "s3", "s4", "s5"],
    )

    _print_agent_section("Test Coverage", result)

    captured = capsys.readouterr().out
    assert "s1" in captured
    assert "s2" in captured
    assert "s3" in captured
    assert "s4" not in captured
    assert "s5" not in captured


def test_doctor_all_passed_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=DoctorResult(
            checks=[
                CheckResult("Settings: github_token", True, "present"),
                CheckResult("Settings: openai_api_key", True, "present"),
                CheckResult("GitHub API", True, "authenticated"),
                CheckResult("OpenAI API", True, "authenticated"),
                CheckResult("ChromaDB", True, "accessible at './data/chroma'"),
            ]
        )
    )
    monkeypatch.setattr("core.doctor_service.run_doctor_checks", mock)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "PASS" in result.stdout
    assert "All checks passed" in result.stdout


def test_doctor_one_failure_exits_one(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=DoctorResult(
            checks=[
                CheckResult("Settings: github_token", True, "present"),
                CheckResult("Settings: openai_api_key", True, "present"),
                CheckResult("GitHub API", False, "unreachable or unauthorized (GithubException)"),
                CheckResult("OpenAI API", True, "authenticated"),
                CheckResult("ChromaDB", True, "accessible at './data/chroma'"),
            ]
        )
    )
    monkeypatch.setattr("core.doctor_service.run_doctor_checks", mock)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert "FAIL" in result.stdout
    assert "GitHub API" in result.stdout


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


def test_ingest_vectorstore_exception_no_traceback(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        side_effect=VectorStoreError("failed to open ChromaDB collection at 'x': boom")
    )
    monkeypatch.setattr("core.ingest_service.ingest_repository", mock)

    result = runner.invoke(app, ["ingest", "octocat/Hello-World"])

    assert result.exit_code == 1
    assert "failed to open ChromaDB collection" in result.output
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
