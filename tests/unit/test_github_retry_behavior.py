"""Proves the retry-with-backoff behavior our GithubRetry(total=...) configuration relies on.

These call the real `github.GithubRetry.increment()` against real `urllib3.response.HTTPResponse`
objects (constructed in-process, no socket needed) — no mocking of GithubRetry itself, so the
actual production code path (body parsing, rate-limit message matching, backoff computation,
exception raising) executes for real.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta

import pytest
from github import GithubException, GithubRetry
from urllib3.exceptions import MaxRetryError
from urllib3.response import HTTPResponse

_URL = "https://api.github.com/repos/owner/repo"


def _response(
    status: int,
    reason: str = "",
    headers: dict[str, str] | None = None,
    body: bytes = b"",
) -> HTTPResponse:
    # preload_content=False + a file-like body: GithubRetry.get_content() reads the body via
    # requests.Response.content, which streams from response.raw — that requires a real file-like
    # `_fp`, not a preloaded bytes buffer (HTTPResponse.stream() can't work without one).
    return HTTPResponse(
        body=io.BytesIO(body),
        headers=headers or {},
        status=status,
        reason=reason,
        preload_content=False,
    )


# ── status_forcelist ─────────────────────────────────────────────────────────


def test_status_forcelist_includes_403_and_5xx() -> None:
    forcelist = GithubRetry().status_forcelist
    assert 403 in forcelist
    assert 500 in forcelist
    assert 599 in forcelist


def test_status_forcelist_excludes_other_4xx() -> None:
    forcelist = GithubRetry().status_forcelist
    assert 400 not in forcelist
    assert 401 not in forcelist
    assert 404 not in forcelist
    assert 422 not in forcelist


# ── plain 5xx retries ────────────────────────────────────────────────────────


def test_5xx_response_is_retried() -> None:
    retry = GithubRetry(total=2)
    response = _response(500, reason="Internal Server Error")

    new_retry = retry.increment(method="GET", url=_URL, response=response)

    assert new_retry.total == 1


def test_5xx_retries_exhausted_raises_max_retry_error() -> None:
    retry = GithubRetry(total=0)
    response = _response(500, reason="Internal Server Error")

    with pytest.raises(MaxRetryError):
        retry.increment(method="GET", url=_URL, response=response)


# ── 403 with Retry-After header ──────────────────────────────────────────────


def test_403_with_retry_after_header_is_retried() -> None:
    retry = GithubRetry(total=2)
    response = _response(403, reason="Forbidden", headers={"Retry-After": "30"})

    new_retry = retry.increment(method="GET", url=_URL, response=response)

    assert new_retry.total == 1


# ── 403 primary rate limit (no Retry-After header) ───────────────────────────


def test_403_primary_rate_limit_backs_off_until_reset() -> None:
    retry = GithubRetry(total=2)
    reset_at = datetime.now(UTC) + timedelta(seconds=90)
    body = b'{"message": "API rate limit exceeded for user ID 123."}'
    response = _response(
        403,
        reason="Forbidden",
        headers={"X-RateLimit-Reset": str(int(reset_at.timestamp()))},
        body=body,
    )

    new_retry = retry.increment(method="GET", url=_URL, response=response)

    # backoff = seconds-until-reset + 1s; allow a few seconds of test-runtime slack.
    assert 85 <= new_retry.get_backoff_time() <= 95


# ── 403 secondary rate limit (no Retry-After header) ─────────────────────────


def test_403_secondary_rate_limit_backs_off_default_wait() -> None:
    retry = GithubRetry(total=2)
    body = (
        b'{"message": "You have exceeded a secondary rate limit. '
        b'Please wait a few minutes before you try again."}'
    )
    response = _response(403, reason="Forbidden", body=body)

    new_retry = retry.increment(method="GET", url=_URL, response=response)

    assert new_retry.get_backoff_time() == 60


# ── 403 that is not rate-limit-flavored ──────────────────────────────────────


def test_403_non_rate_limit_body_raises_immediately() -> None:
    retry = GithubRetry(total=2)
    body = b'{"message": "Forbidden"}'
    response = _response(403, reason="Forbidden", body=body)

    with pytest.raises(GithubException):
        retry.increment(method="GET", url=_URL, response=response)
