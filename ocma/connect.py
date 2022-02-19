import time
from dataclasses import dataclass
from typing import Optional

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

    try:
        w = WebDriverWait(driver, 8)
        w.until(EC.presence_of_element_located((By.NAME, "loginfmt")))

    except TimeoutException:
        raise ValueError("Could not find login page!")

    driver.find_element(By.NAME, "loginfmt").send_keys(username)
    driver.find_element(By.NAME, "passwd").send_keys(password)
    click_continue(driver)  # Confirm username
    click_continue(driver)  # Confirm password

    # Check if we have to enter a MFA code
    if mfa_secret is not None:
        for _ in range(6):
            has_mfa_code_entry(driver)
            mfa_code = get_mfa_code(mfa_secret)
            driver.find_element(By.NAME, "otc").send_keys(mfa_code)
            click_continue(driver, "idSubmit_SAOTCC_Continue")  # Confirm otp

            # Check for any errors
            try:
                w = WebDriverWait(driver, 2)
                w.until(
                    EC.presence_of_element_located((By.ID, "idSpan_SAOTCC_Error_OTC"))
                )
            except TimeoutException:
                break

    click_continue(driver)  # Confirm stay signed in

    # Wait until we have the install page
    try:
        w = WebDriverWait(driver, 8)
        w.until(EC.presence_of_element_located((By.ID, "provisioning_action_label")))
    except TimeoutException:
        raise ValueError("Could not find install page!")

    webvpn_cookie = driver.get_cookie("webvpn")
    driver.close()

    if webvpn_cookie is None:
        raise ValueError(
            "Failed to find the webvpn cookie. Maybe the authentication has failed?"
        )

    webvpn_domain = webvpn_cookie["domain"]
    webvpn_value = webvpn_cookie["value"]

    return VPNCookie(domain=webvpn_domain, cookie=webvpn_value)


def click_continue(driver: webdriver.Firefox, btn_id: str = "idSIButton9") -> bool:
    """Returns true if still on login page, false if not"""
    for _ in range(16):
        try:
            driver.find_element(By.ID, btn_id).click()
            return True

        except (ElementClickInterceptedException, StaleElementReferenceException):
            pass
        except NoSuchElementException:
            if ".fhnw.ch" in driver.current_url:
                return False

        time.sleep(0.5)

    return ".fhnw.ch" not in driver.current_url


def get_mfa_code(secret: str) -> str:
    otp = OTP.fromb32(secret)
    code: str = otp.TOTP()[0]
    return code


def has_mfa_code_entry(driver: webdriver.Firefox) -> bool:
    try:
        w = WebDriverWait(driver, 8)
        w.until(EC.presence_of_element_located((By.NAME, "otc")))
        return True

    except TimeoutException:
        return False
