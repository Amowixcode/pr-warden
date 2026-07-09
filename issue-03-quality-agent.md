## Description
Implement the code-quality-focused agent node in the multi-agent review graph. Builds on the state schema from the architecture/design issue.

## Scope
- `agents/quality_agent.py`: OpenAI-backed node reviewing the PR diff + retrieved RAG context for code quality (style, maintainability, naming, complexity, adherence to CLAUDE.md conventions like type hints/docstrings)
- Distinct system prompt scoped to quality concerns only
- Same retry/error-handling pattern already used for OpenAI calls
- Node reads/writes the shared state schema from `agents/state.py`

## Acceptance Criteria
- [ ] `agents/quality_agent.py` implements the node function
- [ ] Uses configured max_retries and existing exception wrapping conventions
- [ ] Unit tests mocking OpenAI, asserting prompt construction and result parsing
- [ ] Depends on: architecture/state-design issue