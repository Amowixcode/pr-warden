from __future__ import annotations

from github import GithubException
from openai import OpenAIError

from core.errors import user_message
from gh.exceptions import PRNotFoundError, RepoNotFoundError


def test_pr_not_found_with_context() -> None:
    message = user_message(PRNotFoundError(), repo="octocat/Hello-World", pr_number=7)

    assert message == "PR #7 does not exist in octocat/Hello-World."


def test_pr_not_found_without_context() -> None:
    message = user_message(PRNotFoundError())

    assert message == "That pull request does not exist."


def test_repo_not_found_with_context() -> None:
    message = user_message(RepoNotFoundError(), repo="octocat/Hello-World")

    assert message == (
        "Repository 'octocat/Hello-World' was not found. Check the spelling, or it may be private."
    )


def test_repo_not_found_without_context() -> None:
    message = user_message(RepoNotFoundError())

    assert message == "Repository not found. Check the spelling, or it may be private."


def test_github_401_is_invalid_token() -> None:
    exc = GithubException(401, {"message": "Bad credentials"}, None)

    assert user_message(exc) == "The server's GitHub token is invalid."


def test_github_403_is_rate_limit() -> None:
    exc = GithubException(403, {"message": "API rate limit exceeded"}, None)

    assert user_message(exc) == "GitHub rate limit reached. Try again in a few minutes."


def test_github_429_is_rate_limit() -> None:
    exc = GithubException(429, {"message": "Too Many Requests"}, None)

    assert user_message(exc) == "GitHub rate limit reached. Try again in a few minutes."


def test_github_404_untagged_falls_back_to_repo_not_found() -> None:
    exc = GithubException(404, {"message": "Not Found"}, None)

    assert user_message(exc, repo="octocat/Hello-World") == (
        "Repository 'octocat/Hello-World' was not found. Check the spelling, or it may be private."
    )


def test_github_other_status_is_generic() -> None:
    exc = GithubException(500, {"message": "Internal Server Error"}, None)

    assert user_message(exc) == "Something went wrong. Try again."


def test_openai_error_is_generic_ai_message() -> None:
    exc = OpenAIError("rate limited")

    assert user_message(exc) == "The AI service failed to respond. Try again."


def test_unmapped_exception_is_generic_and_does_not_leak_text() -> None:
    exc = RuntimeError("permission denied for table jobs")

    message = user_message(exc)

    assert message == "Something went wrong. Try again."
    assert "permission denied" not in message
