from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from github import GithubException
from openai import OpenAIError
from pydantic import BaseModel, ValidationError

from core.doctor_service import (
    _check_chroma,
    _check_github,
    _check_openai,
    _check_settings,
    _check_supabase,
    run_doctor_checks,
)
from core.exceptions import VectorStoreError


class _RequiredFieldsProbe(BaseModel):
    """Minimal model used to generate a real pydantic ValidationError for a missing field,
    without depending on the real config.settings.Settings class, env vars, or .env file.
    """

    github_token: str
    openai_api_key: str


def _missing_field_error(**present: str) -> ValidationError:
    with pytest.raises(ValidationError) as exc_info:
        _RequiredFieldsProbe(**present)
    return exc_info.value


def _fake_settings(**overrides: object) -> SimpleNamespace:
    defaults = {
        "github_token": "tok",
        "github_max_retries": 3,
        "openai_api_key": "key",
        "openai_max_retries": 3,
        "chroma_persist_dir": "./data/chroma",
        "chroma_collection_name": "pr_warden",
    }
    return SimpleNamespace(**{**defaults, **overrides})


# ── _check_settings ──────────────────────────────────────────────────────────


def test_check_settings_all_present() -> None:
    with patch("config.settings.Settings", return_value=_fake_settings()):
        checks, settings = _check_settings()

    assert all(c.passed for c in checks)
    assert {c.detail for c in checks} == {"present"}
    assert settings is not None


def test_check_settings_missing_github_token() -> None:
    error = _missing_field_error(openai_api_key="key")

    with patch("config.settings.Settings", side_effect=error):
        checks, settings = _check_settings()

    assert settings is None
    gh_check = next(c for c in checks if "github_token" in c.name)
    oa_check = next(c for c in checks if "openai_api_key" in c.name)
    assert gh_check.passed is False
    assert gh_check.detail == "missing"
    assert oa_check.passed is True
    assert oa_check.detail == "present"


def test_check_settings_missing_both_required_fields() -> None:
    error = _missing_field_error()

    with patch("config.settings.Settings", side_effect=error):
        checks, settings = _check_settings()

    assert settings is None
    assert all(not c.passed for c in checks)
    assert all(c.detail == "missing" for c in checks)


def test_check_settings_flags_empty_string_as_not_present() -> None:
    with patch(
        "config.settings.Settings",
        return_value=_fake_settings(github_token=""),
    ):
        checks, settings = _check_settings()

    gh_check = next(c for c in checks if "github_token" in c.name)
    assert gh_check.passed is False
    assert gh_check.detail == "empty"
    assert settings is not None


def test_check_settings_never_exposes_the_value() -> None:
    secret = "SUPER-SECRET-GH-TOKEN-abc123"
    with patch("config.settings.Settings", return_value=_fake_settings(github_token=secret)):
        checks, _ = _check_settings()

    assert all(secret not in c.detail for c in checks)


# ── _check_github ────────────────────────────────────────────────────────────


async def test_check_github_success() -> None:
    settings = _fake_settings()
    with patch("core.doctor_service.GitHubClient") as mock_cls:
        mock_cls.return_value.ping = MagicMock()
        result = await _check_github(settings)

    assert result.name == "GitHub API"
    assert result.passed is True


async def test_check_github_failure_does_not_leak_exception_message() -> None:
    settings = _fake_settings(github_token="GH-SECRET-abc123")
    with patch("core.doctor_service.GitHubClient") as mock_cls:
        mock_cls.return_value.ping.side_effect = GithubException(
            401, {"message": "Bad credentials: GH-SECRET-abc123"}, None
        )
        result = await _check_github(settings)

    assert result.passed is False
    assert "GH-SECRET-abc123" not in result.detail


# ── _check_openai ─────────────────────────────────────────────────────────────


async def test_check_openai_success() -> None:
    settings = _fake_settings()
    with patch("core.doctor_service.OpenAI") as mock_cls:
        mock_cls.return_value.models.list = MagicMock()
        result = await _check_openai(settings)

    assert result.name == "OpenAI API"
    assert result.passed is True


async def test_check_openai_failure_does_not_leak_exception_message() -> None:
    settings = _fake_settings(openai_api_key="sk-SECRET-xyz789")
    with patch("core.doctor_service.OpenAI") as mock_cls:
        mock_cls.return_value.models.list.side_effect = OpenAIError(
            "Incorrect API key provided: sk-SECRET-xyz789"
        )
        result = await _check_openai(settings)

    assert result.passed is False
    assert "sk-SECRET-xyz789" not in result.detail


# ── _check_chroma ─────────────────────────────────────────────────────────────


async def test_check_chroma_success() -> None:
    settings = _fake_settings()
    with patch("ingestion.vector_store.build_chroma_collection"):
        result = await _check_chroma(settings)

    assert result.name == "ChromaDB"
    assert result.passed is True


