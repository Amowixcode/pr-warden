from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from agents.state import AgentResult
from api import rate_limiter
from api.main import app
from config.settings import get_settings
from core.doctor_service import CheckResult, DoctorResult
from core.pr_service import OpenPR

client = TestClient(app)


def _agent_result(
    verdict: str = "APPROVE",
    summary: str = "Looks fine",
    issues: list[str] | None = None,
    suggestions: list[str] | None = None,
) -> AgentResult:
    return AgentResult(
        summary=summary, verdict=verdict, issues=issues or [], suggestions=suggestions or []
    )


def _job_row(job_id: uuid.UUID, kind: str = "review", **overrides: object) -> dict:
    row = {
        "id": str(job_id),
        "kind": kind,
        "repo": "octocat/Hello-World",
        "pr_number": 7,
        "status": "running",
        "stage": "queued",
        "result": None,
        "error": None,
        "created_at": "2024-06-01T00:00:00+00:00",
        "updated_at": "2024-06-01T00:00:00+00:00",
    }
    row.update(overrides)
    return row


def _mock_create_job(created: bool = True):
    """A create_job-shaped mock: returns (job row matching the call, created)."""

    def _create(job_id, kind, repo, pr_number=None):
        return _job_row(job_id, kind=kind, repo=repo, pr_number=pr_number), created

    return MagicMock(side_effect=_create)


def test_review_endpoint_returns_202_with_job_id(monkeypatch: pytest.MonkeyPatch) -> None:
    job_id = uuid.uuid4()
    monkeypatch.setattr("api.routes.review.create_job", _mock_create_job())
    start_job = AsyncMock()
    monkeypatch.setattr("api.routes.review.start_review_job", start_job)

    response = client.post(
        "/review", json={"repo": "octocat/Hello-World", "pr_number": 7, "job_id": str(job_id)}
    )

    assert response.status_code == 202
    assert response.json() == {"job_id": str(job_id)}
    start_job.assert_awaited_once_with(job_id, "octocat", "Hello-World", 7, False)


def test_review_endpoint_full_flag_passed_through(monkeypatch: pytest.MonkeyPatch) -> None:
    """The only way the web UI can force a fresh review of a PR showing a stale cached verdict —
    see issue #124.
    """
    job_id = uuid.uuid4()
    monkeypatch.setattr("api.routes.review.create_job", _mock_create_job())
    start_job = AsyncMock()
    monkeypatch.setattr("api.routes.review.start_review_job", start_job)

    response = client.post(
        "/review",
        json={
            "repo": "octocat/Hello-World",
            "pr_number": 7,
            "full": True,
            "job_id": str(job_id),
        },
    )

    assert response.status_code == 202
    start_job.assert_awaited_once_with(job_id, "octocat", "Hello-World", 7, True)


def test_review_endpoint_duplicate_job_id_does_not_reschedule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The client-generated job_id makes creation idempotent: a retried/duplicated POST with
    the same id must not start a second review.
    """
    job_id = uuid.uuid4()
    monkeypatch.setattr("api.routes.review.create_job", _mock_create_job(created=False))
    start_job = AsyncMock()
    monkeypatch.setattr("api.routes.review.start_review_job", start_job)

    response = client.post(
        "/review", json={"repo": "octocat/Hello-World", "pr_number": 7, "job_id": str(job_id)}
    )

    assert response.status_code == 202
    assert response.json() == {"job_id": str(job_id)}
    start_job.assert_not_called()


def test_review_endpoint_missing_job_id_is_422() -> None:
    response = client.post("/review", json={"repo": "octocat/Hello-World", "pr_number": 7})

    assert response.status_code == 422


def test_review_endpoint_invalid_repo_format() -> None:
    response = client.post(
        "/review", json={"repo": "invalid", "pr_number": 7, "job_id": str(uuid.uuid4())}
    )

    assert response.status_code == 400
    assert "owner/repo" in response.json()["detail"]


def test_ingest_endpoint_returns_202_with_job_id(monkeypatch: pytest.MonkeyPatch) -> None:
    job_id = uuid.uuid4()
    monkeypatch.setattr("api.routes.ingest.create_job", _mock_create_job())
    start_job = AsyncMock()
    monkeypatch.setattr("api.routes.ingest.start_ingest_job", start_job)

    response = client.post("/ingest", json={"repo": "octocat/Hello-World", "job_id": str(job_id)})

    assert response.status_code == 202
    assert response.json() == {"job_id": str(job_id)}
    start_job.assert_awaited_once_with(job_id, "octocat", "Hello-World", False)


def test_ingest_endpoint_duplicate_job_id_does_not_reschedule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = uuid.uuid4()
    monkeypatch.setattr("api.routes.ingest.create_job", _mock_create_job(created=False))
    start_job = AsyncMock()
    monkeypatch.setattr("api.routes.ingest.start_ingest_job", start_job)

    response = client.post("/ingest", json={"repo": "octocat/Hello-World", "job_id": str(job_id)})

    assert response.status_code == 202
    start_job.assert_not_called()


def test_ingest_endpoint_missing_job_id_is_422() -> None:
    response = client.post("/ingest", json={"repo": "octocat/Hello-World"})

    assert response.status_code == 422


def test_ingest_endpoint_invalid_repo_format() -> None:
    response = client.post("/ingest", json={"repo": "invalid", "job_id": str(uuid.uuid4())})

    assert response.status_code == 400
    assert "owner/repo" in response.json()["detail"]


def test_ingest_endpoint_never_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /ingest is public — same as /reviews, /prs, and /health."""
    monkeypatch.setattr(get_settings(), "api_shared_key", "s3cr3t")
    monkeypatch.setattr("api.routes.ingest.create_job", _mock_create_job())
    monkeypatch.setattr("api.routes.ingest.start_ingest_job", AsyncMock())

    response = client.post(
        "/ingest", json={"repo": "octocat/Hello-World", "job_id": str(uuid.uuid4())}
    )

    assert response.status_code == 202


