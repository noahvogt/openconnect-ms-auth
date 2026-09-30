"""Tests for the credential resolution of the CLI."""

import argparse
import io

import pytest

from ocma import cli


def _args(**overrides: str | None) -> argparse.Namespace:
    """
    Build a namespace like the argument parser produces.

    Parameters
    ----------
    **overrides : str | None
        Values overriding the defaults.

    Returns
    -------
    argparse.Namespace
        The namespace to hand to the resolver.
    """
    values: dict[str, str | None] = {
        "username": "user@fhnw.ch",
        "password_command": None,
        "mfa_command": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_reads_secrets_from_commands() -> None:
    """Resolve both secrets from the configured commands."""
    args = _args(password_command="printf pw", mfa_command="printf SECRET")
    assert cli._resolve_credentials(args) == ("pw", "SECRET")


def test_reads_secrets_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve both secrets from the environment."""
    monkeypatch.setenv(cli.PASSWORD_ENV, "env-pw")
    monkeypatch.setenv(cli.MFA_ENV, "ENVSECRET")
    assert cli._resolve_credentials(_args()) == ("env-pw", "ENVSECRET")


def test_command_takes_precedence_over_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prefer the command over the environment."""
    monkeypatch.setenv(cli.PASSWORD_ENV, "env-pw")
    args = _args(password_command="printf cmd-pw")
    assert cli._resolve_credentials(args)[0] == "cmd-pw"


def test_reads_both_secrets_from_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    """Read the password and the MFA secret from the two lines of stdin."""
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO("stdin-pw\nSTDINSECRET\n"))
    assert cli._resolve_credentials(_args()) == ("stdin-pw", "STDINSECRET")


def test_missing_password_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail if no source provides a password."""
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO(""))
    with pytest.raises(ValueError, match="No password found"):
        cli._resolve_credentials(_args())


def test_failing_command_raises() -> None:
    """Fail if the secret command exits non-zero."""
    with pytest.raises(ValueError, match="Failed to read a secret"):
        cli._resolve_credentials(_args(password_command="false"))
