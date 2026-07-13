from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

from config.settings import settings
from core import supabase_history
from core.ingest_history import IngestRecord, load_ingest_record, save_ingest_record
from gh.client import GitHubClient
from gh.repo_fetcher import fetch_issues, fetch_merged_prs, fetch_recent_commits
from ingestion.embedder import get_embed_model
from ingestion.github_loader import (
    commits_to_documents,
    issues_to_documents,
    merged_prs_to_documents,
)
from ingestion.vector_store import (
    build_chroma_collection,
    build_vector_store_index,
    index_documents,
)


@dataclass
class IngestResult:
    issues_indexed: int
    prs_indexed: int
    commits_indexed: int
    total_newly_indexed: int
    incremental: bool = False


async def ingest_repository(owner: str, repo: str, full: bool = False) -> IngestResult:
    """Fetch repo history, embed, and store in ChromaDB.

    Incremental by default: if this repo was ingested before, only issues/PRs/commits
    created or updated since that ingest are fetched — the existing dedup-on-insert in
    ingestion/vector_store.py::index_documents remains as a safety net regardless. Pass
    full=True to ignore history and always do a complete re-fetch.

    Args:
        owner: GitHub repository owner (user or organisation).
        repo: Repository name.
        full: Force a complete re-ingestion, ignoring any prior ingest history.

    Returns:
        IngestResult with counts of newly indexed documents per type.
    """
    client = GitHubClient(settings.github_token, max_retries=settings.github_max_retries)

    run_started_at = datetime.now(UTC)
    prior_record = None if full else load_ingest_record(owner, repo)
    since = prior_record.last_ingested_at if prior_record else None

    issues, prs, commits = await asyncio.gather(
        fetch_issues(client, owner, repo, since=since),
        fetch_merged_prs(client, owner, repo, since=since),
        fetch_recent_commits(client, owner, repo, since=since),
    )

    issue_docs = issues_to_documents(issues, owner, repo)
    pr_docs = merged_prs_to_documents(prs, owner, repo)
    commit_docs = commits_to_documents(commits, owner, repo)

    collection = build_chroma_collection()
    embed_model = get_embed_model()
    index = build_vector_store_index(collection, embed_model)

    n_issues = await index_documents(issue_docs, index, collection)
    n_prs = await index_documents(pr_docs, index, collection)
    n_commits = await index_documents(commit_docs, index, collection)

    save_ingest_record(owner, repo, IngestRecord(last_ingested_at=run_started_at))

    result = IngestResult(
        issues_indexed=n_issues,
        prs_indexed=n_prs,
        commits_indexed=n_commits,
        total_newly_indexed=n_issues + n_prs + n_commits,
        incremental=prior_record is not None,
    )
    await asyncio.to_thread(supabase_history.save_ingest, owner, repo, result, run_started_at)

    return result
