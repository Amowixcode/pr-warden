from __future__ import annotations

import json
import logging

from llama_index.core.schema import NodeWithScore
from openai import OpenAI

from agents.state import AgentResult, ReviewState
from config.settings import settings
from gh.pr_fetcher import PRData
from gh.repo_fetcher import CommitData, IssueData
from retrieval.context_builder import PRContext, ReviewRecord

logger = logging.getLogger(__name__)

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

Every issue must include an "evidence" field: the exact diff line(s) it refers to, copied \
verbatim from the diff above — not paraphrased, not summarized. Issues whose evidence can't be \
found verbatim in the diff are automatically discarded before you ever see the result, so a \
fabricated or paraphrased quote just wastes the finding — quote precisely or leave it out.

Keep findings terse and bullet-style, never narrative paragraphs. Include a file and line \
number in each issue when the diff makes one determinable (e.g. "gh/client.py:23 — ..."). \
Return at most 3 suggestions — the most important ones only, omit minor nits.

Return ONLY a JSON object with this exact schema — no surrounding text or code fences:
{
  "summary": "<one short sentence; if there are no issues, a single short line like \
'No code-quality concerns found.' — never a justification paragraph>",
  "verdict": "<APPROVE | REQUEST_CHANGES | COMMENT>",
  "issues": [
    {"issue": "<file:line — short, specific code-quality issue>", "evidence": "<the exact \
diff line(s) this refers to, copied verbatim from the diff above>"},
    ...
  ],
  "suggestions": ["<short, specific code-quality improvement suggestion>", ...]
}"""


def _format_nodes(nodes: list[NodeWithScore]) -> str:
    if not nodes:
        return "(none)"
    return "\n\n---\n\n".join(n.node.get_content() for n in nodes)


def _format_commits(commits: list[CommitData]) -> str:
    if not commits:
        return "(none)"
    return "\n".join(f"- {c.message.splitlines()[0]}" for c in commits)


def _format_linked_issues(issues: list[IssueData]) -> str:
    if not issues:
        return "(none)"
    return "\n\n---\n\n".join(f"#{i.number}: {i.title}\n{i.body}" for i in issues)


def _format_prior_review(prior_review: ReviewRecord | None) -> str:
    if prior_review is None:
        return ""
    return f"""
## Incremental Review
This PR was previously reviewed at commit {prior_review.head_sha[:7]}. Prior verdict: \
{prior_review.verdict} — {prior_review.summary}
Only the diff below reflects changes made since that prior review. Focus on what's new; \
don't re-flag concerns that apply equally to the unchanged prior code.
"""


def _build_input(pr: PRData, context: PRContext) -> str:
    """Build the quality-review input from PR data and retrieval context."""
    return f"""\
## Pull Request
Title: {pr.title}
Author: {pr.author}
Branch: {pr.head_branch} → {pr.base_branch}

### Description
{pr.body}

### Commit Messages
{_format_commits(pr.commits)}

### Diff
{pr.diff}
{_format_prior_review(context.prior_review)}
## Linked Issues
{_format_linked_issues(context.linked_issues)}

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


def _verify_issues(raw_issues: list, diff: str) -> list[str]:
    """Keep only issues whose evidence is a verbatim substring of the diff.

    Mechanical, non-LLM backstop to the prompt's own self-check clause — a plain string
    containment check, not another model call. Each raw issue is expected to be
    {"issue": ..., "evidence": ...}; anything that isn't a dict, or has no/empty evidence, or
    whose evidence can't be found verbatim in the diff, is dropped and logged rather than
    shown to the user (a real LLM won't always perfectly follow the schema, so this fails
    closed instead of raising).
    """
    verified: list[str] = []
    for raw_issue in raw_issues:
        if not isinstance(raw_issue, dict):
            logger.warning("Dropping malformed issue entry (not an object): %r", raw_issue)
            continue
        description = raw_issue.get("issue", "")
        evidence = raw_issue.get("evidence", "")
        if evidence and evidence.strip() in diff:
            verified.append(description)
        else:
            logger.warning(
                "Dropping unverifiable issue — evidence not found verbatim in diff: "
                "issue=%r evidence=%r",
                description,
                evidence,
            )
    return verified


def _parse_response(text: str, diff: str) -> AgentResult:
    """Parse OpenAI response text into an AgentResult, stripping code fences if present.

    Each issue's evidence is mechanically verified against diff before being kept — see
    _verify_issues.
    """
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    data = json.loads(text)
    return AgentResult(
        summary=data["summary"],
        verdict=data["verdict"],
        issues=_verify_issues(data.get("issues", []), diff),
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
    return {"quality_result": _parse_response(response_text, state["pr"].diff)}
