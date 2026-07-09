"""Full ingest -> review flow, mocking only the true external boundaries.

Everything else — gh/, ingestion/, retrieval/, core/, agents/, cli/ — runs its real code,
including real Chroma writes/reads (isolated_chroma fixture points it at tmp_path), real prompt
construction, and the real compiled multi-agent graph (security/quality/test -> summarizer).
This is the only test that proves the layers actually fit together end to end; every other test
mocks each module in isolation from its neighbors.

The security/quality/test agents run concurrently and each sends OpenAI a distinct system
prompt (agents/*_agent.py's `instructions=`), so the mock server routes canned /responses
bodies by matching a unique marker substring in each agent's instructions, not by call order.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

from cli.main import app
from tests.integration.conftest import OpenAIMock

runner = CliRunner()

_REPO_URL = "https://api.github.com/repos/acme/widgets"
_ISSUE_MARKER = "Login fails on Safari"
_MERGED_PR_MARKER = "Add OAuth flow"

_SECURITY_MARKER = "SECURITY concerns"
_QUALITY_MARKER = "CODE QUALITY concerns"
_TEST_MARKER = "TEST ADEQUACY concerns"


def _github_fixtures() -> dict[tuple[str, str], tuple[dict, object]]:
    return {
        ("GET", "/repos/acme/widgets"): ({}, {"url": _REPO_URL, "full_name": "acme/widgets"}),
        (
            "GET",
            f"{_REPO_URL}/issues",
        ): (
            {},
            [
                {
                    "number": 1,
                    "title": _ISSUE_MARKER,
                    "body": "Users can't log in on Safari 17.",
                    "state": "open",
                    "labels": [],
                    "user": {"login": "alice"},
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "closed_at": None,
                    "pull_request": None,
                }
            ],
        ),
        (
            "GET",
            f"{_REPO_URL}/pulls",
        ): (
            {},
            [
                {
                    "number": 2,
                    "title": _MERGED_PR_MARKER,
                    "body": "Implements OAuth2 login.",
                    "user": {"login": "bob"},
                    "base": {"ref": "main"},
                    "head": {"ref": "feature/oauth"},
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "merged_at": "2026-01-02T00:00:00Z",
                }
            ],
        ),
        (
            "GET",
            f"{_REPO_URL}/commits",
        ): (
            {},
            [
                {
                    "sha": "c" * 40,
                    "commit": {
                        "message": "Fix typo in README",
                        "author": {"name": "carol", "date": "2026-01-01T00:00:00Z"},
                    },
                    "html_url": f"{_REPO_URL}/commit/{'c' * 40}",
                }
            ],
        ),
        (
            "GET",
            f"{_REPO_URL}/pulls/7",
        ): (
            {},
            {
                "url": f"{_REPO_URL}/pulls/7",
                "number": 7,
                "title": "Add retry logic to GitHub calls",
                "body": "Adds retry-with-backoff for transient GitHub API errors.",
                "state": "open",
                "user": {"login": "dave"},
                "base": {"ref": "main"},
                "head": {"ref": "feature/retry"},
                "created_at": "2026-02-01T00:00:00Z",
                "updated_at": "2026-02-02T00:00:00Z",
            },
        ),
        (
            "GET",
            f"{_REPO_URL}/pulls/7/files",
        ): (
            {},
            [
                {
                    "filename": "gh/client.py",
                    "status": "modified",
                    "additions": 8,
                    "deletions": 2,
                    "patch": "@@ -1,3 +1,9 @@\n+from github import GithubRetry\n ...",
                }
            ],
        ),
    }


def _agent_response_body(
    verdict: str, summary: str, issues: list[str], suggestions: list[str]
) -> dict:
    output_text = json.dumps(
        {"summary": summary, "verdict": verdict, "issues": issues, "suggestions": suggestions}
    )
    return {
        "id": "resp_test123",
        "created_at": 1751980800,
        "model": "gpt-4.1-mini",
        "object": "response",
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "tools": [],
        "output": [
            {
                "id": "msg_test123",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": output_text, "annotations": []}],
            }
        ],
    }


def test_ingest_then_review_full_flow(
    github_api: dict[tuple[str, str], tuple[dict, object]],
    openai_api: OpenAIMock,
    isolated_chroma: None,
) -> None:
    github_api.update(_github_fixtures())

    openai_api.set_responses_body_for(
        _SECURITY_MARKER,
        _agent_response_body(
            verdict="REQUEST_CHANGES",
            summary="Found a hardcoded token.",
            issues=["Hardcoded GitHub token in gh/client.py"],
            suggestions=["Move the token to an environment variable"],
        ),
    )
    openai_api.set_responses_body_for(
        _QUALITY_MARKER,
        _agent_response_body(
            verdict="APPROVE", summary="Style looks fine.", issues=[], suggestions=[]
        ),
    )
    openai_api.set_responses_body_for(
        _TEST_MARKER,
        _agent_response_body(
            verdict="APPROVE", summary="Adequately tested.", issues=[], suggestions=[]
        ),
    )

    ingest_result = runner.invoke(app, ["ingest", "acme/widgets"])
    assert ingest_result.exit_code == 0, ingest_result.output
    assert "Issues" in ingest_result.output
    assert "Merged PRs" in ingest_result.output
    assert "Commits" in ingest_result.output
    assert "3" in ingest_result.output  # total newly indexed: 1 issue + 1 PR + 1 commit

    review_result = runner.invoke(app, ["review", "acme/widgets", "7"])
    assert review_result.exit_code == 0, review_result.output
    # The merge policy (agents/summarizer.py) must propagate REQUEST_CHANGES since the
    # security agent flagged it, even though quality and test both approved.
    assert "REQUEST_CHANGES" in review_result.output
    assert "Hardcoded GitHub token in gh/client.py" in review_result.output
    assert "Move the token to an environment variable" in review_result.output

    # Proves the wiring, not just each layer in isolation: the prompts actually sent to
    # OpenAI (one per specialist agent) must contain the real text of documents ingested into
    # Chroma in the first step and pulled back out by retrieval/query_engine.py in the second.
    assert len(openai_api.responses_requests) == 3, "expected one /responses call per agent"
    prompts = [req["input"] for req in openai_api.responses_requests]
    assert any(_ISSUE_MARKER in prompt for prompt in prompts)
    assert any(_MERGED_PR_MARKER in prompt for prompt in prompts)
