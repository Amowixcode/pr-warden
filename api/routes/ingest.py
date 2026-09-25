from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException

from api.models import IngestRequest, JobCreated

router = APIRouter()


def _parse_repo(repo: str) -> tuple[str, str]:
    """Split 'owner/repo' into (owner, repo), raising a clean 400 otherwise."""
    parts = repo.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise HTTPException(status_code=400, detail=f"expected 'owner/repo', got {repo!r}")
    return parts[0], parts[1]


def create_job(job_id: uuid.UUID, owner: str, repo: str) -> tuple[dict, bool]:
    """Lazily import core.supabase_jobs so it never joins api.main's module-scope imports."""
    from core.supabase_jobs import create_job as _create_job

    return _create_job(job_id, "ingest", f"{owner}/{repo}")


async def start_ingest_job(job_id: uuid.UUID, owner: str, repo: str, full: bool) -> None:
    """Lazily import core.job_service so it never joins api.main's module-scope imports."""
    from core.job_service import start_ingest_job as _start_ingest_job

    await _start_ingest_job(job_id, owner, repo, full)


@router.post("/ingest", response_model=JobCreated, status_code=202)
async def ingest(request: IngestRequest, background_tasks: BackgroundTasks) -> JobCreated:
    """Start indexing a repository's issues, merged PRs, and commits into ChromaDB.

    Returns immediately with a job id — the ingest itself runs in the background and is
    polled via GET /jobs/{job_id}. request.job_id is client-generated, making this idempotent:
    a double-click or a retried POST with the same id hits the existing job instead of
    starting the ingest a second time.
    """
    owner, name = _parse_repo(request.repo)
    job, created = create_job(request.job_id, owner, name)
    if created:
        background_tasks.add_task(start_ingest_job, request.job_id, owner, name, False)
    return JobCreated(job_id=job["id"])