async def test_check_chroma_failure() -> None:
    settings = _fake_settings(chroma_persist_dir="./bad-dir")
    with patch(
        "ingestion.vector_store.build_chroma_collection",
        side_effect=VectorStoreError("failed to open ChromaDB collection at './bad-dir': boom"),
    ):
        result = await _check_chroma(settings)

    assert result.passed is False
    assert "bad-dir" in result.detail


# ── _check_supabase ───────────────────────────────────────────────────────────


def _mock_supabase_client(execute_side_effect: Exception | None = None) -> MagicMock:
    client = MagicMock()
    execute = client.table.return_value.select.return_value.limit.return_value.execute
    execute.side_effect = execute_side_effect
    return client


async def test_check_supabase_not_configured() -> None:
    with patch("core.supabase_client.get_supabase_client", return_value=None):
        result = await _check_supabase()

    assert result.name == "Supabase"
    assert result.passed is False
    assert result.detail == "not configured"


async def test_check_supabase_healthy() -> None:
    with patch("core.supabase_client.get_supabase_client", return_value=_mock_supabase_client()):
        result = await _check_supabase()

    assert result.name == "Supabase"
    assert result.passed is True
    assert result.detail == "reachable"


async def test_check_supabase_query_fails() -> None:
    client = _mock_supabase_client(execute_side_effect=RuntimeError("connection refused"))
    with patch("core.supabase_client.get_supabase_client", return_value=client):
        result = await _check_supabase()

    assert result.passed is False
    assert "RuntimeError" in result.detail
    assert "connection refused" not in result.detail


# ── run_doctor_checks (end-to-end) ───────────────────────────────────────────


async def test_run_doctor_checks_all_pass() -> None:
    with (
        patch("config.settings.Settings", return_value=_fake_settings()),
        patch("core.doctor_service.GitHubClient") as mock_gh_cls,
        patch("core.doctor_service.OpenAI") as mock_oa_cls,
        patch("ingestion.vector_store.build_chroma_collection"),
        patch("core.supabase_client.get_supabase_client", return_value=_mock_supabase_client()),
    ):
        mock_gh_cls.return_value.ping = MagicMock()
        mock_oa_cls.return_value.models.list = MagicMock()
        result = await run_doctor_checks()

    assert result.all_passed is True
    assert len(result.checks) == 6


async def test_run_doctor_checks_settings_missing_skips_live_checks() -> None:
    error = _missing_field_error()

    with patch("config.settings.Settings", side_effect=error):
        result = await run_doctor_checks()

    assert result.all_passed is False
    assert len(result.checks) == 6
    assert all("skipped" in c.detail for c in result.checks[2:])


async def test_run_doctor_checks_one_live_check_failing_fails_overall() -> None:
    with (
        patch("config.settings.Settings", return_value=_fake_settings()),
        patch("core.doctor_service.GitHubClient") as mock_gh_cls,
        patch("core.doctor_service.OpenAI") as mock_oa_cls,
        patch("ingestion.vector_store.build_chroma_collection"),
        patch("core.supabase_client.get_supabase_client", return_value=_mock_supabase_client()),
    ):
        mock_gh_cls.return_value.ping.side_effect = GithubException(401, {}, None)
        mock_oa_cls.return_value.models.list = MagicMock()
        result = await run_doctor_checks()

    assert result.all_passed is False


async def test_run_doctor_checks_never_leaks_secret_values() -> None:
    """Regression test for the acceptance criterion: no raw secret value is ever printed,
    even in the worst case where an underlying SDK's own exception message embeds it.
    """
    github_marker = "GH-SECRET-MARKER-abc123"
    openai_marker = "OPENAI-SECRET-MARKER-xyz789"
    supabase_marker = "SUPABASE-SECRET-MARKER-def456"

    supabase_error = RuntimeError(f"connection to postgresql://...:{supabase_marker}@... failed")
    supabase_client = _mock_supabase_client(execute_side_effect=supabase_error)

    with (
        patch(
            "config.settings.Settings",
            return_value=_fake_settings(github_token=github_marker, openai_api_key=openai_marker),
        ),
        patch("core.doctor_service.GitHubClient") as mock_gh_cls,
        patch("core.doctor_service.OpenAI") as mock_oa_cls,
        patch("ingestion.vector_store.build_chroma_collection"),
        patch("core.supabase_client.get_supabase_client", return_value=supabase_client),
    ):
        mock_gh_cls.return_value.ping.side_effect = GithubException(
            401, {"message": f"Bad credentials: {github_marker}"}, None
        )
        mock_oa_cls.return_value.models.list.side_effect = OpenAIError(
            f"Incorrect API key provided: {openai_marker}"
        )
        result = await run_doctor_checks()

    all_detail_text = " ".join(c.detail for c in result.checks)
    assert github_marker not in all_detail_text
    assert openai_marker not in all_detail_text
    assert supabase_marker not in all_detail_text
    assert result.all_passed is False
