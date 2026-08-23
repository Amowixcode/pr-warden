## Description
Implement the security-focused agent node in the multi-agent review graph. Builds on the state schema from the architecture/design issue.

## Scope
- `agents/security_agent.py`: OpenAI-backed node reviewing the PR diff + retrieved RAG context for security concerns (hardcoded secrets, injection risks, unsafe deserialization, auth/authorization gaps, unsafe dependency usage)
- Distinct system prompt scoped to security concerns only
- Same retry/error-handling pattern already used for OpenAI calls (max_retries via Settings, wrapped exceptions)
- Node reads/writes the shared state schema from `agents/state.py`

## Acceptance Criteria
- [ ] `agents/security_agent.py` implements the node function
- [ ] Uses configured max_retries and existing exception wrapping conventions
- [ ] Unit tests mocking OpenAI, asserting prompt construction and result parsing
- [ ] Depends on: architecture/state-design issue