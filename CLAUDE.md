# CLAUDE.md — pr-warden

## What this project is

`pr-warden` is a context-aware PR review CLI built with LangGraph multi-agent orchestration and RAG.
It indexes a GitHub repo's history (issues, commits, merged PRs) into ChromaDB via LlamaIndex,
then runs parallel agents (security, quality, test) backed by OpenAI to review pull requests.

CLI commands:
- `warden ingest <owner/repo>` — index a repo, incremental by default since the last ingest
  (`--full` to ignore ingest history)
- `warden review <owner/repo> <pr_number>` — review a PR, incremental by default since the
  last review (exits non-zero on REQUEST_CHANGES; `--json` for machine-readable output;
  `--full` to ignore review history; `--verbose` to also show per-agent findings, hidden by
  default to avoid duplicating the Final Verdict)
- `warden doctor` — run setup/health checks

## Architecture principle

All business logic lives in `core/`. The CLI and API are thin shells that call core and format output.
Never put logic in `cli/` or `api/`.

```
core/review_service.py   — orchestrates full PR review
core/ingest_service.py   — orchestrates ingestion flow

gh/         — fetch PRs, issues, commits via PyGitHub (renamed from github/ to avoid shadowing PyGitHub's namespace)
ingestion/  — LlamaIndex loaders + ChromaDB embedding
retrieval/  — query ChromaDB for PR context
agents/     — LangGraph agents (security, quality, test, summarizer)
cli/        — Typer CLI, no logic
api/        — FastAPI, no logic (v0.3)
config/     — Pydantic Settings, loads from .env
```

## Stack

- Python 3.11+, managed with `uv`
- LangGraph (agent orchestration)
- LlamaIndex (ingestion + RAG)
- ChromaDB (vector store)
- PyGitHub (GitHub API)
- Typer + Rich (CLI)
- Pydantic Settings (config)
- OpenAI (LLM)

## Development commands

```bash
uv sync                  # install dependencies
uv run pytest            # run tests
uv run warden --help     # test CLI
```

## Git workflow — STRICT RULES

Claude Code may:
- Create feature branches from `dev`: `git checkout -b feature/issue-N-short-name`
- Read git status, log, and diff

Claude Code must NEVER:
- Run `git add`
- Run `git commit` (with or without `--no-verify`)
- Run `git push`
- Use `Co-authored-by` or any commit attribution
- Run `git merge` or `git rebase`

The user stages files, commits and pushes. Claude Code only suggests the message (see below).
This is non-negotiable. The git history must be 100% the user's own work.

## Commit message suggestion

When an issue is done (all quality checks pass), end your final reply with a suggested
commit message the user can copy. Do not commit it yourself.

- Put it in a single fenced code block, nothing else inside the block
- Conventional Commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`
- Subject in imperative mood, lowercase after the prefix, max 72 characters, no period
- Optional body after a blank line: 1 to 4 short bullets on what changed and why
- Last line `Closes #N` when working on issue N
- Write it like a human would: plain wording, no em dashes, no emojis
- No `Co-authored-by`, no "Generated with Claude Code", no links or attribution of any kind

Example:

```
fix: show readable error messages for failed jobs

- map GitHub and OpenAI errors to short user-facing messages
- stop leaking raw exception text into jobs.error

Closes #135
```

## Branch naming

- Feature branches: `feature/issue-N-description` (e.g. `feature/issue-2-github-client`)
- Branch off `dev`, merge back to `dev` via PR
- `main` receives merges from `dev` only at milestone completion

## Code quality

Before considering any task done, run and fix all errors from:

```bash
uv run ruff check .    # lint — fix all reported errors
uv run ruff format .   # format — must produce no changes
uv run pytest          # tests — all must pass
```

All three must exit cleanly with no errors before handing work back to the user.

## Code style

- Type hints on all functions
- Async functions where I/O is involved
- Docstrings on public functions
- No print statements — use Rich console in CLI layer, return data from core layer
- Tests in `tests/unit/` and `tests/integration/`