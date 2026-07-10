## Description
Manual re-test against facebook/react PR #36982 surfaced a bug in the deterministic summarizer: the Final Verdict panel's "Issues" list correctly shows the quality agent's issues, but the "Suggestions" list shows the security agent's suggestions instead of the quality agent's own suggestions. The quality agent's suggestions (extract helper function, add clarifying comment, rename variable) and the test-coverage agent's suggestions (edge case tests, error case tests, nested outlining tests) are both dropped entirely from the Final Verdict.

## Scope
- Locate the merge/aggregation logic in agents/summarizer.py that assembles the Final Verdict's issues/suggestions
- Fix whatever indexing/reference mistake causes suggestions to be pulled from the wrong agent (or only one agent) instead of a correct merge across all three agents
- Decide and implement the correct intended behavior: a capped top-N merge of suggestions across all agents whose findings are included in the verdict, not a single agent's list

## Acceptance Criteria
- [ ] Final Verdict's Suggestions list reflects a correct merge across all agents with findings, not a single (possibly wrong) agent's list
- [ ] Unit test asserting the Suggestions list in the merged verdict traces back to the correct source agent(s), not silently substituting another agent's list
- [ ] Regression test using distinct, uniquely identifiable suggestion strings per agent in test fixtures, so a future mix-up is caught immediately
- [ ] Manual re-test against PR #36982 confirming quality's own suggestions (and test's, if applicable) appear correctly