# Openconnect MS-Auth

This package allows you to authenticate with your MFA enabled Microsoft-Account into the
openconnect VPN client.

It uses selenium to open the login webpage and fill in the form details. At the end, it
fetches the correct VPN HOST and the Cisco AnyConnect `webvpn` cookie.

> This is a fork of [FHNW/openconnect-ms-auth](https://git.lab.black-burn.ch/FHNW/openconnect-ms-auth)
> by Sean Blackburn. It keeps the credentials out of the process arguments, uses
> `pyotp` instead of the unpackaged `OTPpy`, and ships an Arch package.

## Installation

```shell
paru -S openconnect-ms-auth
```

The PKGBUILD lives in [noahvogt/pkgbuilds](https://github.com/noahvogt/pkgbuilds),
which is configured as a paru PKGBUILD repository by
[norisa](https://github.com/noahvogt/norisa).

## Providing credentials

Secrets are never taken as command line arguments, because those are readable by
every process on the machine. `ocma` resolves them in this order:

1. `--password-command` / `--mfa-command`: a command whose stdout holds the secret
2. `$OCMA_PASSWORD` / `$OCMA_MFA_SECRET`
3. stdin: first line the password, second line the TOTP secret

The recommended source is the Secret Service, so that the secrets stay encrypted at
rest and are unlocked once per session:

```shell
secret-tool store --label='FHNW VPN password' service fhnw-vpn type password
secret-tool store --label='FHNW VPN TOTP' service fhnw-vpn type totp
```

The TOTP secret is the `secret` parameter of the enrollment URL. For
`otpauth://totp/FHNW%3Aelon.musk%40students.fhnw.ch?secret=NBSWY3DPEB3W64TMMQ&issuer=Microsoft`
it is `NBSWY3DPEB3W64TMMQ`.

## Reusing a session

The login can be skipped entirely while the Microsoft session of an earlier
login is still valid. `--session-command` reads the stored session cookies,
`--session-save-command` stores them again after a full login:

```shell
--session-command 'secret-tool lookup service fhnw-vpn type session'
--session-save-command 'secret-tool store --label="FHNW VPN session" service fhnw-vpn type session'
```

Both are optional. Without a stored session, or once Microsoft expires it, the
full login runs and stores a fresh one. The stored session is worth as much as
a logged in browser, so keep it where the password and the TOTP secret already
are.

## Example CLI usage

```shell
eval "$(ocma -u elon.musk@students.fhnw.ch \
    --password-command 'secret-tool lookup service fhnw-vpn type password' \
    --mfa-command 'secret-tool lookup service fhnw-vpn type totp' \
    --print-to-stdout)"

[ -n "$VPN_COOKIE" ] && echo "$VPN_COOKIE" | doas openconnect --cookie-on-stdin "$VPN_HOST"
```

To let NetworkManager own the connection instead, so that it shows up in `nmcli`:

```shell
printf 'vpn.secrets.cookie:%s\nvpn.secrets.gateway:%s\n' "$VPN_COOKIE" "$VPN_HOST" \
    | nmcli connection up FHNW passwd-file /dev/stdin
```

Pass `--show-browser` to watch the login happen, which is the way to find out what
broke when Microsoft changes the login pages.

## Example usage in a Python project

```python
from ocma import connect

connect.login(
    username="username",
    password="password",
    mfa_secret="mfa_secret",
)
```

## Development

The project is managed with [uv](https://docs.astral.sh/uv/).

```shell
uv sync         # set up .venv with the dev dependencies
just            # list the recipes
just lint       # ruff check and format check
just test       # pytest
```

### Releasing

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/),
which is what the version bump is derived from.

1. `just release` runs the checks, then lets [commitizen](https://commitizen-tools.github.io/commitizen/)
   pick the next version from the commits since the last tag, bump `pyproject.toml`
   and `uv.lock`, update `CHANGELOG.md`, commit and tag. Pass `--increment PATCH`
   or a version to override it, e.g. when only `build:` or `chore:` commits landed.
2. `git push --follow-tags`. The release workflow then creates the GitHub release.
3. In [pkgbuilds](https://github.com/noahvogt/pkgbuilds), the daily update job opens
   a PR bumping `pkgver`, the checksums and `.SRCINFO` — or run
   `scripts/bump openconnect-ms-auth <version>` there yourself. Merge it, build the
   package once locally, then publish it with
   `scripts/publish-aur openconnect-ms-auth`.

The AUR push happens from your machine, so that no SSH key has to be stored in CI.
