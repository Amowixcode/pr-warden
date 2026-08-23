## Description
Close the documentation-drift gap flagged during the milestone 1 review: CLAUDE.md and README already describe multi-agent LangGraph orchestration, but this only becomes accurate once milestone 2 ships.

## Scope
- Review and update README to accurately describe the implemented agents (security, quality, test), the summarizer's merge policy, and the CLI output format
- Review and update CLAUDE.md's architecture section if it no longer matches the actual `agents/` implementation

## Acceptance Criteria
- [ ] README reflects the actual implemented multi-agent architecture
- [ ] CLAUDE.md architecture section reviewed and updated if needed
- [ ] Depends on: CLI output update issue (or all prior milestone 2 issues)