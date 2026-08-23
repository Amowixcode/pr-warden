from __future__ import annotations

from unittest.mock import patch

import pytest
from github import GithubException, GithubRetry

from gh.client import GitHubClient


def test_github_client_uses_configured_max_retries() -> None:
    with patch("gh.client.Github") as mock_github_cls:
        GitHubClient("tok", max_retries=5)

    _, kwargs = mock_github_cls.call_args
    retry = kwargs["retry"]
    assert isinstance(retry, GithubRetry)
    assert retry.total == 5


def test_github_client_defaults_to_three_retries() -> None:
    with patch("gh.client.Github") as mock_github_cls:
        GitHubClient("tok")

    _, kwargs = mock_github_cls.call_args
    assert kwargs["retry"].total == 3


def test_github_client_passes_token() -> None:
    with patch("gh.client.Github") as mock_github_cls:
        GitHubClient("my-token")

    args, _ = mock_github_cls.call_args
    assert args[0] == "my-token"


def test_ping_calls_get_rate_limit() -> None:
    with patch("gh.client.Github") as mock_github_cls:
        mock_github = mock_github_cls.return_value
        client = GitHubClient("tok")
        client.ping()

    mock_github.get_rate_limit.assert_called_once_with()


def test_ping_propagates_github_exception() -> None:
    with patch("gh.client.Github") as mock_github_cls:
        mock_github = mock_github_cls.return_value
        mock_github.get_rate_limit.side_effect = GithubException(
            401, {"message": "Bad creds"}, None
        )
        client = GitHubClient("tok")

        with pytest.raises(GithubException):
            client.ping()
