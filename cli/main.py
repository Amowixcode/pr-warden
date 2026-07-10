from __future__ import annotations

import asyncio
import json
from collections.abc import Coroutine
from typing import Annotated, Any, NoReturn, TypeVar

import typer
from github import GithubException
from openai import OpenAIError
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core.exceptions import VectorStoreError

app = typer.Typer(help="pr-warden — context-aware PR review CLI")
console = Console()
err_console = Console(stderr=True)

_T = TypeVar("_T")
_VERDICT_STYLE = {"APPROVE": "bold green", "REQUEST_CHANGES": "bold red", "COMMENT": "bold yellow"}
_MAX_SUGGESTIONS = 3


def _parse_repo(repo: str) -> tuple[str, str]:
    """Split 'owner/repo' into (owner, repo), raising a clean usage error otherwise."""
    parts = repo.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise typer.BadParameter(f"expected 'owner/repo', got {repo!r}")
    return parts[0], parts[1]


def _fail(message: str) -> NoReturn:
    err_console.print(f"[bold red]Error:[/bold red] {message}")
    raise typer.Exit(code=1)


def _run(coro: Coroutine[Any, Any, _T]) -> _T:
    """Run an async core call, translating known exception categories into clean CLI errors."""
    try:
        return asyncio.run(coro)
    except ValidationError as e:
        _fail(f"invalid configuration — check your .env file:\n{e}")
    except GithubException as e:
        detail = e.data.get("message", str(e)) if isinstance(e.data, dict) else str(e)
        _fail(f"GitHub API error ({e.status}): {detail}")
    except (json.JSONDecodeError, KeyError) as e:
        _fail(f"failed to parse the AI review response: {e}")
    except OpenAIError as e:
        _fail(f"OpenAI API error: {e}")
    except VectorStoreError as e:
        _fail(str(e))
    except Exception as e:  # no custom exception hierarchy exists in core yet
        _fail(f"unexpected error: {e}")


def _print_ingest_result(owner: str, repo: str, result: Any) -> None:
    table = Table(title=f"Ingested {owner}/{repo}", header_style="bold cyan")
    table.add_column("Category")
    table.add_column("Newly Indexed", justify="right")
    table.add_row("Issues", str(result.issues_indexed))
    table.add_row("Merged PRs", str(result.prs_indexed))
    table.add_row("Commits", str(result.commits_indexed))
    table.add_row("Total", str(result.total_newly_indexed), style="bold green")
    console.print(table)


def _print_agent_section(title: str, result: Any) -> None:
    """Print a Panel + Issues + Suggestions block for anything with those four fields.

    Shared by each per-agent AgentResult and the final aggregated ReviewResult — both have the
    same summary/verdict/issues/suggestions shape. When there's nothing to flag (APPROVE, no
    issues), collapses to a single line instead of an empty panel plus empty section headers —
    matches how terse real-world PR-review tools stay quiet when there's nothing to say.
    """
    style = _VERDICT_STYLE.get(result.verdict, "bold white")

    if result.verdict == "APPROVE" and not result.issues:
        console.print(f"[{style}]✓ {title}  {result.verdict}[/{style}] — {result.summary}")
        for suggestion in result.suggestions[:_MAX_SUGGESTIONS]:
            console.print(f"    ↳ {suggestion}")
        return

    header = f"{title}  [{style}]{result.verdict}[/{style}]"
    console.print(Panel(result.summary, title=header, border_style=style))

    console.print("[bold]Issues[/bold]" if result.issues else "[dim]No issues found.[/dim]")
    for issue in result.issues:
        console.print(f"  • {issue}")

    suggestions = result.suggestions[:_MAX_SUGGESTIONS]
    console.print("[bold]Suggestions[/bold]" if suggestions else "[dim]No suggestions.[/dim]")
    for suggestion in suggestions:
        console.print(f"  • {suggestion}")


def _print_doctor_result(result: Any) -> None:
    """Print a pass/fail table for each doctor check — never the check's raw secret value."""
    table = Table(title="pr-warden setup check", header_style="bold cyan")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")
    for check in result.checks:
        status = "[bold green]PASS[/bold green]" if check.passed else "[bold red]FAIL[/bold red]"
        table.add_row(check.name, status, check.detail)
    console.print(table)

    if result.all_passed:
        console.print("[bold green]All checks passed.[/bold green]")
    else:
        err_console.print("[bold red]One or more checks failed.[/bold red]")


def _print_review_result(result: Any) -> None:
    console.print("[bold underline]Per-Agent Findings[/bold underline]")
    _print_agent_section("Security", result.security_result)
    _print_agent_section("Quality", result.quality_result)
    _print_agent_section("Test Coverage", result.test_result)

    console.print()
    console.print("[bold underline]Final Verdict[/bold underline]")
    _print_agent_section(f"PR #{result.pr_number}", result)


@app.command()
def doctor() -> None:
    """Run setup/health checks (Settings, GitHub, OpenAI, ChromaDB) and report pass/fail."""
    from core.doctor_service import run_doctor_checks  # lazy, same reasoning as ingest/review

    result = _run(run_doctor_checks())
    _print_doctor_result(result)
    if not result.all_passed:
        raise typer.Exit(code=1)


@app.command()
def ingest(
    repo: Annotated[str, typer.Argument(help="GitHub repository as 'owner/repo'")],
) -> None:
    """Index a repository's issues, merged PRs, and commits into ChromaDB."""
    owner, name = _parse_repo(repo)
    from core.ingest_service import ingest_repository  # lazy: avoid Settings() at --help time

    result = _run(ingest_repository(owner, name))
    _print_ingest_result(owner, name, result)


@app.command()
def review(
    repo: Annotated[str, typer.Argument(help="GitHub repository as 'owner/repo'")],
    pr_number: Annotated[int, typer.Argument(help="Pull request number to review", min=1)],
) -> None:
    """Review a pull request using historical repo context and OpenAI."""
    owner, name = _parse_repo(repo)
    from core.review_service import review_pr  # lazy, same reasoning as ingest

    result = _run(review_pr(owner, name, pr_number))
    _print_review_result(result)
