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

_FIRST_HEAD_SHA = "d" * 40
_SECOND_HEAD_SHA = "e" * 40
_NEW_COMMIT_MARKER = "logging_import_marker_xyz"


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
                "head": {"ref": "feature/retry", "sha": _FIRST_HEAD_SHA},
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
        (
            "GET",
            f"{_REPO_URL}/pulls/7/commits",
        ): (
            {},
            [
                {
                    "sha": _FIRST_HEAD_SHA,
                    "commit": {
                        "message": "Add retry-with-backoff for transient GitHub API errors",
                        "author": {"name": "dave", "date": "2026-02-01T00:00:00Z"},
                    },
                    "html_url": f"{_REPO_URL}/commit/{_FIRST_HEAD_SHA}",
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
    isolated_ingest_history: None,
    isolated_review_history: None,
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

    review_result = runner.invoke(app, ["review", "acme/widgets", "7", "--verbose"])
    # REQUEST_CHANGES must fail a CI step (cli/main.py exits 1), not just print.
    assert review_result.exit_code == 1, review_result.output
    # The merge policy (agents/summarizer.py) must propagate REQUEST_CHANGES since the
    # security agent flagged it, even though quality and test both approved.
    assert "REQUEST_CHANGES" in review_result.output
    assert "Hardcoded GitHub token in gh/client.py" in review_result.output
    assert "Move the token to an environment variable" in review_result.output

    # The CLI must show each agent's own finding, not just the merged verdict — proves the
    # real per-agent AgentResults (not just final_verdict) reach cli/main.py.
    assert "Per-Agent Findings" in review_result.output
    assert "Security" in review_result.output
    assert "Quality" in review_result.output
    assert "Test Coverage" in review_result.output
    assert "Style looks fine." in review_result.output
    assert "Adequately tested." in review_result.output
    assert "Final Verdict" in review_result.output

    # Proves the wiring, not just each layer in isolation: the prompts actually sent to
    # OpenAI (one per specialist agent) must contain the real text of documents ingested into
    # Chroma in the first step and pulled back out by retrieval/query_engine.py in the second.
    assert len(openai_api.responses_requests) == 3, "expected one /responses call per agent"
    prompts = [req["input"] for req in openai_api.responses_requests]
    assert any(_ISSUE_MARKER in prompt for prompt in prompts)
    assert any(_MERGED_PR_MARKER in prompt for prompt in prompts)

    # Second review, simulating a new commit pushed upstream: update the PR's head SHA, its
    # commit list, and register a compare(first_sha, second_sha) response containing only the
    # new commit's change. This proves the incremental path actually narrows what reaches the
    # LLM, not just that a banner gets printed — an automated proxy for the acceptance
    # criteria's manual "push a commit upstream, re-review" test.
    github_api[("GET", f"{_REPO_URL}/pulls/7")] = (
        {},
        {
            "url": f"{_REPO_URL}/pulls/7",
            "number": 7,
            "title": "Add retry logic to GitHub calls",
            "body": "Adds retry-with-backoff for transient GitHub API errors.",
            "state": "open",
            "user": {"login": "dave"},
            "base": {"ref": "main"},
            "head": {"ref": "feature/retry", "sha": _SECOND_HEAD_SHA},
            "created_at": "2026-02-01T00:00:00Z",
            "updated_at": "2026-02-03T00:00:00Z",
        },
    )
    github_api[("GET", f"{_REPO_URL}/pulls/7/commits")] = (
        {},
        [
            {
                "sha": _FIRST_HEAD_SHA,
                "commit": {
                    "message": "Add retry-with-backoff for transient GitHub API errors",
                    "author": {"name": "dave", "date": "2026-02-01T00:00:00Z"},
                },
                "html_url": f"{_REPO_URL}/commit/{_FIRST_HEAD_SHA}",
            },
            {
                "sha": _SECOND_HEAD_SHA,
                "commit": {
                    "message": "Add logging around retry attempts",
                    "author": {"name": "dave", "date": "2026-02-03T00:00:00Z"},
                },
                "html_url": f"{_REPO_URL}/commit/{_SECOND_HEAD_SHA}",
            },
        ],
    )
    github_api[("GET", f"{_REPO_URL}/compare/{_FIRST_HEAD_SHA}...{_SECOND_HEAD_SHA}")] = (
        {},
        {
            "files": [
                {
                    "filename": "gh/client.py",
                    "status": "modified",
                    "additions": 2,
                    "deletions": 0,
                    "patch": f"@@ -10,0 +11,2 @@\n+import logging  # {_NEW_COMMIT_MARKER}\n"
                    "+logger = logging.getLogger(__name__)",
                }
            ]
        },
    )

    second_review_result = runner.invoke(app, ["review", "acme/widgets", "7"])
    assert second_review_result.exit_code == 1, second_review_result.output
    assert "Incremental review" in second_review_result.output

    new_prompts = [req["input"] for req in openai_api.responses_requests[3:]]
    assert len(new_prompts) == 3, "expected one more /responses call per agent"
    assert any(_NEW_COMMIT_MARKER in prompt for prompt in new_prompts)
    assert not any("GithubRetry" in prompt for prompt in new_prompts)
