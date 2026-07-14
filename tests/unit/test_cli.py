from __future__ import annotations

import json
from unittest.mock import AsyncMock

import click
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
from core.pr_service import OpenPR
from core.review_service import ReviewResult

# A wide, fixed terminal size for every invoke() in this file — Rich's help/panel rendering
# wraps based on the ambient terminal width, which CI and local dev can report differently (or
# not report at all), splitting asserted substrings across a line break unpredictably otherwise.
runner = CliRunner(env={"COLUMNS": "200", "LINES": "50"})


def _agent_result(
    verdict: str = "APPROVE",
    summary: str = "Looks fine",
    issues: list[str] | None = None,
    suggestions: list[str] | None = None,
) -> AgentResult:
    return AgentResult(
        summary=summary, verdict=verdict, issues=issues or [], suggestions=suggestions or []
    )


def test_bare_invocation_shows_help_not_missing_command_error() -> None:
    """Typer's no_args_is_help raises NoArgsIsHelpError (a click.UsageError subclass), so the
    exit code stays 2 — same "usage issue" family as before — but the *content* changes from
    a terse "Missing command" one-liner to the full help listing + epilog, which is the actual
    behavior this task asks for.
    """
    result = runner.invoke(app, [])
    output = click.unstyle(result.output)

    assert result.exit_code == 2
    assert "Missing command" not in output
    assert "doctor" in output
    assert "ingest" in output
    assert "review" in output
    assert "Quickstart" in output


def test_help_epilog_shows_quickstart_flow() -> None:
    result = runner.invoke(app, ["--help"])
    output = click.unstyle(result.output)

    assert result.exit_code == 0
    assert "uv run warden doctor" in output
    assert "uv run warden ingest" in output
    assert "uv run warden review" in output
    assert "--help" in output


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
    mock.assert_awaited_once_with("octocat", "Hello-World", full=False)


def test_ingest_full_flag_passed_through(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=IngestResult(
            issues_indexed=0, prs_indexed=0, commits_indexed=0, total_newly_indexed=0
        )
    )
    monkeypatch.setattr("core.ingest_service.ingest_repository", mock)

    runner.invoke(app, ["ingest", "octocat/Hello-World", "--full"])

    mock.assert_awaited_once_with("octocat", "Hello-World", full=True)


def test_ingest_shows_incremental_banner(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=IngestResult(
            issues_indexed=1,
            prs_indexed=0,
            commits_indexed=2,
            total_newly_indexed=3,
            incremental=True,
        )
    )
    monkeypatch.setattr("core.ingest_service.ingest_repository", mock)

    result = runner.invoke(app, ["ingest", "octocat/Hello-World"])

    assert "Incremental ingest" in result.stdout


def test_ingest_no_banner_for_ordinary_full_ingest(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=IngestResult(
            issues_indexed=1, prs_indexed=0, commits_indexed=2, total_newly_indexed=3
        )
    )
    monkeypatch.setattr("core.ingest_service.ingest_repository", mock)

    result = runner.invoke(app, ["ingest", "octocat/Hello-World"])

    assert "Incremental ingest" not in result.stdout


def test_list_prs_success(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=[
            OpenPR(number=12, title="Add dark mode", author="alice", age_days=3),
            OpenPR(number=13, title="Fix typo", author="bob", age_days=1),
        ]
    )
    monkeypatch.setattr("core.pr_service.list_open_prs", mock)

    result = runner.invoke(app, ["list", "octocat/Hello-World"])

    assert result.exit_code == 0
    assert "Add dark mode" in result.stdout
    assert "alice" in result.stdout
    assert "#12" in result.stdout
    mock.assert_awaited_once_with("octocat", "Hello-World")


def test_list_prs_no_open_prs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("core.pr_service.list_open_prs", AsyncMock(return_value=[]))

    result = runner.invoke(app, ["list", "octocat/Hello-World"])

    assert result.exit_code == 0


