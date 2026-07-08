from __future__ import annotations

from llama_index.core.schema import Document

from gh.repo_fetcher import CommitData, IssueData, MergedPRData


def _issue_to_document(issue: IssueData, owner: str, repo: str) -> Document:
    text = f"Issue #{issue.number}: {issue.title}\n\nBody:\n{issue.body}"
    doc_id = f"issue-{owner}-{repo}-{issue.number}"
    metadata: dict[str, str | int | float | bool] = {
        "source_doc_id": doc_id,
        "doc_type": "issue",
        "repo": f"{owner}/{repo}",
        "number": issue.number,
        "state": issue.state,
        "author": issue.author,
        "labels": ",".join(issue.labels),
        "created_at": issue.created_at.isoformat(),
        "updated_at": issue.updated_at.isoformat(),
        "closed_at": issue.closed_at.isoformat() if issue.closed_at else "",
    }
    return Document(id_=doc_id, text=text, metadata=metadata)


def _merged_pr_to_document(pr: MergedPRData, owner: str, repo: str) -> Document:
    text = f"Merged PR #{pr.number}: {pr.title}\n\nBody:\n{pr.body}"
    doc_id = f"pr-{owner}-{repo}-{pr.number}"
    metadata: dict[str, str | int | float | bool] = {
        "source_doc_id": doc_id,
        "doc_type": "merged_pr",
        "repo": f"{owner}/{repo}",
        "number": pr.number,
        "author": pr.author,
        "base_branch": pr.base_branch,
        "head_branch": pr.head_branch,
        "merged_at": pr.merged_at.isoformat(),
    }
    return Document(id_=doc_id, text=text, metadata=metadata)


def _commit_to_document(commit: CommitData, owner: str, repo: str) -> Document:
    text = f"Commit {commit.sha[:12]}: {commit.message}"
    doc_id = f"commit-{owner}-{repo}-{commit.sha}"
    metadata: dict[str, str | int | float | bool] = {
        "source_doc_id": doc_id,
        "doc_type": "commit",
        "repo": f"{owner}/{repo}",
        "sha": commit.sha,
        "author": commit.author,
        "committed_at": commit.committed_at.isoformat(),
        "url": commit.url,
    }
    return Document(id_=doc_id, text=text, metadata=metadata)


def issues_to_documents(issues: list[IssueData], owner: str, repo: str) -> list[Document]:
    """Convert IssueData models to LlamaIndex Documents.

    Args:
        issues: Issues returned by gh.repo_fetcher.fetch_issues.
        owner: GitHub owner/organisation name.
        repo: Repository name.

    Returns:
        One Document per issue.
    """
    return [_issue_to_document(issue, owner, repo) for issue in issues]


def merged_prs_to_documents(prs: list[MergedPRData], owner: str, repo: str) -> list[Document]:
    """Convert MergedPRData models to LlamaIndex Documents.

    Args:
        prs: Merged PRs returned by gh.repo_fetcher.fetch_merged_prs.
        owner: GitHub owner/organisation name.
        repo: Repository name.

    Returns:
        One Document per merged PR.
    """
    return [_merged_pr_to_document(pr, owner, repo) for pr in prs]


def commits_to_documents(commits: list[CommitData], owner: str, repo: str) -> list[Document]:
    """Convert CommitData models to LlamaIndex Documents.

    Args:
        commits: Commits returned by gh.repo_fetcher.fetch_recent_commits.
        owner: GitHub owner/organisation name.
        repo: Repository name.

    Returns:
        One Document per commit.
    """
    return [_commit_to_document(commit, owner, repo) for commit in commits]
