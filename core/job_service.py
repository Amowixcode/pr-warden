from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import asdict

from core import supabase_jobs
from core.ingest_service import ingest_repository
from core.review_service import review_pr

logger = logging.getLogger(__name__)


async def start_review_job(
    job_id: uuid.UUID, owner: str, repo: str, pr_number: int, full: bool
) -> None:
    """Run review_pr in the background and report its progress/outcome onto the job row.

    This is the only place review_pr's on_stage hook is wired up — direct/CLI callers never
    pass it. review_pr's own output and everything it persists (local JSON, the reviews table)
    are unchanged; this only adds a side channel for a client to poll.
    """

    async def on_stage(stage: str) -> None:
        await asyncio.to_thread(supabase_jobs.update_job, job_id, stage=stage)

    try:
        result = await review_pr(owner, repo, pr_number, full=full, on_stage=on_stage)
    except Exception as exc:
        logger.exception("Review job %s failed", job_id)
        await asyncio.to_thread(supabase_jobs.update_job, job_id, status="failed", error=str(exc))
        return
    await asyncio.to_thread(
        supabase_jobs.update_job,
        job_id,
        status="succeeded",
        stage="done",
        result=asdict(result),
    )


async def start_ingest_job(job_id: uuid.UUID, owner: str, repo: str, full: bool) -> None:
    """Run ingest_repository in the background and report its progress/outcome onto the job
    row. Mirrors start_review_job — see its docstring.
    """

    async def on_stage(stage: str) -> None:
        await asyncio.to_thread(supabase_jobs.update_job, job_id, stage=stage)

    try:
        result = await ingest_repository(owner, repo, full=full, on_stage=on_stage)
    except Exception as exc:
        logger.exception("Ingest job %s failed", job_id)
        await asyncio.to_thread(supabase_jobs.update_job, job_id, status="failed", error=str(exc))
        return
    await asyncio.to_thread(
        supabase_jobs.update_job,
        job_id,
        status="succeeded",
        stage="done",
        result=asdict(result),
    )
