"""Openconnect-Microsoft-login connection helpers."""

import json
import logging
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import pyotp
from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait

USERNAME_INPUT_NAME = "loginfmt"
USERNAME_ERROR_ID = "usernameError"
PASSWORD_ERROR_ID = "passwordError"
APPROVAL_TITLE_ID = "idDiv_SAOTCAS_Title"
PASSWORD_INPUT_NAME = "passwd"
MFA_INPUT_NAME = "otc"
CONTINUE_BUTTON_ID = "idSIButton9"
MFA_CONTINUE_BUTTON_ID = "idSubmit_SAOTCC_Continue"
MFA_ERROR_TEXT_ID = "idSpan_SAOTCC_Error_OTC"
MAX_RETRY_DOMAIN_CHECK = 16
MAX_RETRY_COOKIE_CHECK = 16
STEP_TIMEOUT = 15
APPROVAL_CHECK_TIMEOUT = 8
MFA_RESULT_TIMEOUT = 2
SESSION_CHECK_TIMEOUT = 10
MS_LOGIN_URL = "https://login.microsoftonline.com/"
SESSION_COOKIE_DOMAIN = "microsoftonline.com"
MFA_MAX_RETRY_COUNT = 3
ELEMENT_CHECK_DELAY = 0.5
DOMAIN_CHECK_DELAY = 0.5
COOKIE_CHECK_DELAY = 0.5

LOGGER = logging.getLogger("OCMA")
LOGGER.setLevel(logging.INFO)


@dataclass
class VPNCookie:
    """VPN cookie data container."""

    domain: str
    cookie: str
    session: str | None = None


def login(  # noqa: PLR0913,PLR0917 # pylint: disable=too-many-arguments,too-many-positional-arguments
    username: str,
    password: str,
    mfa_secret: str | None = None,
    vpn_site: str = "https://vpn.fhnw.ch",
    headless: bool = True,
    log_messages: bool = False,
    session: str | None = None,
) -> VPNCookie:
    """
    Log in to the vpn.

    Parameters
    ----------
    username : str
        Microsoft account username.
    password : str
        Microsoft account password.
    mfa_secret : str | None
        Multi-factor secret, by default None
    vpn_site : str
        VPN site to log into, by default "https://vpn.fhnw.ch"
    headless : bool
        If the browser should be run in headless mode, by default True
    log_messages : bool
        If messages should be logged to the console, by default False
    session : str | None
        Session cookies of an earlier login, as stored by a previous run, by
        default None. A session that is still valid skips the login entirely.

    Returns
    -------
    VPNCookie
        Cookie to log into the openconnect VPN. Its `session` holds the session
        cookies to store when a full login was needed, and None otherwise.

    Raises
    ------
    ValueError
        If anything went sideways during the login.
    """
    if log_messages:
        formatter = logging.Formatter(
            "%(asctime)s: %(levelname)s - %(name)s - %(message)s",
        )
        fh_s = logging.StreamHandler()
        fh_s.setLevel(logging.INFO)
        fh_s.setFormatter(formatter)
        LOGGER.addHandler(fh_s)

    LOGGER.info("Starting")

    options = FirefoxOptions()
    if headless:
        LOGGER.info("Running in headless mode")
        options.add_argument("--headless")

    driver = webdriver.Firefox(options=options)

    try:
        if session:
            _restore_session(driver, session)

        driver.get(vpn_site)

        if session and _skip_login_with_session(driver):
            LOGGER.info("Reused the stored session, no login needed")
            return _get_webvpn_cookie(driver, vpn_site)

        retries = MAX_RETRY_DOMAIN_CHECK
        while not _is_on_ms_login_page(driver) and retries > 0:
            retries -= 1
            time.sleep(DOMAIN_CHECK_DELAY)

        if retries < 0:
            raise ValueError(
                f"We never reached the MS login page! Currently on {driver.current_url}",
            )

        _fill_login(driver, username, password)
        _fill_mfa(driver, mfa_secret)
        _confirm_stay_signed_in(driver)

        vpn_cookie = _get_webvpn_cookie(driver, vpn_site)
        vpn_cookie.session = _dump_session(driver)

    finally:
        driver.quit()

    return vpn_cookie


