# Openconnect MS-Auth

This package allows you to authenticate with your MFA enabled Microsoft-Account into the
openconnect VPN client.

It uses selenium to open the login webpage and fill in the form details. At the end, it
fetches the correct VPN HOST and the Cisco AnyConnect `webvpn` cookie.

## Installation for CLI usage

Simply run `pip install git+https://git.snas.black-burn.ch/FHNW/openconnect-ms-auth` to
install the package globally. Then the "ocma" command should be available. Try it out by
typing `ocma -h`.

## Example CLI usage

Replace `[username]` and `[password]` with your own information. If you have your account
secured with a TOTP MFA, provide the `-m` flag with the TOTP secret as the value.

Example of a TOTP url: `otpauth://totp/FHNW%3Aelon.musk%40students.fhnw.ch?secret=NBSWY3DPEB3W64TMMQ&issuer=Microsoft`
The secret in this case would be `NBSWY3DPEB3W64TMMQ`. This needs to be provided as an input.

```shell
eval $( ocma -u [username] -p [password] -m [mfa_secret] --print-to-stdout );
[ -n $VPN_COOKIE ] && echo $VPN_COOKIE | sudo openconnect --cookie-on-stdin $VPN_HOST
```

## Example usage in a Python project

Add with poetry: `poetry add git+https://git.snas.black-burn.ch/FHNW/openconnect-ms-auth`

```python
from ocma import connect

connect.login(
    username="username",
    password="password",
    mfa_secret="mfa_secret"
)
```
