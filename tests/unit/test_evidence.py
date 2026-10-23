from __future__ import annotations

from agents.evidence import evidence_in_diff, verify_issues

_DIFF = (
    "diff --git a/src/app.py b/src/app.py\n"
    "@@ -1,4 +1,8 @@\n"
    " import os\n"
    " \n"
    "+def load(path):\n"
    "+    with open(path) as f:\n"
    "+        return f.read()\n"
    "+\n"
    "+SECRET = 'hunter2'\n"
    "-OLD = 1\n"
    "diff --git a/src/other.py b/src/other.py\n"
    "@@ -1,2 +1,3 @@\n"
    "+def other():\n"
    "+    return 42\n"
)


def _issue(evidence: str, issue: str = "problem") -> dict:
    return {"issue": issue, "evidence": evidence}


def test_multi_line_quote_without_plus_prefixes_matches() -> None:
    quote = "def load(path):\n    with open(path) as f:\n        return f.read()"

    assert evidence_in_diff(quote, _DIFF)


def test_quote_with_diff_markers_matches() -> None:
    quote = "+def load(path):\n+    with open(path) as f:"

    assert evidence_in_diff(quote, _DIFF)


def test_single_line_quote_matches_with_or_without_marker() -> None:
    assert evidence_in_diff("SECRET = 'hunter2'", _DIFF)
    assert evidence_in_diff("+SECRET = 'hunter2'", _DIFF)


def test_changed_indentation_still_matches() -> None:
    assert evidence_in_diff("def load(path):\nwith open(path) as f:", _DIFF)


def test_removed_line_matches() -> None:
    assert evidence_in_diff("-OLD = 1", _DIFF)
    assert evidence_in_diff("OLD = 1", _DIFF)


def test_blank_lines_in_the_quote_are_ignored() -> None:
    quote = "def load(path):\n\n    with open(path) as f:\n\n"

    assert evidence_in_diff(quote, _DIFF)


def test_blank_line_in_the_diff_does_not_break_a_consecutive_quote() -> None:
    assert evidence_in_diff("return f.read()\nSECRET = 'hunter2'", _DIFF)


def test_crlf_in_the_quote_matches() -> None:
    assert evidence_in_diff("def load(path):\r\n    with open(path) as f:\r\n", _DIFF)


def test_crlf_in_the_diff_matches() -> None:
    crlf_diff = _DIFF.replace("\n", "\r\n")

    assert evidence_in_diff("def load(path):\n    with open(path) as f:", crlf_diff)


def test_invented_line_is_dropped() -> None:
    assert not evidence_in_diff("def load(path):\n    eval(path)", _DIFF)


def test_non_consecutive_lines_are_dropped() -> None:
    assert not evidence_in_diff("def load(path):\n        return f.read()", _DIFF)


def test_lines_spanning_two_files_are_dropped() -> None:
    assert not evidence_in_diff("SECRET = 'hunter2'\ndef other():", _DIFF)


def test_line_order_matters() -> None:
    assert not evidence_in_diff("with open(path) as f:\ndef load(path):", _DIFF)


def test_quote_starting_with_a_dash_that_is_content_matches() -> None:
    diff = "diff --git a/README.md b/README.md\n@@ -1 +1,2 @@\n+- first item\n+- second item\n"

    assert evidence_in_diff("- first item\n- second item", diff)


def test_empty_evidence_never_matches() -> None:
    assert not evidence_in_diff("", _DIFF)
    assert not evidence_in_diff("  \n \r\n", _DIFF)


def test_empty_diff_never_matches() -> None:
    assert not evidence_in_diff("def load(path):", "")


def test_quote_from_the_pr_description_is_dropped() -> None:
    description_quote = "Verified independently that:\n- The previous approach throws RangeError"

    verified, dropped = verify_issues([_issue(description_quote)], _DIFF)

    assert verified == []
    assert [d.reason for d in dropped] == ["not_in_diff"]
    assert dropped[0].evidence == description_quote


def test_verify_issues_keeps_verified_and_reports_dropped_separately() -> None:
    raw = [
        _issue("SECRET = 'hunter2'", issue="hardcoded secret"),
        _issue("totally invented line", issue="made up"),
    ]

    verified, dropped = verify_issues(raw, _DIFF)

    assert verified == ["hardcoded secret"]
    assert [(d.issue, d.reason) for d in dropped] == [("made up", "not_in_diff")]


def test_verify_issues_drops_malformed_and_missing_evidence_with_reasons() -> None:
    raw = ["just a string", {"issue": "no evidence key"}, {"issue": "blank", "evidence": "  "}]

    verified, dropped = verify_issues(raw, _DIFF)

    assert verified == []
    assert [d.reason for d in dropped] == ["malformed", "no_evidence", "no_evidence"]


def test_verify_issues_treats_non_string_evidence_as_missing() -> None:
    verified, dropped = verify_issues([{"issue": "x", "evidence": ["a", "b"]}], _DIFF)

    assert verified == []
    assert dropped[0].reason == "no_evidence"