def test_reviews_endpoint_returns_empty_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("api.routes.history.list_reviews", lambda: [])

    response = client.get("/reviews")

    assert response.status_code == 200
    assert response.json() == []


def test_reviews_endpoint_surfaces_supabase_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        {
            "id": 1,
            "repo": "octocat/Hello-World",
            "pr_number": 7,
            "head_sha": "deadbeef",
            "verdict": "APPROVE",
            "summary": "Looks good",
            "issues": [],
            "suggestions": [],
            "created_at": "2024-06-01T00:00:00Z",
        }
    ]
    monkeypatch.setattr("api.routes.history.list_reviews", lambda: rows)

    response = client.get("/reviews")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["repo"] == "octocat/Hello-World"
    assert data[0]["pr_number"] == 7


def test_health_deep_endpoint_all_passed(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=DoctorResult(
            checks=[
                CheckResult("Settings: github_token", True, "present"),
                CheckResult("GitHub API", True, "authenticated"),
            ]
        )
    )
    monkeypatch.setattr("api.routes.health.run_doctor_checks", mock)

    response = client.get("/health/deep")

    assert response.status_code == 200
    data = response.json()
    assert data["all_passed"] is True
    assert len(data["checks"]) == 2


def test_health_deep_endpoint_one_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=DoctorResult(
            checks=[
                CheckResult("Settings: github_token", True, "present"),
                CheckResult("GitHub API", False, "unreachable"),
            ]
        )
    )
    monkeypatch.setattr("api.routes.health.run_doctor_checks", mock)

    response = client.get("/health/deep")

    assert response.status_code == 200
    assert response.json()["all_passed"] is False


def test_health_endpoint_returns_ok_without_external_io(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("liveness must not construct a GitHub or OpenAI client")

    monkeypatch.setattr("gh.client.GitHubClient", _boom)
    monkeypatch.setattr("openai.OpenAI", _boom)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_deep_endpoint_requires_api_key_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "api_shared_key", "s3cr3t")
    monkeypatch.setattr(
        "api.routes.health.run_doctor_checks", AsyncMock(return_value=DoctorResult(checks=[]))
    )

    response = client.get("/health/deep")

    assert response.status_code == 401


def test_health_deep_endpoint_accepts_correct_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "api_shared_key", "s3cr3t")
    monkeypatch.setattr(
        "api.routes.health.run_doctor_checks", AsyncMock(return_value=DoctorResult(checks=[]))
    )

    response = client.get("/health/deep", headers={"X-API-Key": "s3cr3t"})

    assert response.status_code == 200


