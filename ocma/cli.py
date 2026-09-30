"""CLI interface."""

import argparse
import getpass
import os
import shlex
import subprocess
import sys

from ocma import connect

PASSWORD_ENV = "OCMA_PASSWORD"
MFA_ENV = "OCMA_MFA_SECRET"


def _read_command(command: str) -> str:
    """
    Read a secret from the stdout of a command.

    Parameters
    ----------
    command : str
        Command to run. Split according to shell syntax, but not run in a shell.

    Returns
    -------
    str
        First line of the command output, stripped.

    Raises
    ------
    ValueError
        If the command could not be run or exited non-zero.
    """
    try:
        result = subprocess.run(
            shlex.split(command),
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as e:
        raise ValueError(f"Failed to read a secret from '{command}': {e}") from e

    return result.stdout.splitlines()[0].strip() if result.stdout.strip() else ""


def _write_command(command: str, data: str) -> None:
    """
    Hand a secret to the stdin of a command.

    A failure here is reported but not fatal: it only means the session could
    not be stored, and the next run logs in from scratch.

    Parameters
    ----------
    command : str
        Command to run. Split according to shell syntax, but not run in a shell.
    data : str
        What to write to its stdin.
    """
    try:
        subprocess.run(
            shlex.split(command),
            input=data,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as e:
        print(
            f"Warning: could not store the session with '{command}': {e}",
            file=sys.stderr,
        )


def _read_stdin() -> list[str]:
    """
    Read the credentials passed on stdin.

    Returns
    -------
    list[str]
        The non-empty lines found on stdin.
    """
    return [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]


def _resolve_credentials(args: argparse.Namespace) -> tuple[str, str | None]:
    """
    Resolve the password and the MFA secret from the configured sources.

    The sources are tried in this order: an explicit command, the environment,
    and finally stdin (first line: password, second line: MFA secret). Neither
    secret is ever accepted as a command line argument, because arguments are
    visible to every other process on the machine.

    Parameters
    ----------
    args : argparse.Namespace
        The parsed command line arguments.

    Returns
    -------
    tuple[str, str | None]
        The password and, if one was configured, the MFA secret.

    Raises
    ------
    ValueError
        If no password could be resolved.
    """
    password: str | None = None
    mfa_secret: str | None = None

    if args.password_command:
        password = _read_command(args.password_command)
    elif os.environ.get(PASSWORD_ENV):
        password = os.environ[PASSWORD_ENV]

    if args.mfa_command:
        mfa_secret = _read_command(args.mfa_command)
    elif os.environ.get(MFA_ENV):
        mfa_secret = os.environ[MFA_ENV]

    if password is None:
        if sys.stdin.isatty():
            password = getpass.getpass(f"Password ({args.username}): ")
        else:
            lines = _read_stdin()
            if lines:
                password = lines[0]
            if mfa_secret is None and len(lines) > 1:
                mfa_secret = lines[1]

    if not password:
        raise ValueError(
            "No password found. Provide it via --password-command, "
            f"${PASSWORD_ENV} or on stdin.",
        )

    return password, mfa_secret


def run() -> None:
    """
    Run the CLI interface.

    Raises
    ------
    ValueError
        If the MFA secret is invalid.
    """
    parser = argparse.ArgumentParser(description="openconnect-microsoft-authenticator")

    parser.add_argument(
        "-u",
        "--username",
        metavar="username",
        type=str,
        help="MS Account username.",
        required=True,
    )
    parser.add_argument(
        "--password-command",
        metavar="command",
        type=str,
        help=(
            "Command printing the MS Account password on stdout, e.g. "
            "'secret-tool lookup service fhnw-vpn type password'. Falls back to "
            f"${PASSWORD_ENV} and then to stdin."
        ),
    )
    parser.add_argument(
        "--mfa-command",
        metavar="command",
        type=str,
        help=(
            "Command printing the TOTP secret on stdout. Falls back to "
            f"${MFA_ENV} and then to the second line of stdin. Required if the "
            "account is secured with a TOTP MFA."
        ),
    )

    parser.add_argument(
        "--session-command",
        metavar="command",
        type=str,
        help=(
            "Command printing the session cookies of an earlier login on stdout, "
            "e.g. 'secret-tool lookup service fhnw-vpn type session'. A session "
            "that is still valid skips the login."
        ),
    )
    parser.add_argument(
        "--session-save-command",
        metavar="command",
        type=str,
        help=(
            "Command storing the session cookies handed to it on stdin, e.g. "
            '\'secret-tool store --label="FHNW VPN session" service fhnw-vpn '
            "type session'. Only run after a full login."
        ),
    )

    parser.add_argument(
        "--vpn-url",
        nargs="?",
        metavar="url",
        type=str,
        help="Login URL",
        default="https://vpn.fhnw.ch",
    )
    parser.add_argument(
        "--show-browser",
        action="store_true",
        help="Show the browser window during the authentication process.",
    )
    parser.add_argument(
        "-v",
        action="store_true",
        help="If verbal messages should be printed to stderr",
    )

    parser.add_argument(
        "--print-to-stdout",
        action="store_true",
        help="""If the vpn host and cookie should be printed to the stdout. To be used like:\n
            \n
            eval $( ocma -u [username] --print-to-stdout ); \n
            [ -n $VPN_COOKIE ] && echo $VPN_COOKIE | sudo openconnect --cookie-on-stdin $VPN_HOST
        """,
    )

    args = parser.parse_args()

    password, mfa_secret = _resolve_credentials(args)

    if mfa_secret is not None:
        try:
            connect.get_mfa_code(mfa_secret)

        except ValueError as e:
            raise ValueError("Your MFA secret is invalid!") from e

    session = None
    if args.session_command:
        try:
            session = _read_command(args.session_command)

        except ValueError as e:
            # No session stored yet, or the store is unreachable: log in fully.
            print(f"Warning: {e}", file=sys.stderr)

    cookie = connect.login(
        username=args.username,
        password=password,
        mfa_secret=mfa_secret,
        vpn_site=args.vpn_url,
        headless=not args.show_browser,
        log_messages=args.v,
        session=session,
    )

    if args.session_save_command and cookie.session:
        _write_command(args.session_save_command, cookie.session)

    if args.print_to_stdout:
        print(f"VPN_HOST={cookie.domain}")
        print(f"VPN_COOKIE={cookie.cookie}")


if __name__ == "__main__":
    run()
