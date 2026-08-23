## Description
Implement the aggregator/summarizer node that merges the three agents outputs (security, quality, test) into one final structured verdict.

## Scope
- `agents/summarizer.py`: merge policy - REQUEST_CHANGES if any agent flags it, else COMMENT if any agent has non-blocking issues, else APPROVE
- Combine issues/suggestions from all three agents into the existing structured verdict shape (APPROVE/REQUEST_CHANGES/COMMENT + issues + suggestions)
- Node reads the shared state schema from `agents/state.py` and writes the final verdict field

## Acceptance Criteria
- [ ] `agents/summarizer.py` implements the merge policy
- [ ] Unit tests covering all verdict combinations (all approve, one requests changes, one comments only, mixed)
- [ ] Depends on: architecture/state-design issue