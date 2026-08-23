## Description
Manual testing against facebook/react PR #36982 (TypeScript, babel-plugin-react-compiler) surfaced two distinct problems in the quality agent's output:

1. **Hallucinated finding**: flagged `outlinedObjectMethods` as missing type hints, but the line already has an explicit `Set<IdentifierId>` type parameter. This is a specific, checkable claim that is factually wrong - worse than a vague finding, since it actively erodes trust in the tool.
2. **Language-specific assumption bleeding into review of external code**: flagged a missing "docstring" on a TypeScript function, applying pr-warden's own CLAUDE.md convention ("Docstrings on public functions" - a Python-specific rule for pr-warden's own codebase) to a target repo written in a different language with different documentation conventions (JSDoc/TSDoc, not Python docstrings).

## Scope
- Review and rewrite the quality agent's system prompt so it does not assume pr-warden's own coding conventions (Python docstrings, type hints as written in CLAUDE.md) apply universally to reviewed code
- Instruct the agent to only flag typing/documentation issues relevant to the target language/ecosystem's own conventions
- Add guidance in the prompt to avoid making specific, checkable claims (e.g. "missing type X") unless it can point to the exact absence in the provided diff - reduce confident-but-wrong hallucinations
- Consider a lightweight self-check instruction for claims that reference specific code constructs

## Acceptance Criteria
- [ ] Quality agent prompt no longer references pr-warden's own Python-specific conventions as a universal standard
- [ ] Re-test against PR #36982: the "missing type hints" finding should not recur given the line already has an explicit type parameter
- [ ] Re-test against PR #36982: no docstring/Python-convention complaint should appear for a TypeScript codebase
- [ ] Unit test(s) covering the agent's handling of a non-Python fixture, asserting it doesn't apply Python-specific conventions
- [ ] Manual spot-check against at least one more language (e.g. Go, Rust, or another TS repo) to confirm generalization