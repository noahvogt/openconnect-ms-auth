# Openconnect MS-Auth

This package allows you to authenticate with your MFA enabled Microsoft-Account into the
openconnect VPN client.

## Example CLI usage

Replace `[username]` and `[password]` with your own information. If you have your account
secured with a TOTP MFA, provide the `-m` flag with the TOTP secret as the value.

Example of a TOTP url: `otpauth://totp/FHNW%3Aelon.musk%40students.fhnw.ch?secret=NBSWY3DPEB3W64TMMQ&issuer=Microsoft`
The secret in this case would be `NBSWY3DPEB3W64TMMQ`. This needs to be provided as an input.

```shell
eval $( python ocma/cli.py -u [username] -p [password] -m [mfa_secret] --print-to-stdout );
[ -n $VPN_COOKIE ] && echo $VPN_COOKIE | sudo openconnect --cookie-on-stdin $VPN_HOST
```
