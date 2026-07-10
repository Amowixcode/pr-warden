# pr-warden

[![CI](https://github.com/Amowixcode/pr-warden/actions/workflows/ci.yml/badge.svg)](https://github.com/Amowixcode/pr-warden/actions/workflows/ci.yml)

Context-aware PR review CLI built with LangGraph multi-agent orchestration and RAG. Indexes a
GitHub repo's history (issues, merged PRs, commits) into ChromaDB, then reviews pull requests
with three specialist OpenAI-backed agents — security, quality, and test coverage — running in
parallel and merged into one verdict.

## Usage

```bash
warden ingest owner/repo             # index a repo's issues, merged PRs, and commits into ChromaDB
warden review owner/repo 123         # review PR #123 with full historical context
warden review owner/repo 123 --json  # same review as machine-readable JSON, for CI/tooling
warden doctor                        # run setup/health checks (GitHub token, OpenAI key, ChromaDB)
```

## How a review works

1. `warden ingest` pulls issues, merged PRs, and commits from GitHub and embeds them into
   ChromaDB.
2. `warden review` fetches the target PR, retrieves related historical context, then runs three
   specialist agents in parallel, each backed by its own OpenAI call:
   - **Security** — hardcoded secrets/credentials, injection risks, unsafe deserialization,
     authentication/authorization gaps, unsafe or vulnerable dependency usage.
   - **Quality** — style and readability, maintainability, naming, unnecessary complexity,
     adherence to project conventions (type hints, docstrings, async I/O).
   - **Test coverage** — whether new or changed logic has corresponding tests, whether edge
     cases are considered, whether existing tests were updated when the behavior they cover
     changed.
3. A summarizer merges the three findings into one final verdict: `REQUEST_CHANGES` if any agent
   flagged an issue, else `COMMENT` if any agent had a non-blocking issue, else `APPROVE`.

See [`agents/README.md`](agents/README.md) for the full graph design and merge policy contract.

## Output format

`warden review` prints a **Per-Agent Findings** section — one panel per agent, each with its own
verdict, issues, and suggestions — followed by a **Final Verdict** section with the merged
result for the PR as a whole. Pass `--json` to print that same information as a single JSON
document on stdout instead (nothing else is printed, so it pipes cleanly into `jq` or other
tooling).

`warden review` exits non-zero (`1`) when the final verdict is `REQUEST_CHANGES`, and `0` for
`APPROVE`/`COMMENT` — so it can gate a CI step on the review outcome.
