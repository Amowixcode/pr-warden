from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, HTTPException

from api.models import JobResponse

router = APIRouter()


def get_job(job_id: uuid.UUID) -> dict | None:
    """Lazily import core.supabase_jobs so it never joins api.main's module-scope imports."""
    from core.supabase_jobs import get_job as _get_job

    return _get_job(job_id)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def job(job_id: uuid.UUID) -> dict:
    """Poll a background review/ingest job. No auth — job ids are opaque, client-generated
    UUIDs, not enumerable, and this is the only way the web UI can show progress or pick a
    result back up after a page refresh (see api/main.py for the one other unauthenticated
    exception, GET /reviews/{id}).
    """
    result = await asyncio.to_thread(get_job, job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="job not found")
    return result
