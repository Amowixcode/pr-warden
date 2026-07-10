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
You are a code-quality-focused code reviewer. Review the pull request below for CODE QUALITY \
concerns only:
- Style and readability
- Maintainability and unnecessary complexity
- Naming (variables, functions, classes)
- Documentation and type-annotation conventions — but only as they apply to the language and \
ecosystem the diff is actually written in. Infer the language from the file extensions and \
syntax in the diff itself, and judge it against that language's own conventions (e.g. \
docstrings and type hints for Python, JSDoc/TSDoc for JavaScript/TypeScript, doc comments for \
Go, rustdoc for Rust). Never assume Python conventions apply to non-Python code, and never \
invent a convention the language/ecosystem doesn't use.

Do not comment on security or test coverage — that is out of scope for this review.

Before including any issue that makes a specific, checkable claim about a code construct \
(e.g. "X is missing a type annotation" or "Y has no docstring"), re-read the exact diff \
line(s) for that construct and confirm the claim is true. If you cannot point to the specific \
line(s) that support the claim, drop it or soften it into a general observation instead.

Keep findings terse and bullet-style, never narrative paragraphs. Include a file and line \
number in each issue when the diff makes one determinable (e.g. "gh/client.py:23 — ..."). \
Return at most 3 suggestions — the most important ones only, omit minor nits.

Return ONLY a JSON object with this exact schema — no surrounding text or code fences:
{
  "summary": "<one short sentence; if there are no issues, a single short line like \
'No code-quality concerns found.' — never a justification paragraph>",
  "verdict": "<APPROVE | REQUEST_CHANGES | COMMENT>",
  "issues": ["<file:line — short, specific code-quality issue>", ...],
  "suggestions": ["<short, specific code-quality improvement suggestion>", ...]
}"""


def _format_nodes(nodes: list[NodeWithScore]) -> str:
    if not nodes:
        return "(none)"
    return "\n\n---\n\n".join(n.node.get_content() for n in nodes)


def _build_input(pr: PRData, context: PRContext) -> str:
    """Build the quality-review input from PR data and retrieval context."""
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


def quality_agent(state: ReviewState) -> dict[str, AgentResult]:
    """LangGraph node: reviews state['pr'] + state['context'] for code-quality concerns only.

    Returns a partial state update — {"quality_result": AgentResult(...)} — and never writes
    to any other ReviewState key, per the "each agent owns its own key" contract in
    agents/README.md. Errors (OpenAIError, json.JSONDecodeError, KeyError) propagate un-wrapped,
    the same convention core/review_service.py::review_pr already follows.
    """
    prompt = _build_input(state["pr"], state["context"])
    response_text = _call_openai(prompt)
    return {"quality_result": _parse_response(response_text)}
