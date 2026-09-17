from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from postgrest.exceptions import APIError

from core.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

_JOBS_TABLE = "jobs"
_UNIQUE_VIOLATION = "23505"
_CLEANUP_AFTER = timedelta(hours=24)
_STALE_AFTER = timedelta(minutes=5)


def _cleanup_old_jobs(client: object) -> None:
    """Best-effort delete of jobs older than 24h, run on every insert instead of a cron job.

    Never raises — a failed cleanup must not block creating the job the caller actually asked
    for.
    """
    cutoff = (datetime.now(UTC) - _CLEANUP_AFTER).isoformat()
    try:
        client.table(_JOBS_TABLE).delete().lt("created_at", cutoff).execute()
    except Exception:
        logger.warning("Failed to clean up old jobs in Supabase", exc_info=True)


def create_job(
    job_id: uuid.UUID, kind: str, repo: str, pr_number: int | None = None
) -> tuple[dict, bool]:
    """Idempotently create a job row. Returns (job, created).

    Raises RuntimeError if Supabase isn't configured — unlike reviews/ingests, a job has no
    other source of truth, so a silent no-op here would accept work the API could never report
    back on. The client-supplied job_id makes creation idempotent: inserting the same id twice
    (a double-click, a retried POST) hits the existing row (created=False) instead of starting
    the underlying work a second time.
    """
    client = get_supabase_client()
    if client is None:
        raise RuntimeError("Supabase is not configured; job-based endpoints require it")

    _cleanup_old_jobs(client)

    fields = {"id": str(job_id), "kind": kind, "repo": repo, "pr_number": pr_number}
    try:
        response = client.table(_JOBS_TABLE).insert(fields).execute()
    except APIError as exc:
        if exc.code != _UNIQUE_VIOLATION:
            raise
        existing = get_job(job_id)
        if existing is None:
            raise
        return existing, False
    return response.data[0], True


def update_job(
    job_id: uuid.UUID,
    *,
    stage: str | None = None,
    status: str | None = None,
    result: dict | None = None,
    error: str | None = None,
) -> None:
    """Patch a job's progress or terminal state, or log-and-continue on failure.

    Never raises — an intermediate stage update (or even the final status write) failing must
    not crash an otherwise-successful review/ingest. A job that stops making progress is caught
    by get_job's dead-job read-time check rather than by this call propagating an exception.
    """
    client = get_supabase_client()
    if client is None:
        return
    fields: dict = {"updated_at": datetime.now(UTC).isoformat()}
    if stage is not None:
        fields["stage"] = stage
    if status is not None:
        fields["status"] = status
    if result is not None:
        fields["result"] = result
    if error is not None:
        fields["error"] = error
    try:
        client.table(_JOBS_TABLE).update(fields).eq("id", str(job_id)).execute()
    except Exception:
        logger.warning("Failed to update job %s in Supabase", job_id, exc_info=True)


def get_job(job_id: uuid.UUID) -> dict | None:
    """Return a single job row by id, or None if not found or Supabase isn't configured.

    A job stuck in "running" with no progress in the last 5 minutes (a crashed/restarted
    server orphaning its background task) reads back as "failed" here — a read-time
    transform, not necessarily a rewrite of the stored row.
    """
    client = get_supabase_client()
    if client is None:
        return None
    try:
        response = client.table(_JOBS_TABLE).select("*").eq("id", str(job_id)).limit(1).execute()
    except Exception:
        logger.warning("Failed to read job %s from Supabase", job_id, exc_info=True)
        return None
    if not response.data:
        return None
    return _apply_dead_job_check(response.data[0])


def _apply_dead_job_check(job: dict) -> dict:
    if job["status"] != "running":
        return job
    updated_at = datetime.fromisoformat(job["updated_at"])
    if datetime.now(UTC) - updated_at <= _STALE_AFTER:
        return job
    return {**job, "status": "failed", "error": "Job stalled — no progress reported recently."}
