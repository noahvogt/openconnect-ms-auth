"""Openconnect-Microsoft-login connection helpers."""

import logging
import time
from dataclasses import dataclass
from urllib.parse import urlparse

from otppy import OTP
from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait

USERNAME_INPUT_NAME = "loginfmt"
PASSWORD_INPUT_NAME = "passwd"
MFA_INPUT_NAME = "otc"
CONTINUE_BUTTON_ID = "idSIButton9"
MFA_CONTINUE_BUTTON_ID = "idSubmit_SAOTCC_Continue"
MFA_ERROR_TEXT_ID = "idSpan_SAOTCC_Error_OTC"
VPN_INSTALL_PAGE_EXCLUSIVE_ELEMENT_ID = "provisioning_action_label"
MAX_RETRY_DOMAIN_CHECK = 16
MFA_MAX_RETRY_COUNT = 3
ELEMENT_CHECK_DELAY = 0.5
DOMAIN_CHECK_DELAY = 0.5

LOGGER = logging.getLogger("OCMA")
LOGGER.setLevel(logging.INFO)


@dataclass
class VPNCookie:
    """VPN cookie data container."""

    domain: str
    cookie: str


def login(  # noqa: PLR0913
    username: str,
    password: str,
    mfa_secret: str | None = None,
    vpn_site: str = "https://vpn.fhnw.ch",
    headless: bool = True,
    log_messages: bool = False,
) -> VPNCookie:
    """
    Log in to the vpn.

    Parameters
    ----------
    username : str
        Microsoft account username.
    password : str
        Microsoft account password.
    mfa_secret : str | None, optional
        Multifactor secret, by default None
    vpn_site : str, optional
        VPN site to log into, by default "https://vpn.fhnw.ch"
    headless : bool, optional
        If the browser should be run in headless mode, by default True
    log_messages : bool, optional
        If messages should be logged to the console, by default False

    Returns
    -------
    VPNCookie
        Cookie to log into the openconnect VPN.

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
        options.add_argument("--headless")  # type: ignore

    driver = webdriver.Firefox(options=options)
    driver.get(vpn_site)

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
    _is_on_install_page(driver)
    return _get_webvpn_cookie(driver)


def _fill_login(driver: webdriver.Firefox, username: str, password: str) -> None:
    LOGGER.info("Filling in login information")

    _check_on_ms_login_page(driver)

    if not _find_element(driver, By.NAME, USERNAME_INPUT_NAME):
        raise ValueError("Could not find login page!")

    if not _element_interactable(driver, By.NAME, USERNAME_INPUT_NAME):
        raise ValueError("Could not find username field!")
    driver.find_element(By.NAME, USERNAME_INPUT_NAME).send_keys(username)
    click_continue(driver)

    if _find_element(driver, by=By.ID, item="usernameError", wait=5):
        error_msg = driver.find_element(By.ID, "usernameError").text
        LOGGER.error("Invalid username or other error (Message: %s)", error_msg)
        raise ValueError(f"Invalid username or other error (Message: {error_msg})")

    if not _element_interactable(driver, By.NAME, PASSWORD_INPUT_NAME):
        raise ValueError("Could not find password input!")
    driver.find_element(By.NAME, PASSWORD_INPUT_NAME).send_keys(password)
    click_continue(driver)

    if _find_element(driver, by=By.ID, item="passwordError", wait=5):
        error_msg = driver.find_element(By.ID, "passwordError").text
        LOGGER.error("Invalid password or other error (Message: %s)", error_msg)
        raise ValueError(f"Invalid password or other error (Message: {error_msg})")

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
        if not _find_element(driver, By.ID, MFA_ERROR_TEXT_ID, 2):
            # Did not find an error
            LOGGER.info("MFA seems to have been accepted, no errors")
            break


def _check_approval_screen(driver: webdriver.Firefox) -> None:
    if not _find_element(driver, By.ID, "idDiv_SAOTCAS_Title"):
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

    except ElementNotInteractableException:
        return False

    return True


def _is_on_install_page(driver: webdriver.Firefox) -> None:
    if not _find_element(driver, By.ID, VPN_INSTALL_PAGE_EXCLUSIVE_ELEMENT_ID):
        raise ValueError("Could not find install page!")


def _get_webvpn_cookie(driver: webdriver.Firefox) -> VPNCookie:
    webvpn_cookie = driver.get_cookie("webvpn")
    driver.close()

    if webvpn_cookie is None:
        raise ValueError(
            "Failed to find the webvpn cookie. Maybe the authentication has failed?",
        )

    webvpn_domain = webvpn_cookie["domain"]
    webvpn_value = webvpn_cookie["value"]
    return VPNCookie(domain=webvpn_domain, cookie=webvpn_value)


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
    btn_id : str, optional
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
    Get the multifactor authentication code for the given secret.

    Parameters
    ----------
    secret : str
        MFA secret

    Returns
    -------
    str
        MFA code
    """
    otp = OTP.fromb32(secret)
    code: str = otp.TOTP()[0]
    return code
