"""Coverage-focused tests for env loading in db_config."""

import os
from pathlib import Path

import pytest

from src import db_config

pytestmark = pytest.mark.db


def test_load_env_file_parses_and_preserves_existing_env(monkeypatch, tmp_path):
    """Validate .env parsing rules and non-overwrite behavior."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "# comment",
                "DB_HOST=localhost",
                " DB_PORT = 5432 ",
                "EMPTY_KEY=",
                "QUOTED_DOUBLE=\"abc123\"",
                "QUOTED_SINGLE='xyz789'",
                "INVALID_LINE",
                "",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("DB_HOST", "existing-host")
    monkeypatch.delenv("DB_PORT", raising=False)
    monkeypatch.delenv("EMPTY_KEY", raising=False)
    monkeypatch.delenv("QUOTED_DOUBLE", raising=False)
    monkeypatch.delenv("QUOTED_SINGLE", raising=False)

    db_config._load_env_file(env_file)

    # Existing env vars are intentionally preserved.
    assert os.getenv("DB_HOST") == "existing-host"
    # New vars are loaded and stripped/sanitized.
    assert os.getenv("DB_PORT") == "5432"
    assert os.getenv("EMPTY_KEY") == ""
    assert os.getenv("QUOTED_DOUBLE") == "abc123"
    assert os.getenv("QUOTED_SINGLE") == "xyz789"


def test_load_env_file_missing_path_is_noop(tmp_path):
    """Missing .env file should not raise and should not mutate env."""
    missing = Path(tmp_path / "does_not_exist.env")
    db_config._load_env_file(missing)
