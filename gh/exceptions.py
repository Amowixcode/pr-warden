from __future__ import annotations


class RepoNotFoundError(Exception):
    """A repository fetch returned 404."""


class PRNotFoundError(Exception):
    """A pull request fetch returned 404 (the repo itself resolved fine)."""
