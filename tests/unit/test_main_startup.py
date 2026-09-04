from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest

from api.main import app, lifespan

REPO_ROOT = Path(__file__).resolve().parents[2]

_HEAVY_PACKAGES = ("openai", "github", "langgraph", "llama_index", "chromadb")

_LEAK_CHECK_SCRIPT = f"""
import json
import sys

import api.main

heavy = {_HEAVY_PACKAGES!r}
leaked = sorted(name for name in heavy if name in sys.modules)
print(json.dumps(leaked))
"""


def test_import_api_main_excludes_heavy_dependencies() -> None:
    """The regression guard for the whole issue: openai/github/langgraph/llama_index/chromadb
    must never appear in api.main's import graph. The check must run inside a fresh subprocess
    — this test process already has these loaded via other test files, so an in-process
    sys.modules check would be meaningless. The subprocess prints its findings to stdout; we
    assert on that (not on stderr text), so a regression fails loudly with the exact leaked
    module names.
    """
    result = subprocess.run(
        [sys.executable, "-c", _LEAK_CHECK_SCRIPT],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )

    assert result.returncode == 0, result.stderr

    leaked = json.loads(result.stdout.strip().splitlines()[-1])
    assert leaked == [], f"heavy modules leaked into api.main's import graph: {leaked}"


def test_import_api_main_succeeds_with_empty_environment(tmp_path: Path) -> None:
    """Settings() must no longer be instantiated at import time — importing api.main must not
    require GITHUB_TOKEN/OPENAI_API_KEY (both required, no-default fields on Settings) to be
    set. Runs with cwd in a tmp_path so no repo .env is discoverable, and with those two env
    vars stripped, so a regression (Settings() creeping back to module scope) fails here even
    if a real .env happens to satisfy it.
    """
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in ("GITHUB_TOKEN", "OPENAI_API_KEY")
    }

    result = subprocess.run(
        [sys.executable, "-c", "import api.main"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(tmp_path),
    )

    assert result.returncode == 0, result.stderr


async def test_lifespan_warms_review_service_in_background(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def _record(name: str) -> None:
        calls.append(name)

    monkeypatch.setattr("api.main.importlib.import_module", _record)

    async with lifespan(app):
        await app.state.warmup_task

    assert calls == ["core.review_service"]


async def test_lifespan_warmup_failure_is_logged_and_swallowed(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def _boom(name: str) -> None:
        raise RuntimeError("simulated warm-up failure")

    monkeypatch.setattr("api.main.importlib.import_module", _boom)

    with caplog.at_level(logging.ERROR, logger="api.main"):
        async with lifespan(app):
            await app.state.warmup_task

    assert "warm-up" in caplog.text.lower()
