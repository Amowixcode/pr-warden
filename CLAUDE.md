# CLAUDE.md — pr-warden

## What this project is

`pr-warden` is a context-aware PR review CLI built with LangGraph multi-agent orchestration and RAG.
It indexes a GitHub repo's history (issues, commits, merged PRs) into ChromaDB via LlamaIndex,
then runs parallel agents (security, quality, test) backed by OpenAI to review pull requests.

CLI commands:
- `warden ingest <owner/repo>` — index a repo
- `warden review <owner/repo> <pr_number>` — review a PR
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

The user writes all commit messages, stages files, and pushes.
This is non-negotiable. The git history must be 100% the user's own work.

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