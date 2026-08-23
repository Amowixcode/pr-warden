## Description
Implement the test-coverage-focused agent node in the multi-agent review graph. Builds on the state schema from the architecture/design issue.

## Scope
- `agents/test_agent.py`: OpenAI-backed node reviewing whether the PR diff has adequate test coverage (new/changed logic has corresponding tests, edge cases considered)
- Distinct system prompt scoped to test-adequacy concerns only
- Same retry/error-handling pattern already used for OpenAI calls
- Node reads/writes the shared state schema from `agents/state.py`

## Acceptance Criteria
- [ ] `agents/test_agent.py` implements the node function
- [ ] Uses configured max_retries and existing exception wrapping conventions
- [ ] Unit tests mocking OpenAI, asserting prompt construction and result parsing
- [ ] Depends on: architecture/state-design issue