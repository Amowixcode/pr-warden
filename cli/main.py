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

app = typer.Typer(help="pr-warden — context-aware PR review CLI")
console = Console()
err_console = Console(stderr=True)

_T = TypeVar("_T")
_VERDICT_STYLE = {"APPROVE": "bold green", "REQUEST_CHANGES": "bold red", "COMMENT": "bold yellow"}


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


def _print_review_result(result: Any) -> None:
    style = _VERDICT_STYLE.get(result.verdict, "bold white")
    header = f"PR #{result.pr_number}  [{style}]{result.verdict}[/{style}]"
    console.print(Panel(result.summary, title=header, border_style=style))

    console.print("[bold]Issues[/bold]" if result.issues else "[dim]No issues found.[/dim]")
    for issue in result.issues:
        console.print(f"  • {issue}")

    has_suggestions = result.suggestions
    console.print("[bold]Suggestions[/bold]" if has_suggestions else "[dim]No suggestions.[/dim]")
    for suggestion in result.suggestions:
        console.print(f"  • {suggestion}")


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
