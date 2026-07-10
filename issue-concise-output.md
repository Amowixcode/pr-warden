## Description
Multi-agent output currently returns long free-form prose paragraphs per agent, even when there are no issues, and the final verdict panel repeats the full text of all three agents plus every suggestion verbatim. This does not match how real PR-review tools (CodeRabbit, DeepSource, GitHub Copilot PR review) present findings - those are terse, bullet-based, mostly silent when there is nothing to flag, and the summary synthesizes rather than repeats.

## Scope
- Prompt each agent to return structured, short findings (bullet points, ideally file/line-referenced) instead of narrative paragraphs
- When an agent has no issues, render a single line (e.g. "No concerns found"), not a justification paragraph
- Cap suggestions shown per agent (e.g. top 2-3) instead of an exhaustive list
- Summarizer should synthesize a short final verdict (the decision plus the most important cross-agent point(s)), not concatenate all three agents' full text and every suggestion

## Acceptance Criteria
- [ ] Agent prompts updated to request structured, concise findings
- [ ] APPROVE-with-no-issues renders as a single line per agent
- [ ] Suggestions capped to top N per agent
- [ ] Summarizer output is a genuine synthesis, not a concatenation of per-agent text
- [ ] Manual re-test against PR #36940 confirming output is materially shorter and non-redundant