def _restore_session(driver: webdriver.Firefox, session: str) -> None:
    # Cookies can only be added for the domain the browser is currently on.
    try:
        cookies = json.loads(session)

    except json.JSONDecodeError:
        LOGGER.warning("The stored session is not valid JSON, ignoring it")
        return

    LOGGER.info("Restoring %s session cookies", len(cookies))
    driver.get(MS_LOGIN_URL)

    for cookie in cookies:
        try:
            driver.add_cookie(cookie)

        except WebDriverException:
            LOGGER.info("Could not restore one of the session cookies")


def _dump_session(driver: webdriver.Firefox) -> str | None:
    driver.get(MS_LOGIN_URL)
    cookies = [
        cookie
        for cookie in driver.get_cookies()
        if SESSION_COOKIE_DOMAIN in cookie.get("domain", "")
    ]

    if not cookies:
        LOGGER.info("Found no session cookies to store")
        return None

    LOGGER.info("Storing %s session cookies", len(cookies))
    return json.dumps(cookies)


def _skip_login_with_session(driver: webdriver.Firefox) -> bool:
    # Either the portal hands out the cookie right away, or the session is
    # spent and we are back at the login form.
    _wait_for_any(
        driver,
        [
            lambda d: d.get_cookie("webvpn") is not None,
            ec.presence_of_element_located((By.NAME, USERNAME_INPUT_NAME)),
        ],
        SESSION_CHECK_TIMEOUT,
    )

    if driver.get_cookie("webvpn") is not None:
        return True

    # Leftovers of a spent session can land us on an account picker or a
    # prefilled form, neither of which _fill_login knows how to drive.
    LOGGER.info("The stored session did not work out, starting clean")
    driver.delete_all_cookies()
    driver.get(driver.current_url)
    return False


def _fill_login(driver: webdriver.Firefox, username: str, password: str) -> None:
    LOGGER.info("Filling in login information")

    _check_on_ms_login_page(driver)

    if not _element_interactable(driver, By.NAME, USERNAME_INPUT_NAME):
        raise ValueError("Could not find username field!")
    driver.find_element(By.NAME, USERNAME_INPUT_NAME).send_keys(username)
    click_continue(driver)

    if not _wait_for_any(
        driver,
        [
            ec.element_to_be_clickable((By.NAME, PASSWORD_INPUT_NAME)),
            ec.presence_of_element_located((By.ID, USERNAME_ERROR_ID)),
        ],
        STEP_TIMEOUT,
    ):
        raise ValueError("Could not find password input!")

    _raise_on_error(driver, USERNAME_ERROR_ID, "Invalid username or other error")

    driver.find_element(By.NAME, PASSWORD_INPUT_NAME).send_keys(password)
    click_continue(driver)

    # After the password the page moves on to the MFA code, to the approval
    # screen, or straight off the login pages, depending on the account.
    if not _wait_for_any(
        driver,
        [
            ec.presence_of_element_located((By.ID, PASSWORD_ERROR_ID)),
            ec.presence_of_element_located((By.NAME, MFA_INPUT_NAME)),
            ec.presence_of_element_located((By.ID, APPROVAL_TITLE_ID)),
            lambda d: not _is_on_ms_login_page(d),
        ],
        STEP_TIMEOUT,
    ):
        raise ValueError("The login did not continue after the password!")

    _raise_on_error(driver, PASSWORD_ERROR_ID, "Invalid password or other error")

    retries = MAX_RETRY_DOMAIN_CHECK
    while on_login_form(driver) and retries > 0:
        LOGGER.info(
            "Login information may not have yet been confirmed. Checking again (Try %s of %s)",
            MAX_RETRY_DOMAIN_CHECK - retries + 1,
            MAX_RETRY_DOMAIN_CHECK,
        )
        time.sleep(ELEMENT_CHECK_DELAY)

        if on_login_form(driver):
            LOGGER.info("Login information has not yet been confirmed. Trying again")
            click_continue(driver)  # Confirm password
        retries -= 1

    if retries < 0:
        raise ValueError("Failed to confirm login form!")

    LOGGER.info("Login information filled out")


