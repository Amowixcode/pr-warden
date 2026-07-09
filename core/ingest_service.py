from __future__ import annotations

import asyncio
from dataclasses import dataclass

from config.settings import settings
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


async def ingest_repository(owner: str, repo: str) -> IngestResult:
    """Fetch all repo history, embed, and store in ChromaDB.

    Args:
        owner: GitHub repository owner (user or organisation).
        repo: Repository name.

    Returns:
        IngestResult with counts of newly indexed documents per type.
    """
    client = GitHubClient(settings.github_token, max_retries=settings.github_max_retries)

    issues, prs, commits = await asyncio.gather(
        fetch_issues(client, owner, repo),
        fetch_merged_prs(client, owner, repo),
        fetch_recent_commits(client, owner, repo),
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

    return IngestResult(
        issues_indexed=n_issues,
        prs_indexed=n_prs,
        commits_indexed=n_commits,
        total_newly_indexed=n_issues + n_prs + n_commits,
    )
