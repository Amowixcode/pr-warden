from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from config.settings import settings
from gh.client import GitHubClient
from gh.pr_fetcher import fetch_open_prs


@dataclass
class OpenPR:
    number: int
    title: str
    author: str
    age_days: int


async def list_open_prs(owner: str, repo: str) -> list[OpenPR]:
    """List open pull requests for a repository, each annotated with its age in days.

    Args:
        owner: GitHub repository owner.
        repo: Repository name.

    Returns:
        Open PRs newest-first, each with a computed age_days — gh/pr_fetcher.py only returns
        the raw created_at timestamp; deriving "how old" is this layer's job.
    """
    client = GitHubClient(settings.github_token, max_retries=settings.github_max_retries)
    prs = await fetch_open_prs(client, owner, repo)
    now = datetime.now(UTC)
    return [
        OpenPR(
            number=pr.number,
            title=pr.title,
            author=pr.author,
            age_days=(now - pr.created_at).days,
        )
        for pr in prs
    ]
