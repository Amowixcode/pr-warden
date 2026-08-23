## Description
Cover the multi-agent pipeline with graph-level and integration tests, beyond the per-agent unit tests already covered in their own issues.

## Scope
- Graph-wiring test proving fan-out to all three agents and fan-in to the summarizer actually happens
- Extend the milestone 1 end-to-end integration test (ingest -> retrieve -> review) to exercise the full multi-agent path

## Acceptance Criteria
- [ ] Graph-level test in `tests/unit/` (or `tests/integration/` if it needs real graph execution)
- [ ] Milestone 1 integration test extended to cover the multi-agent flow end-to-end
- [ ] Depends on: graph wiring / core integration issue