def on_login_form(driver: webdriver.Firefox) -> bool:
    """
    Check if we are on the login form.

    Parameters
    ----------
    driver : webdriver.Firefox
        The web driver to check on.

    Returns
    -------
    bool
        True if we are on the login form, else false.
    """
    return "saml2" in driver.current_url  # or driver.current_url.endswith("login")


def _fill_mfa(driver: webdriver.Firefox, mfa_secret: str | None) -> None:
    LOGGER.info("Checking if we can fill in MFA information")

    _check_on_ms_login_page(driver)

    # Check if we have the MFA page
    if driver.current_url.endswith("/login") and mfa_secret is None:
        raise ValueError("You need to supply your MFA secret to log in!")

    _check_approval_screen(driver)

    # Check if we have an MFA code to enter
    if mfa_secret is None:
        LOGGER.info("Filling in login information")
        return

    for i in range(MFA_MAX_RETRY_COUNT):
        LOGGER.info(
            "Filling in MFA information (Try %s of %s)",
            i + 1,
            MFA_MAX_RETRY_COUNT,
        )
        if not _find_element(driver, By.NAME, MFA_INPUT_NAME):
            time.sleep(ELEMENT_CHECK_DELAY)
            continue

        mfa_code = get_mfa_code(mfa_secret)
        driver.find_element(By.NAME, MFA_INPUT_NAME).send_keys(mfa_code)
        click_continue(driver, MFA_CONTINUE_BUTTON_ID)  # Confirm otp

        LOGGER.info("Confirmed MFA code")

        if not driver.current_url.endswith("/login"):
            # We have moved on
            LOGGER.info("We have moved away from the MFA page")
            break

        # Check for any errors
        _wait_for_any(
            driver,
            [
                ec.presence_of_element_located((By.ID, MFA_ERROR_TEXT_ID)),
                lambda d: not d.current_url.endswith("/login"),
            ],
            MFA_RESULT_TIMEOUT,
        )
        if not driver.find_elements(By.ID, MFA_ERROR_TEXT_ID):
            # Did not find an error
            LOGGER.info("MFA seems to have been accepted, no errors")
            break


def _check_approval_screen(driver: webdriver.Firefox) -> None:
    # The approval screen is optional, so race it against the code input.
    if not _wait_for_any(
        driver,
        [
            ec.presence_of_element_located((By.ID, APPROVAL_TITLE_ID)),
            ec.presence_of_element_located((By.NAME, MFA_INPUT_NAME)),
        ],
        APPROVAL_CHECK_TIMEOUT,
    ):
        return

    if not driver.find_elements(By.ID, APPROVAL_TITLE_ID):
        return

    found_sign_in_other_way = False
    for _ in range(16):
        try:
            driver.find_element(By.ID, "signInAnotherWay").click()
            found_sign_in_other_way = True
            break

        except (ElementClickInterceptedException, StaleElementReferenceException):
            pass
        except NoSuchElementException:
            pass

        time.sleep(ELEMENT_CHECK_DELAY)

    if not found_sign_in_other_way:
        raise ValueError("Failed to find the option to sing in another way!")

    for _ in range(16):
        try:
            driver.find_element(By.XPATH, "//div[@data-value='PhoneAppOTP']").click()
            break

        except (ElementClickInterceptedException, StaleElementReferenceException):
            pass
        except NoSuchElementException:
            pass

        time.sleep(ELEMENT_CHECK_DELAY)

    return


def _confirm_stay_signed_in(driver: webdriver.Firefox) -> bool:
    LOGGER.info("Checking if we should confirm if we should stay signed in")

    if not _is_on_ms_login_page(driver):
        LOGGER.info("Already logged in, can't confirm 'stay signed in'")
        return False

    if not driver.current_url.endswith("/common/SAS/ProcessAuth"):
        LOGGER.info(
            "We have reached a dead end. We have completed the login, but not on the 'stay signed in' page",
        )
        return False

    click_continue(driver)  # Confirm stay signed in
    LOGGER.info("Confirmed to 'stay signed in'")
    return True


