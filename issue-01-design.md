## Description
Define the foundational LangGraph structure for the multi-agent review pipeline described in CLAUDE.md/README ("runs parallel agents (security, quality, test) backed by OpenAI"). This is the contract everything else in milestone 2 builds on - must land before the three agents, the summarizer, or graph wiring can be implemented.

## Scope
- Define a shared state schema (TypedDict or Pydantic model) carrying: PR diff, retrieved RAG context, per-agent results, final aggregated verdict
- Define the graph shape: three agent nodes (security, quality, test) run in parallel (fan-out), a summarizer node merges their outputs (fan-in)
- Decide the merge policy contract the summarizer will implement (e.g. REQUEST_CHANGES if any agent flags it, else COMMENT if any non-blocking issue, else APPROVE) - implementation happens in a later issue, but the state schema must support it
- Document the design in `agents/` so later issues have a clear contract to implement against

## Acceptance Criteria
- [ ] `agents/state.py` with the shared state schema
- [ ] Design notes describing the graph shape and node responsibilities
- [ ] Contract-only - unblocks issues for security_agent, quality_agent, test_agent, summarizer, and graph wiring