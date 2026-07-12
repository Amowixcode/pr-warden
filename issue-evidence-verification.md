## Description
Manual verification against facebook/react PR #36794 found a genuine hallucination that slipped past the existing self-check clause: the security/quality output claimed "the else branch that calls bridge.shutdown() is commented out" (packages/react-devtools-extensions/src/main/index.js:460-475). Checked against the real diff on GitHub - the `bridge?.shutdown()` call is NOT commented out, it is live, functional code with an explanatory comment written above it. The self-check instruction ("re-read the exact diff line before making a specific claim") is not sufficient alone to prevent this class of error.

## Scope
Add a mechanical, non-LLM verification layer instead of relying purely on prompt instructions:
- Extend each agent's JSON output schema to require an `evidence` field per issue: an exact, verbatim quote of the specific code line(s) the issue refers to
- After parsing the agent's response, add a Python-level check (plain string matching, not another LLM call) verifying that each issue's `evidence` string actually appears in the diff text passed to that agent
- If an issue's evidence cannot be found verbatim in the diff, drop that issue automatically (and log it for later inspection) rather than showing it to the user
- This is a stricter, mechanically-enforced version of the existing self-check clause, not a replacement for it - keep both

## Acceptance Criteria
- [ ] Agent JSON schema includes an `evidence` field per issue (exact quoted diff excerpt)
- [ ] Post-processing verification step checks each issue's evidence against the actual diff text before it reaches the user
- [ ] Issues that fail verification are dropped automatically, not shown
- [ ] Unit test: an agent response with a fabricated `evidence` string (not present in the diff) results in that issue being filtered out
- [ ] Regression test using the actual #36794 scenario (a fabricated "commented out" claim) to prove this specific failure mode is now caught
- [ ] Manual re-test against PR #36794 confirming the false claim no longer appears