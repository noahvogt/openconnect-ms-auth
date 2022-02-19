import argparse

from ocma import connect


def run() -> None:
    parser = argparse.ArgumentParser(description="openconnect-microsoft-authenticator")

    # add argument
    parser.add_argument(
        "-u",
        "--username",
        metavar="username",
        type=str,
        help="MS Account username",
        required=True,
    )
    parser.add_argument(
        "-p",
        "--password",
        metavar="password",
        type=str,
        help="MS Account password",
        required=True,
    )
    parser.add_argument(
        "-m",
        "--mfa",
        metavar="secret",
        type=str,
        help="TOTP secret. Required, if you have set up 2FA with your MS account (only TOTP)",
        required=False,
    )

    parser.add_argument(
        "--vpn_url",
        nargs="?",
        metavar="url",
        type=str,
        help="Login URL",
        default="https://vpn.fhnw.ch",
    )
    parser.add_argument(
        "--show-head",
        action="store_false",
        help="If the browser window should be shown during the authentication process",
    )

    parser.add_argument(
        "--print-to-stdout",
        action="store_true",
        help="""If the vpn host and cookie should be printed to the stdout. To be used like:\n
            \n
            eval $( python ocma/cli.py -u [username] -p [password] --print-to-stdout ); \n
            [ -n $VPN_COOKIE ] && echo $VPN_COOKIE | sudo openconnect --cookie-on-stdin $VPN_HOST
        """,
    )

    # parse the arguments from standard input
    args = parser.parse_args()

    username: str = args.username
    password: str = args.password
    mfa_secret: str = args.mfa
    vpn_url: str = args.vpn_url
    headless: bool = args.show_head
    print_to_stdout: bool = args.print_to_stdout

    if username is None or password is None:
        raise ValueError("Username and password must be specified!")

    if mfa_secret is not None:
        try:
            connect.get_mfa_code(mfa_secret)

        except ValueError as e:
            raise ValueError(f"Your MFA secret '{mfa_secret}' is invalid!") from e

    cookie = connect.login(
        username=username,
        password=password,
        mfa_secret=mfa_secret,
        vpn_site=vpn_url,
        headless=headless,
    )

    if print_to_stdout:
        print(f"VPN_HOST={cookie.domain}")
        print(f"VPN_COOKIE={cookie.cookie}")


if __name__ == "__main__":
    run()
