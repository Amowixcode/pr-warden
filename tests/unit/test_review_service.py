from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from llama_index.core.schema import NodeWithScore, TextNode

from core.review_service import ReviewResult, _build_prompt, _parse_response, review_pr
from gh.pr_fetcher import PRData
from retrieval.context_builder import PRContext

_PATCH = "core.review_service.{}"
_NOW = datetime(2024, 6, 1, tzinfo=UTC)

_VALID_JSON = json.dumps(
    {
        "summary": "Looks good overall.",
        "verdict": "APPROVE",
        "issues": ["Missing type hint on line 5"],
        "suggestions": ["Add a docstring"],
    }
)


def _make_pr(
    number: int = 7,
    title: str = "Fix login bug",
    body: str = "Resolves auth issue.",
    diff: str = "diff --git a/auth.py b/auth.py\n+fix",
) -> PRData:
    return PRData(
        number=number,
        title=title,
        body=body,
        state="open",
        author="dev",
        base_branch="main",
        head_branch="fix/login",
        created_at=_NOW,
        updated_at=_NOW,
        changed_files=[],
        diff=diff,
    )


def _make_node(text: str) -> NodeWithScore:
    return NodeWithScore(node=TextNode(text=text), score=0.9)


def _make_context(
    issues: list[str] | None = None,
    prs: list[str] | None = None,
    commits: list[str] | None = None,
) -> PRContext:
    return PRContext(
        similar_issues=[_make_node(t) for t in (issues or [])],
        similar_prs=[_make_node(t) for t in (prs or [])],
        related_commits=[_make_node(t) for t in (commits or [])],
    )


def _make_patches(pr: PRData, context: PRContext, openai_json: str = _VALID_JSON) -> dict:
    return {
        "fetch_pull_request": AsyncMock(return_value=pr),
        "build_pr_context": AsyncMock(return_value=context),
        "build_chroma_collection": MagicMock(return_value=MagicMock()),
        "build_vector_store_index": MagicMock(return_value=MagicMock()),
        "get_embed_model": MagicMock(return_value=MagicMock()),
        "_call_openai": MagicMock(return_value=openai_json),
        "GitHubClient": MagicMock(),
    }


def _apply(mocks: dict):
    return (
        patch(_PATCH.format("fetch_pull_request"), mocks["fetch_pull_request"]),
        patch(_PATCH.format("build_pr_context"), mocks["build_pr_context"]),
        patch(_PATCH.format("build_chroma_collection"), mocks["build_chroma_collection"]),
        patch(_PATCH.format("build_vector_store_index"), mocks["build_vector_store_index"]),
        patch(_PATCH.format("get_embed_model"), mocks["get_embed_model"]),
        patch(_PATCH.format("_call_openai"), mocks["_call_openai"]),
        patch(_PATCH.format("GitHubClient"), mocks["GitHubClient"]),
    )


# ── review_pr orchestration ──────────────────────────────────────────────────


async def test_review_pr_returns_review_result() -> None:
    pr = _make_pr()
    mocks = _make_patches(pr, _make_context())

    with (
        _apply(mocks)[0],
        _apply(mocks)[1],
        _apply(mocks)[2],
        _apply(mocks)[3],
        _apply(mocks)[4],
        _apply(mocks)[5],
        _apply(mocks)[6],
    ):
        result = await review_pr("owner", "repo", 7)

    assert isinstance(result, ReviewResult)


async def test_review_pr_pr_number_matches_input() -> None:
    pr = _make_pr(number=42)
    mocks = _make_patches(pr, _make_context())

    with (
        _apply(mocks)[0],
        _apply(mocks)[1],
        _apply(mocks)[2],
        _apply(mocks)[3],
        _apply(mocks)[4],
        _apply(mocks)[5],
        _apply(mocks)[6],
    ):
        result = await review_pr("owner", "repo", 42)

    assert result.pr_number == 42


async def test_review_pr_fields_from_openai_json() -> None:
    pr = _make_pr()
    mocks = _make_patches(pr, _make_context())

    with (
        _apply(mocks)[0],
        _apply(mocks)[1],
        _apply(mocks)[2],
        _apply(mocks)[3],
        _apply(mocks)[4],
        _apply(mocks)[5],
        _apply(mocks)[6],
    ):
        result = await review_pr("owner", "repo", 7)

    assert result.summary == "Looks good overall."
    assert result.verdict == "APPROVE"
    assert result.issues == ["Missing type hint on line 5"]
    assert result.suggestions == ["Add a docstring"]


