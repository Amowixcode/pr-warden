from __future__ import annotations

from github import Github
from github.Repository import Repository


class GitHubClient:
    """Thin wrapper around PyGitHub's Github client.

    Decoupled from config so callers and tests can inject any token directly.
    """

    def __init__(self, token: str) -> None:
        """Initialise with a GitHub personal access token.

        Args:
            token: A GitHub PAT with at minimum ``repo`` read scope.
        """
        self._github: Github = Github(token)

    def get_repo(self, owner: str, name: str) -> Repository:
        """Return the PyGitHub Repository for owner/name.

        Args:
            owner: GitHub user or organisation name.
            name: Repository name.

        Returns:
            The PyGitHub Repository object for ``{owner}/{name}``.
        """
        return self._github.get_repo(f"{owner}/{name}")
