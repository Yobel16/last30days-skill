"""`first-run-check`: the SKILL.md first-run gate as an engine command.

The gate used to `grep` ~/.config/last30days/.env from the shell, which hosts that
guard credential-file reads block. The engine now reads the file and prints only a
token: FIRST_RUN_DETECTED, REDDIT_OFFER or 1. A secret in the file must never reach
stdout or stderr, and the command must not load the full config (no Keychain/pass).
"""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import pytest

import last30days as cli

SECRET = "dummy-secret-not-real-0123456789"


def _run(env_path: Path | None, host: str | None = None) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    environ = {"LAST30DAYS_HOST": host} if host else {}
    with (
        mock.patch.object(cli.env, "CONFIG_FILE", env_path),
        mock.patch.object(cli.env, "get_config", side_effect=AssertionError("first-run-check must not load config")),
        mock.patch.dict(cli.os.environ, environ, clear=False),
        mock.patch.object(sys, "argv", ["last30days.py", "first-run-check"]),
        redirect_stdout(stdout),
        redirect_stderr(stderr),
    ):
        if host is None:
            cli.os.environ.pop("LAST30DAYS_HOST", None)
        rc = cli.main()
    return rc, stdout.getvalue(), stderr.getvalue()


def _env(tmp_path: Path, body: str) -> Path:
    path = tmp_path / ".env"
    path.write_text(body, encoding="utf-8")
    path.chmod(0o600)
    return path


@pytest.mark.parametrize(
    "body, host, token",
    [
        (None, None, "FIRST_RUN_DETECTED"),  # no file
        ("XAI_API_KEY=" + SECRET + "\n", None, "FIRST_RUN_DETECTED"),  # file without the marker
        ("SETUP_COMPLETE=true\n", None, "REDDIT_OFFER"),
        ("SETUP_COMPLETE=true\nREDDIT_SESSION_OFFERED=true\n", None, "1"),
        ("SETUP_COMPLETE=true\nREDDIT_BROWSER_CONSENT=false\n", None, "1"),
        ("SETUP_COMPLETE=true\nFROM_BROWSER=off\n", None, "1"),
        ("SETUP_COMPLETE=true\nFROM_BROWSER=auto\n", None, "REDDIT_OFFER"),
        ("SETUP_COMPLETE=true\n", "grok-bot", "1"),
        ("XAI_API_KEY=" + SECRET + "\n", "grok-bot", "FIRST_RUN_DETECTED"),  # host rule never skips setup
    ],
)
def test_token(tmp_path, body, host, token):
    path = _env(tmp_path, body) if body is not None else tmp_path / "missing.env"
    rc, out, err = _run(path, host)
    assert rc == 0
    assert out.strip() == token
    assert SECRET not in out + err


def test_clean_config_mode_is_first_run():
    """LAST30DAYS_CONFIG_DIR="" leaves CONFIG_FILE None: same as a missing file."""
    rc, out, _ = _run(None)
    assert (rc, out.strip()) == (0, "FIRST_RUN_DETECTED")
