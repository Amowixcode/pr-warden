from __future__ import annotations

import asyncio
import re
from datetime import datetime

from github import GithubException
from pydantic import BaseModel, Field

from gh.client import GitHubClient
from gh.repo_fetcher import CommitData, IssueData

_LINKED_ISSUE_PATTERN = re.compile(r"\b(?:fixes|closes|resolves)\s+#(\d+)\b", re.IGNORECASE)


class PRFile(BaseModel):
    """A single file changed within a pull request."""

    filename: str
    status: str
    additions: int
    deletions: int
    patch: str | None = None


class PRData(BaseModel):
    """Full snapshot of a pull request, including per-file change data."""

    number: int
    title: str
    body: str
    state: str
    author: str
    base_branch: str
    head_branch: str
    created_at: datetime
    updated_at: datetime
    changed_files: list[PRFile]
    diff: str
    commits: list[CommitData] = Field(default_factory=list)


def _build_diff(pr_files: list[PRFile]) -> str:
    """Assemble a combined diff string from per-file patch content.

    Binary files (``patch=None``) are skipped — they appear in
    ``changed_files`` but contribute nothing to the diff string.

    Args:
        pr_files: Processed PRFile objects.

    Returns:
        A string with one ``diff --git`` header block per text file.
    """
    parts: list[str] = []
    for f in pr_files:
        if f.patch is not None:
            parts.append(f"diff --git a/{f.filename} b/{f.filename}")
            parts.append(f.patch)
    return "\n".join(parts)


async def fetch_pull_request(
    client: GitHubClient,
    owner: str,
    name: str,
    pr_number: int,
) -> PRData:
    """Fetch a pull request and all its file changes from GitHub.

    PyGitHub is synchronous, including ``PaginatedList`` iteration when
    calling ``pr.get_files()``. The entire fetch is wrapped in a single
    ``asyncio.to_thread`` closure so the event loop is never blocked and
    pagination is exhausted inside the worker thread.

    Args:
        client: An initialised GitHubClient.
        owner: GitHub user or organisation owning the repository.
        name: Repository name.
        pr_number: Pull request number.

    Returns:
        A fully populated PRData model.
    """

    def _fetch_sync() -> PRData:
        repo = client.get_repo(owner, name)
        pr = repo.get_pull(pr_number)
        raw_files = list(pr.get_files())
        raw_commits = list(pr.get_commits())

        changed_files = [
            PRFile(
                filename=f.filename,
                status=f.status,
                additions=f.additions,
                deletions=f.deletions,
                patch=f.patch,
            )
            for f in raw_files
        ]

        commits = [
            CommitData(
                sha=c.sha,
                message=c.commit.message or "",
                author=c.commit.author.name or "",
                committed_at=c.commit.author.date,
                url=c.html_url,
            )
            for c in raw_commits
        ]

        return PRData(
            number=pr.number,
            title=pr.title,
            body=pr.body or "",
            state=pr.state,
            author=pr.user.login,
            base_branch=pr.base.ref,
            head_branch=pr.head.ref,
            created_at=pr.created_at,
            updated_at=pr.updated_at,
            changed_files=changed_files,
            diff=_build_diff(changed_files),
            commits=commits,
        )

    return await asyncio.to_thread(_fetch_sync)


def parse_linked_issue_numbers(body: str) -> list[int]:
    """Extract issue numbers referenced via GitHub's Fixes/Closes/Resolves #N linking syntax.

    Case-insensitive, matching GitHub's own PR-closing keywords. Returns numbers in
    first-appearance order, deduplicated.

    Args:
        body: The PR description text.

    Returns:
        Referenced issue numbers, in order of first appearance.
    """
    seen: dict[int, None] = {}
    for match in _LINKED_ISSUE_PATTERN.finditer(body):
        seen.setdefault(int(match.group(1)), None)
    return list(seen)


async def fetch_linked_issues(
    client: GitHubClient,
    owner: str,
    name: str,
    body: str,
) -> list[IssueData]:
    """Fetch the issues referenced by Fixes/Closes/Resolves #N in a PR description.

    Best-effort: a referenced number that doesn't resolve to an accessible issue (deleted,
    private, or actually a pull request number) is silently skipped rather than failing the
    whole review — the PR's own diff and commits remain the primary review material regardless.

    Args:
        client: An initialised GitHubClient.
        owner: GitHub user or organisation owning the repository.
        name: Repository name.
        body: The PR description text to parse for linked issue references.

    Returns:
        IssueData for each linked issue that was found and fetchable.
    """
    numbers = parse_linked_issue_numbers(body)
    if not numbers:
        return []

    def _fetch_sync() -> list[IssueData]:
        repo = client.get_repo(owner, name)
        results: list[IssueData] = []
        for number in numbers:
            try:
                issue = repo.get_issue(number)
            except GithubException:
                continue
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
        return results

    return await asyncio.to_thread(_fetch_sync)
