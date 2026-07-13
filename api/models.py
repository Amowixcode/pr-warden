from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReviewRequest(BaseModel):
    repo: str
    pr_number: int


class IngestRequest(BaseModel):
    repo: str


class AgentResultModel(BaseModel):
    model_config = {"from_attributes": True}

    summary: str
    verdict: str
    issues: list[str]
    suggestions: list[str]


class ReviewResponse(BaseModel):
    model_config = {"from_attributes": True}

    pr_number: int
    summary: str
    verdict: str
    issues: list[str]
    suggestions: list[str]
    security_result: AgentResultModel
    quality_result: AgentResultModel
    test_result: AgentResultModel
    incremental: bool = False
    cached: bool = False
    prior_verdict: str | None = None
    prior_head_sha: str | None = None


class IngestResponse(BaseModel):
    model_config = {"from_attributes": True}

    issues_indexed: int
    prs_indexed: int
    commits_indexed: int
    total_newly_indexed: int
    incremental: bool = False


class CheckResultModel(BaseModel):
    model_config = {"from_attributes": True}

    name: str
    passed: bool
    detail: str


class HealthResponse(BaseModel):
    model_config = {"from_attributes": True}

    checks: list[CheckResultModel]
    all_passed: bool


class ReviewHistoryItem(BaseModel):
    id: int
    repo: str
    pr_number: int
    head_sha: str
    verdict: str
    summary: str
    issues: list[str]
    suggestions: list[str]
    created_at: datetime
