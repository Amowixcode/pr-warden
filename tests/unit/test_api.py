from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from github import GithubException

from agents.state import AgentResult
from api.main import app
from core.doctor_service import CheckResult, DoctorResult
from core.ingest_service import IngestResult
from core.review_service import ReviewResult

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


def test_review_endpoint_returns_review_result(monkeypatch: pytest.MonkeyPatch) -> None:
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
    monkeypatch.setattr("api.routes.review.review_pr", mock)

    response = client.post("/review", json={"repo": "octocat/Hello-World", "pr_number": 7})

    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] == "APPROVE"
    assert data["pr_number"] == 7
    assert data["suggestions"] == ["Add tests"]
    assert data["security_result"]["verdict"] == "APPROVE"
    mock.assert_awaited_once_with("octocat", "Hello-World", 7)


def test_review_endpoint_invalid_repo_format() -> None:
    response = client.post("/review", json={"repo": "invalid", "pr_number": 7})

    assert response.status_code == 400
    assert "owner/repo" in response.json()["detail"]


def test_review_endpoint_github_exception_maps_to_status(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(side_effect=GithubException(404, {"message": "Not Found"}, None))
    monkeypatch.setattr("api.routes.review.review_pr", mock)

    response = client.post("/review", json={"repo": "octocat/Hello-World", "pr_number": 999})

    assert response.status_code == 404
    assert "Not Found" in response.json()["detail"]


def test_ingest_endpoint_returns_ingest_result(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=IngestResult(
            issues_indexed=3, prs_indexed=2, commits_indexed=10, total_newly_indexed=15
        )
    )
    monkeypatch.setattr("api.routes.ingest.ingest_repository", mock)

    response = client.post("/ingest", json={"repo": "octocat/Hello-World"})

    assert response.status_code == 200
    data = response.json()
    assert data["total_newly_indexed"] == 15
    mock.assert_awaited_once_with("octocat", "Hello-World")


def test_ingest_endpoint_invalid_repo_format() -> None:
    response = client.post("/ingest", json={"repo": "invalid"})

    assert response.status_code == 400
    assert "owner/repo" in response.json()["detail"]


def test_reviews_endpoint_returns_empty_list() -> None:
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


def test_health_endpoint_all_passed(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=DoctorResult(
            checks=[
                CheckResult("Settings: github_token", True, "present"),
                CheckResult("GitHub API", True, "authenticated"),
            ]
        )
    )
    monkeypatch.setattr("api.routes.health.run_doctor_checks", mock)

    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["all_passed"] is True
    assert len(data["checks"]) == 2


def test_health_endpoint_one_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    mock = AsyncMock(
        return_value=DoctorResult(
            checks=[
                CheckResult("Settings: github_token", True, "present"),
                CheckResult("GitHub API", False, "unreachable"),
            ]
        )
    )
    monkeypatch.setattr("api.routes.health.run_doctor_checks", mock)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["all_passed"] is False
