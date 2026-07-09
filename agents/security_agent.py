from __future__ import annotations

import json

from llama_index.core.schema import NodeWithScore
from openai import OpenAI

from agents.state import AgentResult, ReviewState
from config.settings import settings
from gh.pr_fetcher import PRData
from retrieval.context_builder import PRContext

_OPENAI_MODEL = "gpt-4.1-mini"

_SYSTEM_PROMPT = """\
You are a security-focused code reviewer. Review the pull request below for SECURITY concerns \
only:
- Hardcoded secrets or credentials
- Injection risks (SQL, command, template, etc.)
- Unsafe deserialization
- Authentication/authorization gaps
- Unsafe or vulnerable dependency usage

Do not comment on code style, performance, or test coverage — that is out of scope for this \
review.

Return ONLY a JSON object with this exact schema — no surrounding text or code fences:
{
  "summary": "<2-3 sentence overview of security-relevant findings, or lack thereof>",
  "verdict": "<APPROVE | REQUEST_CHANGES | COMMENT>",
  "issues": ["<specific security issue found>", ...],
  "suggestions": ["<security improvement suggestion>", ...]
}"""


def _format_nodes(nodes: list[NodeWithScore]) -> str:
    if not nodes:
        return "(none)"
    return "\n\n---\n\n".join(n.node.get_content() for n in nodes)


def _build_input(pr: PRData, context: PRContext) -> str:
    """Build the security-review input from PR data and retrieval context."""
    return f"""\
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
"""


def _call_openai(prompt: str) -> str:
    """Synchronous OpenAI call; LangGraph runs sync nodes in a thread executor automatically."""
    client = OpenAI(api_key=settings.openai_api_key, max_retries=settings.openai_max_retries)
    response = client.responses.create(
        model=_OPENAI_MODEL,
        instructions=_SYSTEM_PROMPT,
        input=prompt,
        store=False,
    )
    return response.output_text


def _parse_response(text: str) -> AgentResult:
    """Parse OpenAI response text into an AgentResult, stripping code fences if present."""
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    data = json.loads(text)
    return AgentResult(
        summary=data["summary"],
        verdict=data["verdict"],
        issues=data.get("issues", []),
        suggestions=data.get("suggestions", []),
    )


def security_agent(state: ReviewState) -> dict[str, AgentResult]:
    """LangGraph node: reviews state['pr'] + state['context'] for security concerns only.

    Returns a partial state update — {"security_result": AgentResult(...)} — and never writes
    to any other ReviewState key, per the "each agent owns its own key" contract in
    agents/README.md. Errors (OpenAIError, json.JSONDecodeError, KeyError) propagate un-wrapped,
    the same convention core/review_service.py::review_pr already follows.
    """
    prompt = _build_input(state["pr"], state["context"])
    response_text = _call_openai(prompt)
    return {"security_result": _parse_response(response_text)}