def test_list_prs_invalid_repo_format() -> None:
    result = runner.invoke(app, ["list", "not-a-valid-repo"])

    assert result.exit_code == 2
    assert "owner/repo" in result.output


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
    mock.assert_awaited_once_with("octocat", "Hello-World", 7, full=False)


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

    # REQUEST_CHANGES must fail a CI step, not just print — non-zero exit is the whole point.
    assert result.exit_code == 1
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

    result = runner.invoke(app, ["review", "octocat/Hello-World", "7", "--verbose"])

    assert result.exit_code == 1
    assert "Per-Agent Findings" in result.stdout
    assert "Security" in result.stdout
    assert "Quality" in result.stdout
    assert "Test Coverage" in result.stdout
    assert "Found a hardcoded secret" in result.stdout
    assert "Missing a docstring" in result.stdout
    assert "No edge-case coverage" in result.stdout
    assert "Final Verdict" in result.stdout


def test_review_default_hides_per_agent_findings(monkeypatch: pytest.MonkeyPatch) -> None:
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

    assert result.exit_code == 1
    assert "Per-Agent Findings" not in result.stdout
    assert "Final Verdict" in result.stdout
    assert "Hardcoded secret" in result.stdout
    assert "Missing docstring" in result.stdout
    assert "No edge-case test" in result.stdout


def test_review_exits_zero_on_comment_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=ReviewResult(
            pr_number=11,
            summary="Minor notes only",
            verdict="COMMENT",
            issues=[],
            suggestions=["Consider renaming this variable"],
            security_result=_agent_result(),
            quality_result=_agent_result(verdict="COMMENT"),
            test_result=_agent_result(),
        )
    )
    monkeypatch.setattr("core.review_service.review_pr", mock)

    result = runner.invoke(app, ["review", "octocat/Hello-World", "11"])

    assert result.exit_code == 0
    assert "COMMENT" in result.stdout


