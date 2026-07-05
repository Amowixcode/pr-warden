from __future__ import annotations

import asyncio
import itertools
from datetime import datetime

from pydantic import BaseModel

from gh.client import GitHubClient


class IssueData(BaseModel):
    """A GitHub issue (excludes pull requests)."""

    number: int
    title: str
    body: str
    state: str
    labels: list[str]
    author: str
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None


class MergedPRData(BaseModel):
    """Lightweight snapshot of a merged pull request for historical context."""

    number: int
    title: str
    body: str
    author: str
    base_branch: str
    head_branch: str
    merged_at: datetime


class CommitData(BaseModel):
    """A single commit from the repository history."""

    sha: str
    message: str
    author: str
    committed_at: datetime
    url: str


async def fetch_issues(
    client: GitHubClient,
    owner: str,
    name: str,
    state: str = "all",
    limit: int = 100,
) -> list[IssueData]:
    """Fetch issues from a repository, excluding pull requests.

    GitHub's issues API returns both issues and pull requests; this function
    filters out any item that has an associated pull request.

    Args:
        client: An initialised GitHubClient.
        owner: GitHub user or organisation owning the repository.
        name: Repository name.
        state: Issue state filter — ``"open"``, ``"closed"``, or ``"all"``.
        limit: Maximum number of issues to return.

    Returns:
        A list of IssueData objects, capped at ``limit``.
    """

    def _fetch_sync() -> list[IssueData]:
        repo = client.get_repo(owner, name)
        raw = repo.get_issues(state=state)
        results: list[IssueData] = []
        for issue in itertools.islice(raw, limit * 2):  # over-fetch to account for filtered PRs
            if issue.pull_request is not None:
                continue
            results.append(
                IssueData(
                    number=issue.number,
                    title=issue.title,
                    body=issue.body or "",
                    state=issue.state,
                    labels=[label.name for label in issue.labels],
                    author=issue.user.login,
                    created_at=issue.created_at,
                    updated_at=issue.updated_at,
                    closed_at=issue.closed_at,
                )
            )
            if len(results) >= limit:
                break
        return results

    return await asyncio.to_thread(_fetch_sync)


async def fetch_merged_prs(
    client: GitHubClient,
    owner: str,
    name: str,
    limit: int = 100,
) -> list[MergedPRData]:
    """Fetch merged pull requests for historical context.

    Returns lightweight PR records (no diff, no file list) suitable for
    embedding as context documents.

    Args:
        client: An initialised GitHubClient.
        owner: GitHub user or organisation owning the repository.
        name: Repository name.
        limit: Maximum number of merged PRs to return.

    Returns:
        A list of MergedPRData objects, capped at ``limit``.
    """

    def _fetch_sync() -> list[MergedPRData]:
        repo = client.get_repo(owner, name)
        raw = repo.get_pulls(state="closed")
        results: list[MergedPRData] = []
        for pr in itertools.islice(raw, limit * 2):  # over-fetch to account for unmerged closed PRs
            if pr.merged_at is None:
                continue
            results.append(
                MergedPRData(
                    number=pr.number,
                    title=pr.title,
                    body=pr.body or "",
                    author=pr.user.login,
                    base_branch=pr.base.ref,
                    head_branch=pr.head.ref,
                    merged_at=pr.merged_at,
                )
            )
            if len(results) >= limit:
                break
        return results

    return await asyncio.to_thread(_fetch_sync)


async def fetch_recent_commits(
    client: GitHubClient,
    owner: str,
    name: str,
    limit: int = 200,
) -> list[CommitData]:
    """Fetch the most recent commits from the default branch.

    Commits are returned newest-first by the GitHub API.

    Args:
        client: An initialised GitHubClient.
        owner: GitHub user or organisation owning the repository.
        name: Repository name.
        limit: Maximum number of commits to return.

    Returns:
        A list of CommitData objects, capped at ``limit``.
    """

    def _fetch_sync() -> list[CommitData]:
        repo = client.get_repo(owner, name)
        raw = repo.get_commits()
        results: list[CommitData] = []
        for commit in itertools.islice(raw, limit):
            results.append(
                CommitData(
                    sha=commit.sha,
                    message=commit.commit.message or "",
                    author=commit.commit.author.name or "",
                    committed_at=commit.commit.author.date,
                    url=commit.html_url,
                )
            )
        return results

    return await asyncio.to_thread(_fetch_sync)
