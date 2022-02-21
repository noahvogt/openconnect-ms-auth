import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from otppy import OTP
from selenium import webdriver
from selenium.common.exceptions import ElementClickInterceptedException
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

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


@dataclass
class VPNCookie:
    domain: str
    cookie: str


def login(
    username: str,
    password: str,
    mfa_secret: Optional[str] = None,
    vpn_site: str = "https://vpn.fhnw.ch",
    headless: bool = True,
) -> VPNCookie:
    options = FirefoxOptions()

    if headless:
        options.add_argument("--headless")

    driver = webdriver.Firefox(options=options)
    driver.get(vpn_site)

    retries = MAX_RETRY_DOMAIN_CHECK
    while not _is_on_ms_login_page(driver) and retries > 0:
        retries -= 1
        time.sleep(DOMAIN_CHECK_DELAY)

    if retries < 0:
        raise ValueError("We never reached the MS login page!")

    _fill_login(driver, username, password)
    _fill_mfa(driver, mfa_secret)
    _confirm_stay_signed_in(driver)
    _is_on_install_page(driver)
    return _get_webvpn_cookie(driver)


def _fill_login(driver: webdriver.Firefox, username: str, password: str) -> None:
    _check_on_ms_login_page(driver)

    if not _find_element(driver, By.NAME, USERNAME_INPUT_NAME):
        raise ValueError("Could not find login page!")

    driver.find_element(By.NAME, USERNAME_INPUT_NAME).send_keys(username)
    driver.find_element(By.NAME, PASSWORD_INPUT_NAME).send_keys(password)
    click_continue(driver)  # Confirm username
    click_continue(driver)  # Confirm password


def _fill_mfa(driver: webdriver.Firefox, mfa_secret: Optional[str]) -> None:
    _check_on_ms_login_page(driver)

    # Check if we have the MFA page
    if driver.current_url.endswith("/login") and mfa_secret is None:
        raise ValueError("You need to supply your MFA secret to log in!")

    # Check if we have an MFA code to enter
    if mfa_secret is None:
        return

    for _ in range(MFA_MAX_RETRY_COUNT):
        if not _find_element(driver, By.NAME, MFA_INPUT_NAME):
            time.sleep(ELEMENT_CHECK_DELAY)
            continue

        mfa_code = get_mfa_code(mfa_secret)
        driver.find_element(By.NAME, MFA_INPUT_NAME).send_keys(mfa_code)
        click_continue(driver, MFA_CONTINUE_BUTTON_ID)  # Confirm otp

        if not driver.current_url.endswith("/login"):
            # We have moved on
            break

        # Check for any errors
        if not _find_element(driver, By.ID, MFA_ERROR_TEXT_ID, 2):
            # Did not find an error
            break


def _confirm_stay_signed_in(driver: webdriver.Firefox) -> bool:
    if not _is_on_ms_login_page(driver):
        return False

    if not driver.current_url.endswith("/common/SAS/ProcessAuth"):
        return False

    click_continue(driver)  # Confirm stay signed in
    return True


def _find_element(driver: webdriver.Firefox, by: str, item: str, wait: int = 8) -> bool:
    try:
        w = WebDriverWait(driver, wait)
        w.until(EC.presence_of_element_located((by, item)))
        return True

    except TimeoutException:
        return False


def _is_on_install_page(driver: webdriver.Firefox) -> None:
    if not _find_element(driver, By.ID, VPN_INSTALL_PAGE_EXCLUSIVE_ELEMENT_ID):
        raise ValueError("Could not find install page!")


def _get_webvpn_cookie(driver: webdriver.Firefox) -> VPNCookie:
    webvpn_cookie = driver.get_cookie("webvpn")
    driver.close()

    if webvpn_cookie is None:
        raise ValueError(
            "Failed to find the webvpn cookie. Maybe the authentication has failed?"
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
    """Returns true if still on login page, false if not"""
    for _ in range(16):
        try:
            driver.find_element(By.ID, btn_id).click()
            return True

        except (ElementClickInterceptedException, StaleElementReferenceException):
            pass
        except NoSuchElementException:
            pass

        time.sleep(ELEMENT_CHECK_DELAY)
    return False


def get_mfa_code(secret: str) -> str:
    otp = OTP.fromb32(secret)
    code: str = otp.TOTP()[0]
    return code
