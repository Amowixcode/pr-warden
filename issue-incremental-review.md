## Description
`warden review` currently performs a full review from scratch every time it runs against a PR, even if the PR has already been reviewed and only a few new commits were pushed since. Real PR-review tools (CodeRabbit and others) support incremental/differential re-review: only reviewing what changed since the last review, instead of redoing the whole PR each time.

## Scope
- Track the last-reviewed commit SHA for a given PR (persisted locally, keyed by owner/repo/PR number)
- On a subsequent `warden review` call for the same PR, if a prior review exists, compute the diff between the last-reviewed SHA and the current HEAD, and pass only that incremental diff to the agents (plus enough surrounding context to stay coherent)
- Clearly indicate in the output that this is an incremental review, referencing the prior verdict for context
- Provide a `--full` flag to force a complete re-review regardless of history

## Acceptance Criteria
- [ ] Last-reviewed commit SHA is persisted per PR (owner/repo/PR number)
- [ ] Subsequent reviews of the same PR use the incremental diff since the last reviewed SHA, when available
- [ ] `--full` flag forces a complete review ignoring history
- [ ] Unit tests covering: first review (no history, full review), second review (incremental), `--full` override
- [ ] Manual test: review a PR, push a small additional commit upstream, re-review, and confirm only the new change is analyzed