def _wait_for_any(
    driver: webdriver.Firefox,
    conditions: list[Any],
    timeout: float,
) -> bool:
    # Racing the expected next step against the error message keeps a
    # successful login from waiting out the timeout of an error that the page
    # never shows.
    try:
        WebDriverWait(driver, timeout).until(ec.any_of(*conditions))

    except TimeoutException:
        return False

    return True


def _raise_on_error(driver: webdriver.Firefox, error_id: str, message: str) -> None:
    errors = driver.find_elements(By.ID, error_id)
    if not errors:
        return

    error_msg = errors[0].text
    LOGGER.error("%s (Message: %s)", message, error_msg)
    raise ValueError(f"{message} (Message: {error_msg})")


def _find_element(driver: webdriver.Firefox, by: str, item: str, wait: int = 8) -> bool:
    try:
        w = WebDriverWait(driver, wait)
        w.until(ec.presence_of_element_located((by, item)))

    except TimeoutException:
        return False

    return True


def _element_interactable(
    driver: webdriver.Firefox,
    by: str,
    item: str,
    wait: int = 8,
) -> bool:
    try:
        w = WebDriverWait(driver, wait)
        w.until(ec.element_to_be_clickable((by, item)))

    except (ElementNotInteractableException, TimeoutException):
        return False

    return True


def _poll_webvpn_cookie(driver: webdriver.Firefox) -> dict[str, Any] | None:
    for _ in range(MAX_RETRY_COOKIE_CHECK):
        webvpn_cookie = driver.get_cookie("webvpn")
        if webvpn_cookie is not None:
            return webvpn_cookie

        time.sleep(COOKIE_CHECK_DELAY)

    return None


def _get_webvpn_cookie(driver: webdriver.Firefox, vpn_site: str) -> VPNCookie:
    LOGGER.info("Waiting for the webvpn cookie")
    webvpn_cookie = _poll_webvpn_cookie(driver)

    if webvpn_cookie is None:
        # Which page the portal ends up on differs between sessions, and the
        # cookie is only readable from the VPN domain it belongs to.
        LOGGER.info("No cookie on %s, going back to %s", driver.current_url, vpn_site)
        driver.get(vpn_site)
        webvpn_cookie = _poll_webvpn_cookie(driver)

    if webvpn_cookie is None:
        raise ValueError(
            f"Failed to find the webvpn cookie, ended up on {driver.current_url}. "
            "Maybe the authentication has failed?",
        )

    return VPNCookie(
        domain=webvpn_cookie["domain"],
        cookie=webvpn_cookie["value"],
    )


def _check_on_ms_login_page(driver: webdriver.Firefox) -> None:
    if not _is_on_ms_login_page(driver):
        raise ValueError("We should still be on the MS login page but we aren't!")


def _is_on_ms_login_page(driver: webdriver.Firefox) -> bool:
    return urlparse(driver.current_url).netloc == "login.microsoftonline.com"


def click_continue(driver: webdriver.Firefox, btn_id: str = CONTINUE_BUTTON_ID) -> bool:
    """
    Click the continue button.

    Parameters
    ----------
    driver : webdriver.Firefox
        The driver for which to click the continue button.
    btn_id : str
        The buttons ID to be clicked, by default CONTINUE_BUTTON_ID

    Returns
    -------
    bool
        True if still on login page, false if not.
    """
    for _ in range(16):
        try:
            driver.find_element(By.ID, btn_id).click()
        except (ElementClickInterceptedException, StaleElementReferenceException):
            pass
        except NoSuchElementException:
            pass
        else:
            return True

        time.sleep(ELEMENT_CHECK_DELAY)
    return False


def get_mfa_code(secret: str) -> str:
    """
    Get the multi-factor authentication code for the given secret.

    Parameters
    ----------
    secret : str
        MFA secret, base32 encoded. pyotp raises a ValueError for an invalid one.

    Returns
    -------
    str
        MFA code
    """
    code: str = pyotp.TOTP(secret).now()
    return code
