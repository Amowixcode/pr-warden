## Description
`warden review` currently always exits 0 regardless of verdict, and only prints Rich-formatted human output. This means the tool cannot function as a real CI gate (a CI step can't fail a build based on a REQUEST_CHANGES verdict) and cannot be consumed programmatically by other tooling.

## Scope
- `warden review` returns a non-zero exit code when the final verdict is REQUEST_CHANGES (e.g. exit 1), and 0 for APPROVE/COMMENT
- Add a `--json` flag that outputs the structured verdict (per-agent findings + final verdict) as machine-readable JSON instead of the Rich-formatted human output
- Keep the default (no flag) behavior as the current human-readable Rich output
- Document both in README/CLAUDE.md CLI command reference

## Acceptance Criteria
- [ ] `warden review` exits non-zero on REQUEST_CHANGES, zero on APPROVE/COMMENT
- [ ] `--json` flag prints a well-formed JSON document with the same information as the human output
- [ ] Unit tests covering exit code per verdict and JSON output shape
- [ ] Manual test: `warden review <owner/repo> <pr>; echo $?` shows the correct exit code, and piping `--json` output into `jq` works