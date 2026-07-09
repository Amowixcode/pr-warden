from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

from llama_index.core.schema import NodeWithScore
from openai import OpenAI

from config.settings import settings
from gh.client import GitHubClient
from gh.pr_fetcher import PRData, fetch_pull_request
from ingestion.embedder import get_embed_model
from ingestion.vector_store import build_chroma_collection, build_vector_store_index
from retrieval.context_builder import PRContext, build_pr_context

_OPENAI_MODEL = "gpt-4.1-mini"


@dataclass
class ReviewResult:
    pr_number: int
    summary: str
    verdict: str  # "APPROVE" | "REQUEST_CHANGES" | "COMMENT"
    issues: list[str]
    suggestions: list[str]


def _format_nodes(nodes: list[NodeWithScore]) -> str:
    if not nodes:
        return "(none)"
    return "\n\n---\n\n".join(n.node.get_content() for n in nodes)


def _build_prompt(pr: PRData, context: PRContext) -> str:
    """Build the OpenAI review prompt from PR data and retrieval context."""
    return f"""\
You are an expert code reviewer. Review the pull request below and return a JSON object.

## Pull Request
Title: {pr.title}
Author: {pr.author}
Branch: {pr.head_branch} → {pr.base_branch}

### Description
{pr.body}

### Diff
{pr.diff}

## Historical Context

### Similar Issues
{_format_nodes(context.similar_issues)}

### Related Merged PRs
{_format_nodes(context.similar_prs)}

### Related Commits
{_format_nodes(context.related_commits)}

## Instructions
Return ONLY a JSON object with this exact schema — no surrounding text or code fences:
{{
  "summary": "<2-3 sentence overview of the PR and its quality>",
  "verdict": "<APPROVE | REQUEST_CHANGES | COMMENT>",
  "issues": ["<specific problem found>", ...],
  "suggestions": ["<improvement suggestion>", ...]
}}
"""


def _call_openai(prompt: str) -> str:
    """Synchronous OpenAI call; run via asyncio.to_thread to avoid blocking."""
    client = OpenAI(api_key=settings.openai_api_key, max_retries=settings.openai_max_retries)
    response = client.responses.create(
        model=_OPENAI_MODEL,
        input=prompt,
        store=False,
    )
    return response.output_text


def _parse_response(pr_number: int, text: str) -> ReviewResult:
    """Parse OpenAI response text into a ReviewResult, stripping code fences if present."""
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    data = json.loads(text)
    return ReviewResult(
        pr_number=pr_number,
        summary=data["summary"],
        verdict=data["verdict"],
        issues=data.get("issues", []),
        suggestions=data.get("suggestions", []),
    )


async def review_pr(owner: str, repo: str, pr_number: int) -> ReviewResult:
    """Fetch a PR, retrieve historical context, and produce a structured review.

    Args:
        owner: GitHub repository owner.
        repo: Repository name.
        pr_number: Pull request number to review.

    Returns:
        A ReviewResult with summary, verdict, issues, and suggestions.
    """
    client = GitHubClient(settings.github_token)
    pr = await fetch_pull_request(client, owner, repo, pr_number)

    collection = build_chroma_collection()
    embed_model = get_embed_model()
    index = build_vector_store_index(collection, embed_model)

    context = await build_pr_context(pr, index, owner, repo)
    prompt = _build_prompt(pr, context)
    response_text = await asyncio.to_thread(_call_openai, prompt)

    return _parse_response(pr.number, response_text)
