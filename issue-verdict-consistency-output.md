## Description
Manual testing surfaced two related output-design problems:

1. **Verdict/issue inconsistency**: an agent (or the merged Final Verdict) can return APPROVE while still listing a non-empty "Issues" list. Confirmed on two separate occasions:
   - facebook/react PR #36982: identical quality findings produced APPROVE with 3 Issues in one test run, and REQUEST_CHANGES with the same 3 issues in a later run
   - facebook/react PR #36994 (`alphaSortEntries` sort utility): Quality agent verdict APPROVE with 3 non-empty Issues (missing comment on numeric check, `require` inside `beforeEach`, vague test names) - Final Verdict also APPROVE, carrying the same 3 issues. All three findings are legitimate/accurate, not hallucinated - this is purely a verdict/issue consistency bug.
2. **Duplicated output**: for any PR with findings, the exact same issues and suggestions are printed twice - once under "Per-Agent Findings" and again under "Final Verdict" - creating redundant, repetitive CLI output instead of two genuinely different information levels.

## Scope
- Add a rule to the summarizer's verdict merge logic: if the merged issues list is non-empty, the final verdict must never be APPROVE (bump to COMMENT at minimum)
- Add a CLI flag (e.g. `--verbose`) controlling whether the "Per-Agent Findings" section is printed; default output should avoid repeating the same issues/suggestions twice
- Decide and implement: either Final Verdict synthesizes a short summary instead of repeating full lists, or per-agent detail is hidden by default and only shown with `--verbose`

## Acceptance Criteria
- [ ] Verdict merge logic: non-empty merged issues list means verdict is never APPROVE (minimum COMMENT)
- [ ] Unit test covering this rule (e.g. an agent returns APPROVE with issues -> summarizer overrides to COMMENT)
- [ ] CLI gains a `--verbose` flag (or similar) controlling whether Per-Agent Findings is printed; default output reduces duplication with Final Verdict
- [ ] Manual re-test against PR #36982 AND PR #36994 confirming consistent verdict and less redundant output