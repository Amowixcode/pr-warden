from __future__ import annotations

import asyncio
from datetime import datetime

from pydantic import BaseModel

from gh.client import GitHubClient


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
        )

    return await asyncio.to_thread(_fetch_sync)
