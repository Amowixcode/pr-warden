from __future__ import annotations

from gh.exceptions import PRNotFoundError, RepoNotFoundError

_GENERIC = "Something went wrong. Try again."


def user_message(exc: Exception, *, repo: str | None = None, pr_number: int | None = None) -> str:
    """Map an exception to a short, safe message for the end user.

    Never includes `exc`'s own text — the only detail ever surfaced is the repo/PR the caller
    already told the user about, never an exception's internal message (e.g. Supabase's raw
    error strings must never reach the frontend). GitHub/OpenAI SDK exceptions are detected by
    their defining module name, the same way `_ExternalApiErrorMiddleware` in api/main.py does,
    so this module never needs to import those SDKs.

    Args:
        exc: The exception to map.
        repo: The `owner/repo` string the caller was operating on, if known.
        pr_number: The PR number the caller was operating on, if known (review jobs only).

    Returns:
        A short English sentence safe to show directly to a user.
    """
    if isinstance(exc, PRNotFoundError):
        if repo is not None and pr_number is not None:
            return f"PR #{pr_number} does not exist in {repo}."
        return "That pull request does not exist."

    if isinstance(exc, RepoNotFoundError):
        return _repo_not_found_message(repo)

    module = type(exc).__module__

    if module.startswith("github"):
        status = getattr(exc, "status", None)
        if status == 401:
            return "The server's GitHub token is invalid."
        if status in (403, 429):
            return "GitHub rate limit reached. Try again in a few minutes."
        if status == 404:
            return _repo_not_found_message(repo)
        return _GENERIC

    if module.startswith("openai"):
        return "The AI service failed to respond. Try again."

    return _GENERIC


def _repo_not_found_message(repo: str | None) -> str:
    if repo is not None:
        return f"Repository '{repo}' was not found. Check the spelling, or it may be private."
    return "Repository not found. Check the spelling, or it may be private."