def test_invalid_settings_returns_handled_500(monkeypatch: pytest.MonkeyPatch) -> None:
    """A genuinely broken Settings() must surface as a handled 500 via the registered
    ValidationError handler, not an import-time crash. require_api_key calls get_settings()
    before the route body runs, so any authenticated route exercises this path.
    """
    import os

    from pydantic_settings import BaseSettings, SettingsConfigDict

    import config.settings as settings_module

    class _BrokenSettings(BaseSettings):
        model_config = SettingsConfigDict(env_file=None)

        required_with_no_source: str

    monkeypatch.setattr(settings_module, "Settings", _BrokenSettings)
    settings_module.get_settings.cache_clear()
    try:
        response = client.get("/reviews")

        assert response.status_code == 500
        assert "invalid configuration" in response.json()["detail"]
        for secret_env_var in ("GITHUB_TOKEN", "OPENAI_API_KEY"):
            value = os.environ.get(secret_env_var)
            if value:
                assert value not in response.text
    finally:
        settings_module.get_settings.cache_clear()


def test_reviews_endpoint_never_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /reviews is public — the home screen and history view read it with no key."""
    monkeypatch.setattr(get_settings(), "api_shared_key", "s3cr3t")
    monkeypatch.setattr("api.routes.history.list_reviews", lambda: [])

    response = client.get("/reviews")

    assert response.status_code == 200


def test_health_endpoint_never_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "api_shared_key", "s3cr3t")

    response = client.get("/health")

    assert response.status_code == 200


def test_review_endpoint_returns_401_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "api_shared_key", "s3cr3t")

    response = client.post(
        "/review",
        json={"repo": "octocat/Hello-World", "pr_number": 7, "job_id": str(uuid.uuid4())},
    )

    assert response.status_code == 401


def test_review_endpoint_returns_401_with_wrong_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "api_shared_key", "s3cr3t")

    response = client.post(
        "/review",
        json={"repo": "octocat/Hello-World", "pr_number": 7, "job_id": str(uuid.uuid4())},
        headers={"X-API-Key": "wrong"},
    )

    assert response.status_code == 401


# ── Repo allowlist ───────────────────────────────────────────────────────────


def test_review_endpoint_rejects_repo_outside_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "review_allowed_repos", "octocat/Hello-World")

    response = client.post(
        "/review",
        json={"repo": "evil/other-repo", "pr_number": 7, "job_id": str(uuid.uuid4())},
    )

    assert response.status_code == 403
    assert "allowlist" in response.json()["detail"]


def test_review_endpoint_allows_repo_in_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "review_allowed_repos", "octocat/Hello-World")
    monkeypatch.setattr("api.routes.review.create_job", _mock_create_job())
    monkeypatch.setattr("api.routes.review.start_review_job", AsyncMock())

    response = client.post(
        "/review",
        json={"repo": "octocat/Hello-World", "pr_number": 7, "job_id": str(uuid.uuid4())},
    )

    assert response.status_code == 202


def test_review_endpoint_no_allowlist_configured_allows_any_repo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "review_allowed_repos", None)
    monkeypatch.setattr("api.routes.review.create_job", _mock_create_job())
    monkeypatch.setattr("api.routes.review.start_review_job", AsyncMock())

    response = client.post(
        "/review",
        json={"repo": "anyone/anything", "pr_number": 7, "job_id": str(uuid.uuid4())},
    )

    assert response.status_code == 202


# ── CORS ─────────────────────────────────────────────────────────────────────

_ALLOWED_ORIGIN = "https://allowed.example.com"
_ALLOWED_ORIGIN_2 = "https://allowed-preview.example.com"
_ALLOWED_ORIGINS = f"{_ALLOWED_ORIGIN},{_ALLOWED_ORIGIN_2}"


def test_cors_preflight_disallowed_origin_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "allowed_origins", _ALLOWED_ORIGINS)

    response = client.options(
        "/health",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400


def test_cors_allowed_origin_gets_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "allowed_origins", _ALLOWED_ORIGINS)

    response = client.get("/health", headers={"Origin": _ALLOWED_ORIGIN})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == _ALLOWED_ORIGIN
    assert response.headers["vary"] == "Origin"


def test_cors_second_allowed_origin_gets_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """A second configured origin (e.g. a Vercel branch preview's own subdomain) must also be
    allowed — this is the multi-origin behavior this feature adds.
    """
    monkeypatch.setattr(get_settings(), "allowed_origins", _ALLOWED_ORIGINS)

    response = client.get("/health", headers={"Origin": _ALLOWED_ORIGIN_2})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == _ALLOWED_ORIGIN_2


def test_cors_disallowed_origin_gets_no_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "allowed_origins", _ALLOWED_ORIGINS)

    response = client.get("/health", headers={"Origin": "https://evil.example.com"})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
    assert response.headers["vary"] == "Origin"


def test_cors_no_allowed_origins_configured_blocks_everything(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "allowed_origins", None)

    response = client.get("/health", headers={"Origin": _ALLOWED_ORIGIN})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_cors_trailing_slash_in_config_still_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    """A trailing slash pasted into ALLOWED_ORIGINS (e.g. copied from a browser address bar)
    must still match the slash-less Origin header a browser actually sends.
    """
    monkeypatch.setattr(get_settings(), "allowed_origins", f"{_ALLOWED_ORIGIN}/")

    response = client.get("/health", headers={"Origin": _ALLOWED_ORIGIN})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == _ALLOWED_ORIGIN


def test_unhandled_exception_still_gets_cors_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """A route that raises an exception with no typed handler (not ValidationError,
    VectorStoreError, a GitHub/OpenAI SDK error, etc.) falls through to the catch-all
    `@app.exception_handler(Exception)`. Its response must still carry CORS headers, or the
    browser reports the real 500 as an opaque CORS failure instead of showing it.
    """
    monkeypatch.setattr(get_settings(), "allowed_origins", _ALLOWED_ORIGINS)
    monkeypatch.setattr(
        "api.routes.history.list_reviews",
        lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    # The default `client` raises server exceptions instead of returning a response for a
    # handler registered under the literal `Exception` class (see _ExternalApiErrorMiddleware's
    # docstring in api/main.py) — a real ASGI server never does this, so disable it here too.
    no_raise_client = TestClient(app, raise_server_exceptions=False)

    response = no_raise_client.get("/reviews", headers={"Origin": _ALLOWED_ORIGIN})

    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == _ALLOWED_ORIGIN
    assert response.headers["vary"] == "Origin"


# ── Rate limiting ────────────────────────────────────────────────────────────


def test_review_rate_limit_triggers_after_max_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rate_limiter, "_call_timestamps", [])
    monkeypatch.setattr(get_settings(), "review_rate_limit_max_calls", 2)
    monkeypatch.setattr("api.routes.review.create_job", _mock_create_job())
    monkeypatch.setattr("api.routes.review.start_review_job", AsyncMock())

    def _body() -> dict:
        return {"repo": "octocat/Hello-World", "pr_number": 7, "job_id": str(uuid.uuid4())}

    assert client.post("/review", json=_body()).status_code == 202
    assert client.post("/review", json=_body()).status_code == 202

    response = client.post("/review", json=_body())

    assert response.status_code == 429


def test_review_rate_limit_resets_outside_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rate_limiter, "_call_timestamps", [])
    monkeypatch.setattr(get_settings(), "review_rate_limit_max_calls", 1)
    monkeypatch.setattr(get_settings(), "review_rate_limit_window_seconds", 0)
    monkeypatch.setattr("api.routes.review.create_job", _mock_create_job())
    monkeypatch.setattr("api.routes.review.start_review_job", AsyncMock())

    def _body() -> dict:
        return {"repo": "octocat/Hello-World", "pr_number": 7, "job_id": str(uuid.uuid4())}

    assert client.post("/review", json=_body()).status_code == 202
    assert client.post("/review", json=_body()).status_code == 202


# ── List open PRs ────────────────────────────────────────────────────────────


def test_prs_endpoint_returns_open_prs(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=[
            OpenPR(number=12, title="Add dark mode", author="alice", age_days=3),
            OpenPR(number=13, title="Fix typo", author="bob", age_days=1),
        ]
    )
    monkeypatch.setattr("api.routes.prs.list_open_prs", mock)

    response = client.get("/prs/octocat/Hello-World")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["number"] == 12
    assert data[0]["title"] == "Add dark mode"
    assert data[0]["author"] == "alice"
    assert data[0]["age_days"] == 3
    mock.assert_awaited_once_with("octocat", "Hello-World")


def test_prs_endpoint_no_open_prs_returns_empty_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("api.routes.prs.list_open_prs", AsyncMock(return_value=[]))

    response = client.get("/prs/octocat/Hello-World")

    assert response.status_code == 200
    assert response.json() == []


def test_prs_endpoint_never_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /prs is public — the open-PR list is read-only and cheap."""
    monkeypatch.setattr(get_settings(), "api_shared_key", "s3cr3t")
    monkeypatch.setattr("api.routes.prs.list_open_prs", AsyncMock(return_value=[]))

    response = client.get("/prs/octocat/Hello-World")

    assert response.status_code == 200


# ── Review detail ────────────────────────────────────────────────────────────


def _review_detail_row() -> dict:
    return {
        "id": 1,
        "repo": "octocat/Hello-World",
        "pr_number": 7,
        "head_sha": "deadbeef",
        "verdict": "REQUEST_CHANGES",
        "summary": "1 issue flagged",
        "issues": ["path/to/file.py:10 - hardcoded secret"],
        "suggestions": [],
        "security_result": _agent_result(verdict="REQUEST_CHANGES"),
        "quality_result": _agent_result(),
        "test_result": _agent_result(),
        "created_at": "2024-06-01T00:00:00Z",
    }


def test_review_detail_endpoint_returns_full_record(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "api.routes.review_detail.get_review_by_id", lambda _id: _review_detail_row()
    )

    response = client.get("/reviews/1")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["verdict"] == "REQUEST_CHANGES"
    assert data["security_result"]["verdict"] == "REQUEST_CHANGES"
    assert data["quality_result"] is not None


def test_review_detail_endpoint_null_per_agent_results(monkeypatch: pytest.MonkeyPatch) -> None:
    row = _review_detail_row()
    row["security_result"] = None
    row["quality_result"] = None
    row["test_result"] = None
    monkeypatch.setattr("api.routes.review_detail.get_review_by_id", lambda _id: row)

    response = client.get("/reviews/1")

    assert response.status_code == 200
    data = response.json()
    assert data["security_result"] is None
    assert data["quality_result"] is None
    assert data["test_result"] is None


def test_review_detail_endpoint_404_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("api.routes.review_detail.get_review_by_id", lambda _id: None)

    response = client.get("/reviews/999")

    assert response.status_code == 404


def test_review_detail_endpoint_never_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "api_shared_key", "s3cr3t")
    monkeypatch.setattr(
        "api.routes.review_detail.get_review_by_id", lambda _id: _review_detail_row()
    )

    response = client.get("/reviews/1")

    assert response.status_code == 200


