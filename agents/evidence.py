from __future__ import annotations

import logging

from agents.state import DroppedIssue

logger = logging.getLogger(__name__)

_DIFF_HEADER = "diff --git "
_MARKERS = "+- "


def _split_files(diff: str) -> list[list[str]]:
    """Split a combined diff into per-file lists of normalized, non-empty lines.

    Each line has its trailing "\\r" removed, its single leading +/-/space diff marker dropped,
    and outer whitespace stripped. Blank lines are discarded so a quote that skipped them is
    still consecutive. "diff --git" headers start a new file and are not kept as lines.
    """
    files: list[list[str]] = []
    current: list[str] | None = None
    for raw in diff.split("\n"):
        line = raw.rstrip("\r")
        if line.startswith(_DIFF_HEADER):
            current = []
            files.append(current)
            continue
        if current is None:
            current = []
            files.append(current)
        body = line[1:] if line[:1] in _MARKERS and line else line
        body = body.strip()
        if body:
            current.append(body)
    return files


def _quote_lines(evidence: str) -> list[str]:
    return [stripped for line in evidence.split("\n") if (stripped := line.rstrip("\r").strip())]


def _line_matches(quote_line: str, diff_line: str) -> bool:
    """A quote line matches if it equals the diff line, with or without its diff marker."""
    if quote_line == diff_line:
        return True
    return quote_line[:1] in _MARKERS and quote_line[1:].strip() == diff_line


def _found_consecutively(quote: list[str], file_lines: list[str]) -> bool:
    span = len(quote)
    for start in range(len(file_lines) - span + 1):
        if all(_line_matches(q, file_lines[start + i]) for i, q in enumerate(quote)):
            return True
    return False


def evidence_in_diff(evidence: str, diff: str) -> bool:
    """True if every non-empty evidence line appears, in order and consecutively, in one file.

    Lines are compared after dropping "\\r", the leading +/-/space diff marker, and outer
    whitespace, so a quote copied without its "+" prefixes or with CRLF endings still matches.
    """
    quote = _quote_lines(evidence)
    if not quote:
        return False
    return any(_found_consecutively(quote, file_lines) for file_lines in _split_files(diff))


def verify_issues(raw_issues: list, diff: str) -> tuple[list[str], list[DroppedIssue]]:
    """Split raw model issues into verified descriptions and dropped findings.

    Mechanical, non-LLM backstop to the prompt's own self-check clause. Each raw issue is
    expected to be {"issue": ..., "evidence": ...}; anything that isn't an object, has no
    evidence, or whose evidence isn't found line-by-line in a single file of the diff is
    dropped and logged (this fails closed rather than raising on a schema-violating model).
    """
    verified: list[str] = []
    dropped: list[DroppedIssue] = []
    for raw_issue in raw_issues:
        if not isinstance(raw_issue, dict):
            logger.warning("Dropping malformed issue entry (not an object): %r", raw_issue)
            dropped.append(DroppedIssue(issue=repr(raw_issue), evidence="", reason="malformed"))
            continue
        description = str(raw_issue.get("issue", ""))
        evidence = raw_issue.get("evidence", "")
        evidence = evidence if isinstance(evidence, str) else ""
        if not _quote_lines(evidence):
            logger.warning("Dropping issue with no evidence: issue=%r", description)
            dropped.append(DroppedIssue(issue=description, evidence=evidence, reason="no_evidence"))
        elif evidence_in_diff(evidence, diff):
            verified.append(description)
        else:
            logger.warning(
                "Dropping unverifiable issue — evidence not found in a single file of the diff: "
                "issue=%r evidence=%r",
                description,
                evidence,
            )
            dropped.append(DroppedIssue(issue=description, evidence=evidence, reason="not_in_diff"))
    return verified, dropped
