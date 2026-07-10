from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from github import GithubException
from openai import OpenAI, OpenAIError
from pydantic import ValidationError

from core.exceptions import VectorStoreError
from gh.client import GitHubClient

if TYPE_CHECKING:
    from config.settings import Settings

_REQUIRED_SETTINGS_FIELDS = ("github_token", "openai_api_key")


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


@dataclass
class DoctorResult:
    checks: list[CheckResult]

    @property
    def all_passed(self) -> bool:
        return all(check.passed for check in self.checks)


def _check_settings() -> tuple[list[CheckResult], Settings | None]:
    """Report pass/fail per required Settings field without ever exposing the value itself.

    Settings() reads env vars fresh on every call. A field that's entirely unset raises a
    ValidationError (caught below, fields identified by err["loc"] only — never err["input"]).
    A field present but set to an empty string loads fine under Pydantic's str type, so it's
    checked separately via truthiness.
    """
    try:
        from config.settings import Settings  # lazy: avoid Settings() at collection/import time

        settings = Settings()
    except ValidationError as e:
        missing = {str(err["loc"][0]) for err in e.errors() if err["type"] == "missing"}
        checks = [
            CheckResult(
                f"Settings: {field}",
                field not in missing,
                "missing" if field in missing else "present",
            )
            for field in _REQUIRED_SETTINGS_FIELDS
        ]
        return checks, None

    checks = [
        CheckResult(
            f"Settings: {field}",
            bool(getattr(settings, field)),
            "present" if getattr(settings, field) else "empty",
        )
        for field in _REQUIRED_SETTINGS_FIELDS
    ]
    return checks, settings


async def _check_github(settings: Settings) -> CheckResult:
    try:
        client = GitHubClient(settings.github_token, max_retries=settings.github_max_retries)
        await asyncio.to_thread(client.ping)
    except GithubException as e:
        return CheckResult("GitHub API", False, f"unreachable or unauthorized ({type(e).__name__})")
    except Exception as e:
        return CheckResult("GitHub API", False, f"unexpected error ({type(e).__name__})")
    return CheckResult("GitHub API", True, "authenticated")


async def _check_openai(settings: Settings) -> CheckResult:
    try:
        client = OpenAI(api_key=settings.openai_api_key, max_retries=settings.openai_max_retries)
        await asyncio.to_thread(client.models.list)
    except OpenAIError as e:
        return CheckResult("OpenAI API", False, f"unreachable or unauthorized ({type(e).__name__})")
    except Exception as e:
        return CheckResult("OpenAI API", False, f"unexpected error ({type(e).__name__})")
    return CheckResult("OpenAI API", True, "authenticated")


async def _check_chroma(settings: Settings) -> CheckResult:
    try:
        from ingestion.vector_store import build_chroma_collection  # lazy: see _check_settings

        await asyncio.to_thread(
            build_chroma_collection, settings.chroma_persist_dir, settings.chroma_collection_name
        )
    except VectorStoreError as e:
        return CheckResult("ChromaDB", False, str(e))
    return CheckResult("ChromaDB", True, f"accessible at {settings.chroma_persist_dir!r}")


async def run_doctor_checks() -> DoctorResult:
    """Run setup/health checks: Settings presence, GitHub, OpenAI, and ChromaDB connectivity.

    Never lets a check's exception propagate — each check catches its own failures and
    contributes a pass/fail CheckResult, so one failing check doesn't prevent the rest from
    running (unlike ingest/review, which fail fast via cli/main.py's shared _run()).
    """
    settings_checks, settings = _check_settings()
    checks = list(settings_checks)

    if settings is None:
        checks.append(CheckResult("GitHub API", False, "skipped — required settings missing"))
        checks.append(CheckResult("OpenAI API", False, "skipped — required settings missing"))
        checks.append(CheckResult("ChromaDB", False, "skipped — required settings missing"))
        return DoctorResult(checks=checks)

    checks.append(await _check_github(settings))
    checks.append(await _check_openai(settings))
    checks.append(await _check_chroma(settings))
    return DoctorResult(checks=checks)
