from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from config.settings import Settings


def _clear_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "GITHUB_TOKEN",
        "GEMINI_API_KEY",
        "CHROMA_PERSIST_DIR",
        "CHROMA_COLLECTION_NAME",
    ):
        monkeypatch.delenv(key, raising=False)


def test_settings_loads_from_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_settings_env(monkeypatch)
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setenv("GEMINI_API_KEY", "key")

    settings = Settings(_env_file=None)

    assert settings.github_token == "tok"
    assert settings.gemini_api_key == "key"


def test_settings_case_insensitive_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_settings_env(monkeypatch)
    monkeypatch.setenv("github_token", "tok")
    monkeypatch.setenv("gemini_api_key", "key")

    settings = Settings(_env_file=None)

    assert settings.github_token == "tok"
    assert settings.gemini_api_key == "key"


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_settings_env(monkeypatch)
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setenv("GEMINI_API_KEY", "key")

    settings = Settings(_env_file=None)

    assert settings.chroma_persist_dir == "./data/chroma"
    assert settings.chroma_collection_name == "pr_warden"


def test_settings_overrides_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_settings_env(monkeypatch)
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    monkeypatch.setenv("CHROMA_PERSIST_DIR", "/tmp/chroma")
    monkeypatch.setenv("CHROMA_COLLECTION_NAME", "custom_collection")

    settings = Settings(_env_file=None)

    assert settings.chroma_persist_dir == "/tmp/chroma"
    assert settings.chroma_collection_name == "custom_collection"


def test_settings_missing_required_fields_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_settings_env(monkeypatch)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_loads_from_env_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _clear_settings_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text("GITHUB_TOKEN=file-tok\nGEMINI_API_KEY=file-key\n")

    settings = Settings(_env_file=str(env_file))

    assert settings.github_token == "file-tok"
    assert settings.gemini_api_key == "file-key"
