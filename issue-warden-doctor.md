## Description
Diagnosing a broken setup (missing/invalid env vars, unreachable GitHub/OpenAI/ChromaDB) currently means reading a raw Pydantic ValidationError or a generic API error. A `doctor` command, following the pattern of `gh auth status` / `aws configure list` / CodeRabbit CLI's `cr doctor`, would let a user (or CI) verify the setup in one command.

## Scope
- New `warden doctor` CLI command
- Checks presence (not value) of required Settings fields: `github_token`, `openai_api_key`, etc. - print pass/fail per field, never the raw secret value
- Optionally performs a lightweight live connectivity check: a cheap GitHub API call (e.g. authenticated `/user`) and a cheap OpenAI API call (e.g. list models), reporting success/failure only - never printing the key/token itself, not even masked, unless explicitly needed for user recognition (and if so, only last 3-4 characters)
- Checks the ChromaDB persistence directory is accessible/writable
- Clear pass/fail summary at the end, non-zero exit code if anything fails

## Acceptance Criteria
- [ ] `warden doctor` command exists and checks all required Settings fields for presence
- [ ] Live GitHub/OpenAI connectivity check implemented, reporting only success/failure
- [ ] No raw secret value is ever printed to stdout/stderr/logs, verified by a test
- [ ] Non-zero exit code when any check fails
- [ ] Unit tests mocking GitHub/OpenAI clients to cover both pass and fail paths
- [ ] Documented in README/CLAUDE.md CLI command reference