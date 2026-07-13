from __future__ import annotations

import asyncio
import dataclasses
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

app = typer.Typer(
    help="pr-warden — context-aware PR review CLI",
    no_args_is_help=True,
    epilog=(
        "Quickstart: warden doctor -> warden ingest owner/repo -> "
        "warden review owner/repo 123\n\n"
        "Run 'warden <command> --help' for details on any command."
    ),
)
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
    if result.incremental:
        console.print(
            "[bold cyan]Incremental ingest — fetching only items updated since the last "
            "run.[/bold cyan]"
        )
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


def _print_review_result(result: Any, verbose: bool = False) -> None:
    if result.cached:
        console.print(
            f"[bold cyan]No new commits since last review "
            f"(commit {result.prior_head_sha[:7]}) — showing cached verdict.[/bold cyan]"
        )
        console.print()
    elif result.incremental:
        console.print(
            f"[bold cyan]Incremental review — since commit {result.prior_head_sha[:7]}, "
            f"prior verdict: {result.prior_verdict}.[/bold cyan]"
        )
        console.print()

    if verbose:
        console.print("[bold underline]Per-Agent Findings[/bold underline]")
        _print_agent_section("Security", result.security_result)
        _print_agent_section("Quality", result.quality_result)
        _print_agent_section("Test Coverage", result.test_result)
        console.print()

    console.print("[bold underline]Final Verdict[/bold underline]")
    _print_agent_section(f"PR #{result.pr_number}", result)


def _print_review_result_json(result: Any) -> None:
    """Print the review result as machine-readable JSON only — no Rich panels mixed in.

    Rich auto-detects a non-tty stdout (e.g. piped to jq) and disables ANSI color/highlighting,
    so this stays clean, valid JSON when piped.
    """
    console.print_json(data=dataclasses.asdict(result))


@app.command(short_help="Run setup/health checks (optional, run anytime).")
def doctor() -> None:
    """Run setup/health checks (Settings, GitHub, OpenAI, ChromaDB) and report pass/fail.

    Optional — run this anytime, before or after ingest/review, to confirm your GitHub token,
    OpenAI key, and ChromaDB are configured correctly.
    """
    from core.doctor_service import run_doctor_checks  # lazy, same reasoning as ingest/review

    result = _run(run_doctor_checks())
    _print_doctor_result(result)
    if not result.all_passed:
        raise typer.Exit(code=1)


@app.command(short_help="Index a repo (run this first).")
def ingest(
    repo: Annotated[str, typer.Argument(help="GitHub repository as 'owner/repo'")],
    full: Annotated[
        bool,
        typer.Option(
            "--full", help="Force a complete re-ingestion, ignoring any prior ingest history"
        ),
    ] = False,
) -> None:
    """Index a repository's issues, merged PRs, and commits into ChromaDB. Run this first,
    before reviewing a PR.

    Incremental by default: if this repo was ingested before, only items created or updated
    since that ingest are fetched. Pass --full to always do a complete re-ingestion.
    """
    owner, name = _parse_repo(repo)
    from core.ingest_service import ingest_repository  # lazy: avoid Settings() at --help time

    result = _run(ingest_repository(owner, name, full=full))
    _print_ingest_result(owner, name, result)


@app.command(short_help="Review a PR (run after ingest).")
def review(
    repo: Annotated[str, typer.Argument(help="GitHub repository as 'owner/repo'")],
    pr_number: Annotated[int, typer.Argument(help="Pull request number to review", min=1)],
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output machine-readable JSON instead of Rich-formatted text"),
    ] = False,
    full: Annotated[
        bool,
        typer.Option(
            "--full", help="Force a complete review, ignoring any prior incremental review history"
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Also show each agent's individual findings, not just the merged Final Verdict",
        ),
    ] = False,
) -> None:
    """Review a pull request using historical repo context and OpenAI. Run this after
    ingesting the repo.

    Incremental by default: if this PR was reviewed before, only the diff since the last
    review is sent to the agents (or, if nothing changed, the cached result is returned with
    no new API calls). Pass --full to always do a complete review.

    Default output shows only the merged Final Verdict, to avoid printing the same
    issues/suggestions twice. Pass --verbose to also show each agent's own findings.

    Exits non-zero when the final verdict is REQUEST_CHANGES, so this can gate a CI step.
    """
    owner, name = _parse_repo(repo)
    from core.review_service import review_pr  # lazy, same reasoning as ingest

    result = _run(review_pr(owner, name, pr_number, full=full))
    if json_output:
        _print_review_result_json(result)
    else:
        _print_review_result(result, verbose=verbose)

    if result.verdict == "REQUEST_CHANGES":
        raise typer.Exit(code=1)
