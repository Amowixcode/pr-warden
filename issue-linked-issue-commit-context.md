## Description
`warden review` currently builds review context from the PR diff plus RAG-retrieved historical context, but does not look at the PR's own commit messages or any issue it references (e.g. "Fixes #N" in the PR description). This context is exactly the "why" a human reviewer relies on, and matches how real tools like CodeRabbit read project-management context (Jira/Linear tickets) rather than just the diff.

## Scope
- Parse the PR description for linked issue references (e.g. `Fixes #N`, `Closes #N`, `Resolves #N`) and fetch that issue's title/body via `gh/` for inclusion in the agent context
- Include the PR's own commit messages (from `gh/pr_fetcher.py`'s commit list) in the context passed to agents, not just the final squashed diff
- Keep this additive to the existing RAG-retrieved historical context, not a replacement

## Acceptance Criteria
- [ ] PR description is parsed for `Fixes|Closes|Resolves #N` patterns (case-insensitive), matching GitHub's own linking keywords
- [ ] Linked issue content (if found and fetchable) is included in the context built for agents
- [ ] PR's own commit messages are included in the context
- [ ] Unit tests covering: PR with a linked issue, PR with no linked issue, PR with commit messages of varying quality
- [ ] Manual re-test against a PR with a "Fixes #N" reference (e.g. facebook/react PR #36947, which references #27670) confirming the issue content shows up in context/influences the review