def test_review_json_flag_outputs_expected_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=ReviewResult(
            pr_number=7,
            summary="Looks good",
            verdict="APPROVE",
            issues=[],
            suggestions=["Add tests"],
            security_result=_agent_result(summary="No secrets found"),
            quality_result=_agent_result(summary="Clean"),
            test_result=_agent_result(summary="Well covered"),
        )
    )
    monkeypatch.setattr("core.review_service.review_pr", mock)

    result = runner.invoke(app, ["review", "octocat/Hello-World", "7", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["pr_number"] == 7
    assert data["summary"] == "Looks good"
    assert data["verdict"] == "APPROVE"
    assert data["issues"] == []
    assert data["suggestions"] == ["Add tests"]
    for key in ("security_result", "quality_result", "test_result"):
        assert set(data[key].keys()) == {"summary", "verdict", "issues", "suggestions"}
    assert data["security_result"]["summary"] == "No secrets found"


def test_review_json_flag_omits_human_output(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=ReviewResult(
            pr_number=7,
            summary="Looks good",
            verdict="APPROVE",
            issues=[],
            suggestions=[],
            security_result=_agent_result(),
            quality_result=_agent_result(),
            test_result=_agent_result(),
        )
    )
    monkeypatch.setattr("core.review_service.review_pr", mock)

    result = runner.invoke(app, ["review", "octocat/Hello-World", "7", "--json"])

    assert "Per-Agent Findings" not in result.stdout
    assert "Final Verdict" not in result.stdout
    json.loads(result.stdout)  # still parses cleanly as a single JSON document


def test_review_json_flag_respects_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=ReviewResult(
            pr_number=9,
            summary="Needs work",
            verdict="REQUEST_CHANGES",
            issues=["bug A"],
            suggestions=[],
            security_result=_agent_result(verdict="REQUEST_CHANGES", issues=["bug A"]),
            quality_result=_agent_result(),
            test_result=_agent_result(),
        )
    )
    monkeypatch.setattr("core.review_service.review_pr", mock)

    result = runner.invoke(app, ["review", "octocat/Hello-World", "9", "--json"])

    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["verdict"] == "REQUEST_CHANGES"


def test_review_full_flag_passed_through(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=ReviewResult(
            pr_number=7,
            summary="Looks good",
            verdict="APPROVE",
            issues=[],
            suggestions=[],
            security_result=_agent_result(),
            quality_result=_agent_result(),
            test_result=_agent_result(),
        )
    )
    monkeypatch.setattr("core.review_service.review_pr", mock)

    runner.invoke(app, ["review", "octocat/Hello-World", "7", "--full"])

    mock.assert_awaited_once_with("octocat", "Hello-World", 7, full=True)


def test_review_full_reinvoke_request_changes_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--full re-reviews must still fail a CI step on REQUEST_CHANGES.

    Live PR verdicts aren't stable enough to assert against real GitHub data here (that
    instability against an unchanged PR was the actual bug — see agent temperature pinning),
    so this locks down the exit-code contract via a mocked review result instead.
    """
    mock = AsyncMock(
        return_value=ReviewResult(
            pr_number=36476,
            summary="Needs work",
            verdict="REQUEST_CHANGES",
            issues=["bug A"],
            suggestions=[],
            security_result=_agent_result(),
            quality_result=_agent_result(),
            test_result=_agent_result(),
        )
    )
    monkeypatch.setattr("core.review_service.review_pr", mock)

    result = runner.invoke(app, ["review", "facebook/react", "36476", "--full"])

    assert result.exit_code == 1
    assert "REQUEST_CHANGES" in result.stdout
    mock.assert_awaited_once_with("facebook", "react", 36476, full=True)


def test_review_default_full_flag_is_false(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=ReviewResult(
            pr_number=7,
            summary="Looks good",
            verdict="APPROVE",
            issues=[],
            suggestions=[],
            security_result=_agent_result(),
            quality_result=_agent_result(),
            test_result=_agent_result(),
        )
    )
    monkeypatch.setattr("core.review_service.review_pr", mock)

    runner.invoke(app, ["review", "octocat/Hello-World", "7"])

    mock.assert_awaited_once_with("octocat", "Hello-World", 7, full=False)


def test_review_shows_incremental_banner(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=ReviewResult(
            pr_number=7,
            summary="Looks good",
            verdict="APPROVE",
            issues=[],
            suggestions=[],
            security_result=_agent_result(),
            quality_result=_agent_result(),
            test_result=_agent_result(),
            incremental=True,
            cached=False,
            prior_verdict="COMMENT",
            prior_head_sha="deadbeef1234",
        )
    )
    monkeypatch.setattr("core.review_service.review_pr", mock)

    result = runner.invoke(app, ["review", "octocat/Hello-World", "7"])

    assert "Incremental review" in result.stdout
    assert "deadbee" in result.stdout
    assert "COMMENT" in result.stdout


def test_review_shows_cached_banner(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=ReviewResult(
            pr_number=7,
            summary="Looks good",
            verdict="APPROVE",
            issues=[],
            suggestions=[],
            security_result=_agent_result(),
            quality_result=_agent_result(),
            test_result=_agent_result(),
            incremental=True,
            cached=True,
            prior_verdict="APPROVE",
            prior_head_sha="deadbeef1234",
        )
    )
    monkeypatch.setattr("core.review_service.review_pr", mock)

    result = runner.invoke(app, ["review", "octocat/Hello-World", "7"])

    assert "No new commits since last review" in result.stdout
    assert "cached verdict" in result.stdout
    assert "deadbee" in result.stdout


def test_review_no_banner_for_ordinary_full_review(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=ReviewResult(
            pr_number=7,
            summary="Looks good",
            verdict="APPROVE",
            issues=[],
            suggestions=[],
            security_result=_agent_result(),
            quality_result=_agent_result(),
            test_result=_agent_result(),
        )
    )
    monkeypatch.setattr("core.review_service.review_pr", mock)

    result = runner.invoke(app, ["review", "octocat/Hello-World", "7"])

    assert "Incremental review" not in result.stdout
    assert "cached verdict" not in result.stdout


def test_review_json_includes_incremental_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=ReviewResult(
            pr_number=7,
            summary="Looks good",
            verdict="APPROVE",
            issues=[],
            suggestions=[],
            security_result=_agent_result(),
            quality_result=_agent_result(),
            test_result=_agent_result(),
            incremental=True,
            cached=False,
            prior_verdict="COMMENT",
            prior_head_sha="deadbeef1234",
        )
    )
    monkeypatch.setattr("core.review_service.review_pr", mock)

    result = runner.invoke(app, ["review", "octocat/Hello-World", "7", "--json"])

    data = json.loads(result.stdout)
    assert data["incremental"] is True
    assert data["cached"] is False
    assert data["prior_verdict"] == "COMMENT"
    assert data["prior_head_sha"] == "deadbeef1234"


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
