from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException

from api.allowlist import check_repo_allowed
from api.models import JobCreated, ReviewRequest

router = APIRouter()


def _parse_repo(repo: str) -> tuple[str, str]:
    """Split 'owner/repo' into (owner, repo), raising a clean 400 otherwise."""
    parts = repo.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise HTTPException(status_code=400, detail=f"expected 'owner/repo', got {repo!r}")
    return parts[0], parts[1]


def create_job(job_id: uuid.UUID, owner: str, repo: str, pr_number: int) -> tuple[dict, bool]:
    """Lazily import core.supabase_jobs so it never joins api.main's module-scope imports."""
    from core.supabase_jobs import create_job as _create_job

    return _create_job(job_id, "review", f"{owner}/{repo}", pr_number)


async def start_review_job(
    job_id: uuid.UUID, owner: str, repo: str, pr_number: int, full: bool
) -> None:
    """Lazily import core.job_service so it never joins api.main's module-scope imports."""
    from core.job_service import start_review_job as _start_review_job

    await _start_review_job(job_id, owner, repo, pr_number, full)


@router.post("/review", response_model=JobCreated, status_code=202)
async def review(request: ReviewRequest, background_tasks: BackgroundTasks) -> JobCreated:
    """Start reviewing a pull request using historical repo context and OpenAI.

    Returns immediately with a job id — the review itself runs in the background and is
    polled via GET /jobs/{job_id}. request.job_id is client-generated, making this idempotent:
    a double-click or a retried POST with the same id hits the existing job instead of
    starting the review a second time.

    `full=True` bypasses the incremental/cached review history — the only way the web UI can
    force a fresh review of a PR that's currently showing a stale cached verdict.
    """
    owner, name = _parse_repo(request.repo)
    check_repo_allowed(owner, name)
    job, created = create_job(request.job_id, owner, name, request.pr_number)
    if created:
        background_tasks.add_task(
            start_review_job, request.job_id, owner, name, request.pr_number, request.full
        )
    return JobCreated(job_id=job["id"])
