from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from core.supabase_client import get_supabase_client

if TYPE_CHECKING:
    from core.ingest_service import IngestResult
    from retrieval.context_builder import ReviewRecord

logger = logging.getLogger(__name__)

_REVIEWS_TABLE = "reviews"
_INGESTS_TABLE = "ingests"


def save_review(owner: str, repo: str, pr_number: int, record: ReviewRecord) -> None:
    """Insert a review outcome into Supabase, or no-op if Supabase isn't configured.

    Additive to core/review_history.py's local JSON store — never raises, so a Supabase
    outage can't break the CLI's local incremental-review caching.
    """
    client = get_supabase_client()
    if client is None:
        return
    try:
        client.table(_REVIEWS_TABLE).insert(
            {
                "repo": f"{owner}/{repo}",
                "pr_number": pr_number,
                "head_sha": record.head_sha,
                "verdict": record.verdict,
                "summary": record.summary,
                "issues": record.issues,
                "suggestions": record.suggestions,
            }
        ).execute()
    except Exception:
        logger.warning("Failed to write review history to Supabase", exc_info=True)


def save_ingest(owner: str, repo: str, result: IngestResult, last_ingested_at: datetime) -> None:
    """Insert an ingest outcome into Supabase, or no-op if Supabase isn't configured.

    Additive to core/ingest_history.py's local JSON store — never raises, so a Supabase
    outage can't break the CLI's local incremental-ingest caching.
    """
    client = get_supabase_client()
    if client is None:
        return
    try:
        client.table(_INGESTS_TABLE).insert(
            {
                "repo": f"{owner}/{repo}",
                "last_ingested_at": last_ingested_at.isoformat(),
                "issues_count": result.issues_indexed,
                "merged_prs_count": result.prs_indexed,
                "commits_count": result.commits_indexed,
            }
        ).execute()
    except Exception:
        logger.warning("Failed to write ingest history to Supabase", exc_info=True)


def list_reviews(limit: int = 50) -> list[dict]:
    """Return the most recent reviews from Supabase, newest first.

    Returns an empty list if Supabase isn't configured or the query fails — GET /reviews
    degrades to an empty result rather than a 500 on a Supabase hiccup.
    """
    client = get_supabase_client()
    if client is None:
        return []
    try:
        response = (
            client.table(_REVIEWS_TABLE)
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception:
        logger.warning("Failed to read review history from Supabase", exc_info=True)
        return []
    return response.data
