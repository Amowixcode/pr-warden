from __future__ import annotations

from datetime import datetime, timezone

from gh.repo_fetcher import CommitData, IssueData, MergedPRData
from ingestion.github_loader import (
    commits_to_documents,
    issues_to_documents,
    merged_prs_to_documents,
)

_NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
_THEN = datetime(2024, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
OWNER = "acme"
REPO = "backend"


def _make_issue(**kwargs) -> IssueData:
    defaults: dict = dict(
        number=42,
        title="Fix the thing",
        body="It was broken",
        state="closed",
        labels=["bug"],
        author="alice",
        created_at=_THEN,
        updated_at=_NOW,
        closed_at=_NOW,
    )
    return IssueData(**(defaults | kwargs))


def _make_merged_pr(**kwargs) -> MergedPRData:
    defaults: dict = dict(
        number=10,
        title="Add feature",
        body="Implements XYZ",
        author="bob",
        base_branch="main",
        head_branch="feature/xyz",
        merged_at=_NOW,
    )
    return MergedPRData(**(defaults | kwargs))


def _make_commit(**kwargs) -> CommitData:
    defaults: dict = dict(
        sha="abc123def456789012345678901234567890abcd",
        message="chore: update deps",
        author="carol",
        committed_at=_NOW,
        url="https://github.com/acme/backend/commit/abc123def456789012345678901234567890abcd",
    )
    return CommitData(**(defaults | kwargs))


# ── issue_to_document ────────────────────────────────────────────────────────


def test_issue_id_is_stable():
    doc = issues_to_documents([_make_issue(number=42)], OWNER, REPO)[0]
    assert doc.id_ == "issue-acme-backend-42"


def test_issue_text_contains_title_and_body():
    issue = _make_issue(title="My title", body="My body")
    doc = issues_to_documents([issue], OWNER, REPO)[0]
    assert "Issue #42:" in doc.text
    assert "My title" in doc.text
    assert "My body" in doc.text


def test_issue_metadata_doc_type():
    doc = issues_to_documents([_make_issue()], OWNER, REPO)[0]
    assert doc.metadata["doc_type"] == "issue"


def test_issue_metadata_repo():
    doc = issues_to_documents([_make_issue()], OWNER, REPO)[0]
    assert doc.metadata["repo"] == "acme/backend"


def test_issue_metadata_source_doc_id_mirrors_id():
    doc = issues_to_documents([_make_issue(number=42)], OWNER, REPO)[0]
    assert doc.metadata["source_doc_id"] == doc.id_


def test_issue_metadata_datetimes_are_iso_strings():
    doc = issues_to_documents(
        [_make_issue(created_at=_THEN, updated_at=_NOW, closed_at=_NOW)], OWNER, REPO
    )[0]
    assert doc.metadata["created_at"] == _THEN.isoformat()
    assert doc.metadata["updated_at"] == _NOW.isoformat()
    assert doc.metadata["closed_at"] == _NOW.isoformat()


def test_issue_metadata_labels_joined():
    doc = issues_to_documents([_make_issue(labels=["bug", "urgent"])], OWNER, REPO)[0]
    assert doc.metadata["labels"] == "bug,urgent"


def test_issue_metadata_empty_labels():
    doc = issues_to_documents([_make_issue(labels=[])], OWNER, REPO)[0]
    assert doc.metadata["labels"] == ""


def test_issue_metadata_closed_at_none_is_empty_string():
    doc = issues_to_documents([_make_issue(closed_at=None)], OWNER, REPO)[0]
    assert doc.metadata["closed_at"] == ""


def test_issue_metadata_values_are_chroma_compatible():
    doc = issues_to_documents([_make_issue()], OWNER, REPO)[0]
    for val in doc.metadata.values():
        assert isinstance(val, (str, int, float, bool))


# ── merged_pr_to_document ────────────────────────────────────────────────────


def test_pr_id_is_stable():
    doc = merged_prs_to_documents([_make_merged_pr(number=10)], OWNER, REPO)[0]
    assert doc.id_ == "pr-acme-backend-10"


def test_pr_text_contains_title_and_body():
    pr = _make_merged_pr(title="My PR", body="PR body")
    doc = merged_prs_to_documents([pr], OWNER, REPO)[0]
    assert "Merged PR #10:" in doc.text
    assert "My PR" in doc.text
    assert "PR body" in doc.text


def test_pr_metadata_source_doc_id_mirrors_id():
    doc = merged_prs_to_documents([_make_merged_pr(number=10)], OWNER, REPO)[0]
    assert doc.metadata["source_doc_id"] == doc.id_


def test_pr_metadata_merged_at_is_iso_string():
    doc = merged_prs_to_documents([_make_merged_pr()], OWNER, REPO)[0]
    assert isinstance(doc.metadata["merged_at"], str)
    assert doc.metadata["merged_at"] == _NOW.isoformat()


def test_pr_metadata_has_branches():
    pr = _make_merged_pr(base_branch="main", head_branch="feature/x")
    doc = merged_prs_to_documents([pr], OWNER, REPO)[0]
    assert doc.metadata["base_branch"] == "main"
    assert doc.metadata["head_branch"] == "feature/x"


def test_pr_metadata_values_are_chroma_compatible():
    doc = merged_prs_to_documents([_make_merged_pr()], OWNER, REPO)[0]
    for val in doc.metadata.values():
        assert isinstance(val, (str, int, float, bool))


# ── commit_to_document ───────────────────────────────────────────────────────


def test_commit_id_uses_full_sha():
    sha = "abc123def456789012345678901234567890abcd"
    doc = commits_to_documents([_make_commit(sha=sha)], OWNER, REPO)[0]
    assert doc.id_ == f"commit-acme-backend-{sha}"


def test_commit_text_uses_short_sha():
    sha = "abc123def456789012345678901234567890abcd"
    doc = commits_to_documents([_make_commit(sha=sha)], OWNER, REPO)[0]
    assert sha[:12] in doc.text


def test_commit_text_contains_message():
    doc = commits_to_documents([_make_commit(message="fix: broken thing")], OWNER, REPO)[0]
    assert "fix: broken thing" in doc.text


def test_commit_metadata_source_doc_id_mirrors_id():
    doc = commits_to_documents([_make_commit()], OWNER, REPO)[0]
    assert doc.metadata["source_doc_id"] == doc.id_


def test_commit_metadata_committed_at_is_iso_string():
    doc = commits_to_documents([_make_commit()], OWNER, REPO)[0]
    assert isinstance(doc.metadata["committed_at"], str)
    assert doc.metadata["committed_at"] == _NOW.isoformat()


def test_commit_metadata_values_are_chroma_compatible():
    doc = commits_to_documents([_make_commit()], OWNER, REPO)[0]
    for val in doc.metadata.values():
        assert isinstance(val, (str, int, float, bool))


# ── batch functions ──────────────────────────────────────────────────────────


def test_issues_to_documents_length():
    issues = [_make_issue(number=i) for i in range(5)]
    docs = issues_to_documents(issues, OWNER, REPO)
    assert len(docs) == 5


def test_merged_prs_to_documents_all_have_doc_type():
    prs = [_make_merged_pr(number=i) for i in range(3)]
    docs = merged_prs_to_documents(prs, OWNER, REPO)
    assert all(d.metadata["doc_type"] == "merged_pr" for d in docs)


def test_commits_to_documents_empty_list():
    assert commits_to_documents([], OWNER, REPO) == []