async def test_review_pr_prompt_contains_title() -> None:
    pr = _make_pr(title="Unique PR title XYZ")
    mocks = _make_patches(pr, _make_context())

    with (
        _apply(mocks)[0],
        _apply(mocks)[1],
        _apply(mocks)[2],
        _apply(mocks)[3],
        _apply(mocks)[4],
        _apply(mocks)[5],
        _apply(mocks)[6],
    ):
        await review_pr("owner", "repo", 7)

    prompt = mocks["_call_openai"].call_args.args[0]
    assert "Unique PR title XYZ" in prompt


async def test_review_pr_prompt_contains_diff() -> None:
    pr = _make_pr(diff="unique-diff-marker-abc123")
    mocks = _make_patches(pr, _make_context())

    with (
        _apply(mocks)[0],
        _apply(mocks)[1],
        _apply(mocks)[2],
        _apply(mocks)[3],
        _apply(mocks)[4],
        _apply(mocks)[5],
        _apply(mocks)[6],
    ):
        await review_pr("owner", "repo", 7)

    prompt = mocks["_call_openai"].call_args.args[0]
    assert "unique-diff-marker-abc123" in prompt


# ── _build_prompt ────────────────────────────────────────────────────────────


def test_build_prompt_contains_title() -> None:
    pr = _make_pr(title="My Special PR")
    ctx = _make_context()
    assert "My Special PR" in _build_prompt(pr, ctx)


def test_build_prompt_contains_diff() -> None:
    pr = _make_pr(diff="--- a/foo.py\n+++ b/foo.py")
    ctx = _make_context()
    assert "--- a/foo.py" in _build_prompt(pr, ctx)


def test_build_prompt_contains_issue_node_text() -> None:
    pr = _make_pr()
    ctx = _make_context(issues=["Issue #1: Login fails on Safari"])
    assert "Login fails on Safari" in _build_prompt(pr, ctx)


def test_build_prompt_contains_pr_node_text() -> None:
    pr = _make_pr()
    ctx = _make_context(prs=["Merged PR #5: Add OAuth flow"])
    assert "Add OAuth flow" in _build_prompt(pr, ctx)


def test_build_prompt_contains_commit_node_text() -> None:
    pr = _make_pr()
    ctx = _make_context(commits=["Commit abc123: Fix null pointer"])
    assert "Fix null pointer" in _build_prompt(pr, ctx)


def test_build_prompt_empty_context_renders_none() -> None:
    pr = _make_pr()
    ctx = _make_context()
    prompt = _build_prompt(pr, ctx)
    assert prompt.count("(none)") == 3


# ── _call_openai ─────────────────────────────────────────────────────────────


def test_call_openai_uses_configured_max_retries() -> None:
    from config.settings import settings
    from core.review_service import _call_openai

    mock_client = MagicMock()
    mock_client.responses.create.return_value = MagicMock(output_text="ok")

    with patch(_PATCH.format("OpenAI"), return_value=mock_client) as mock_openai_cls:
        _call_openai("some prompt")

    mock_openai_cls.assert_called_once_with(
        api_key=settings.openai_api_key, max_retries=settings.openai_max_retries
    )


# ── _parse_response ──────────────────────────────────────────────────────────


def test_parse_response_maps_all_fields() -> None:
    raw = json.dumps(
        {
            "summary": "LGTM",
            "verdict": "REQUEST_CHANGES",
            "issues": ["bug A", "bug B"],
            "suggestions": ["refactor X"],
        }
    )
    result = _parse_response(99, raw)

    assert result.pr_number == 99
    assert result.summary == "LGTM"
    assert result.verdict == "REQUEST_CHANGES"
    assert result.issues == ["bug A", "bug B"]
    assert result.suggestions == ["refactor X"]


def test_parse_response_strips_json_code_fence() -> None:
    raw = "```json\n" + _VALID_JSON + "\n```"
    result = _parse_response(1, raw)
    assert result.verdict == "APPROVE"


def test_parse_response_strips_plain_code_fence() -> None:
    raw = "```\n" + _VALID_JSON + "\n```"
    result = _parse_response(1, raw)
    assert result.verdict == "APPROVE"


def test_parse_response_issues_defaults_to_empty_list() -> None:
    raw = json.dumps({"summary": "ok", "verdict": "APPROVE"})
    result = _parse_response(1, raw)
    assert result.issues == []


def test_parse_response_suggestions_defaults_to_empty_list() -> None:
    raw = json.dumps({"summary": "ok", "verdict": "APPROVE"})
    result = _parse_response(1, raw)
    assert result.suggestions == []