# ── Job polling ──────────────────────────────────────────────────────────────


def test_job_endpoint_returns_running_job(monkeypatch: pytest.MonkeyPatch) -> None:
    job_id = uuid.uuid4()
    row = _job_row(job_id, status="running", stage="running review agents")
    monkeypatch.setattr("api.routes.jobs.get_job", lambda _id: row)

    response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert data["stage"] == "running review agents"
    assert data["result"] is None


def test_job_endpoint_returns_succeeded_job_with_result(monkeypatch: pytest.MonkeyPatch) -> None:
    job_id = uuid.uuid4()
    row = _job_row(
        job_id,
        status="succeeded",
        stage="done",
        result={"pr_number": 7, "verdict": "APPROVE"},
    )
    monkeypatch.setattr("api.routes.jobs.get_job", lambda _id: row)

    response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "succeeded"
    assert data["result"]["verdict"] == "APPROVE"


def test_job_endpoint_returns_failed_job_with_error(monkeypatch: pytest.MonkeyPatch) -> None:
    job_id = uuid.uuid4()
    row = _job_row(job_id, status="failed", error="GitHub API error: Not Found")
    monkeypatch.setattr("api.routes.jobs.get_job", lambda _id: row)

    response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["error"] == "GitHub API error: Not Found"


def test_job_endpoint_stale_running_job_reads_as_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end check that the dead-job read-time transform (core/supabase_jobs.py, tested
    directly in test_supabase_jobs.py) actually reaches the HTTP response unaltered.
    """
    job_id = uuid.uuid4()
    row = _job_row(job_id, status="failed", error="Job stalled — no progress reported recently.")
    monkeypatch.setattr("api.routes.jobs.get_job", lambda _id: row)

    response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert "stalled" in data["error"]


def test_job_endpoint_404_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("api.routes.jobs.get_job", lambda _id: None)

    response = client.get(f"/jobs/{uuid.uuid4()}")

    assert response.status_code == 404


def test_job_endpoint_invalid_id_is_422() -> None:
    response = client.get("/jobs/not-a-uuid")

    assert response.status_code == 422


def test_job_endpoint_never_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "api_shared_key", "s3cr3t")
    job_id = uuid.uuid4()
    monkeypatch.setattr("api.routes.jobs.get_job", lambda _id: _job_row(job_id))

    response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 200
