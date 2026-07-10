from __future__ import annotations

from github import Github, GithubRetry
from github.Repository import Repository


class GitHubClient:
    """Thin wrapper around PyGitHub's Github client.

    Decoupled from config so callers and tests can inject any token/retry directly.
    """

    def __init__(self, token: str, max_retries: int = 3) -> None:
        """Initialise with a GitHub personal access token.

        Args:
            token: A GitHub PAT with at minimum ``repo`` read scope.
            max_retries: Retry budget for transient errors (429/5xx, connection/timeout).
                Passed to PyGitHub's GithubRetry, which also respects Retry-After and
                backs off on primary/secondary rate limits — never retries other 4xx.
        """
        retry = GithubRetry(total=max_retries, backoff_factor=1.0)
        self._github: Github = Github(token, retry=retry)

    def get_repo(self, owner: str, name: str) -> Repository:
        """Return the PyGitHub Repository for owner/name.

        Args:
            owner: GitHub user or organisation name.
            name: Repository name.

        Returns:
            The PyGitHub Repository object for ``{owner}/{name}``.
        """
        return self._github.get_repo(f"{owner}/{name}")

    def ping(self) -> None:
        """Verify the token is valid and the API is reachable.

        Uses GET /rate_limit — a cheap metadata call with no repo access — raising
        GithubException on auth/network failure, same as get_repo.
        """
        self._github.get_rate_limit()
