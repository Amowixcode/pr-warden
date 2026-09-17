from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ReviewRequest(BaseModel):
    repo: str
    pr_number: int
    full: bool = False
    job_id: uuid.UUID


class IngestRequest(BaseModel):
    repo: str
    job_id: uuid.UUID


class AgentResultModel(BaseModel):
    model_config = {"from_attributes": True}

    summary: str
    verdict: str
    issues: list[str]
    suggestions: list[str]


class CheckResultModel(BaseModel):
    model_config = {"from_attributes": True}

    name: str
    passed: bool
    detail: str


class HealthResponse(BaseModel):
    model_config = {"from_attributes": True}

    checks: list[CheckResultModel]
    all_passed: bool


class LivenessResponse(BaseModel):
    status: str = "ok"


class OpenPRResponse(BaseModel):
    model_config = {"from_attributes": True}

    number: int
    title: str
    author: str
    age_days: int


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


class ReviewDetailResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    repo: str
    pr_number: int
    head_sha: str
    verdict: str
    summary: str
    issues: list[str]
    suggestions: list[str]
    security_result: AgentResultModel | None = None
    quality_result: AgentResultModel | None = None
    test_result: AgentResultModel | None = None


class JobCreated(BaseModel):
    """The 202 body POST /review and POST /ingest return immediately — the work itself runs
    in the background and is polled via GET /jobs/{job_id}.
    """

    job_id: uuid.UUID


class JobResponse(BaseModel):
    """GET /jobs/{job_id} — result/error are only populated once status is terminal. stage is
    a short label ("running review agents"), never a percentage: review has no honest fraction
    to report.
    """

    id: uuid.UUID
    kind: str
    status: str
    stage: str
    result: dict | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    created_at: datetime
