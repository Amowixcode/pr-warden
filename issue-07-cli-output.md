## Description
Update the CLI output to surface the multi-agent nature of the review, not just the merged verdict.

## Scope
- `cli/main.py`: display each agent's individual findings (security/quality/test) alongside the final aggregated verdict, using the existing Rich console conventions
- Preserve the existing error boundary (GitHub/OpenAI/VectorStore/validation errors still map to readable messages, no raw tracebacks)

## Acceptance Criteria
- [ ] CLI displays per-agent findings sections plus the final verdict
- [ ] Existing error-handling behavior preserved and tested
- [ ] Depends on: graph wiring / core integration issue