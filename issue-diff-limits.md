## Description
A single `warden review` call against facebook/react PR #36940 (a large AI chat assistant feature) consumed ~300k OpenAI tokens. Root cause: each of the three agents (security/quality/test) receives the full PR diff and full RAG context independently - effectively 3x the token cost of the milestone 1 single-prompt design - compounded by an unusually large diff with no size limit in place.

## Scope
- Add a configurable max diff size (lines or tokens) to `config/settings.py` (e.g. `max_diff_tokens`)
- When a PR diff exceeds the limit, truncate before sending to agents (e.g. drop generated/lockfile-like files first, then truncate remaining hunks) and surface a clear warning in CLI output ("diff truncated: reviewing N of M files")
- Log/print actual token usage (prompt + completion) per review run so cost is visible instead of discovered by surprise

## Acceptance Criteria
- [ ] Configurable diff size limit in Settings
- [ ] Diffs exceeding the limit are truncated with a visible warning in CLI output, not silently
- [ ] Token usage for a review run is logged/printed
- [ ] Unit test proving truncation triggers above the configured limit
- [ ] Manual re-test against PR #36940 showing meaningfully reduced token usage