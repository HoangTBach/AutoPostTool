from urllib.parse import urlsplit, urlunsplit

from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

PAGE_READY_TIMEOUT = 30


class FacebookSwitchError(RuntimeError):
    def __init__(
        self,
        message: str,
        retryable: bool = True,
    ):
        super().__init__(message)
        self.retryable = retryable


# ----- Facebook Helpers -----
def _normalize_page_link(page_link: str) -> str:
    link = str(page_link or "").strip()

    if not link:
        raise FacebookSwitchError(
            "page_link is missing in Excel.",
            retryable=False,
        )

    if any(char.isspace() for char in link):
        raise FacebookSwitchError(
            f"Invalid page_link: {link}",
            retryable=False,
        )

    if link.startswith("//"):
        link = f"https:{link}"
    elif "://" not in link:
        link = f"https://{link}"

    try:
        parsed = urlsplit(link)
        hostname = (parsed.hostname or "").lower()
    except ValueError as error:
        raise FacebookSwitchError(
            f"Invalid page_link: {link}",
            retryable=False,
        ) from error

    is_facebook_url = (
        hostname == "facebook.com"
        or hostname.endswith(".facebook.com")
        or hostname == "fb.com"
        or hostname.endswith(".fb.com")
    )

    if parsed.scheme not in ("http", "https") or not is_facebook_url:
        raise FacebookSwitchError(
            f"page_link is not a valid Facebook URL: {link}",
            retryable=False,
        )

    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path or "/",
            parsed.query,
            parsed.fragment,
        )
    )


def _wait_for_page_ready(driver) -> None:
    try:
        WebDriverWait(
            driver,
            PAGE_READY_TIMEOUT,
        ).until(
            lambda browser: browser.execute_script("return document.readyState")
            in ("interactive", "complete")
        )

    except TimeoutException as error:
        raise FacebookSwitchError(
            "Timed out while waiting for the Facebook page to load.",
            retryable=True,
        ) from error

    except WebDriverException as error:
        raise FacebookSwitchError(
            f"Cannot wait for the Facebook page to load: {error}",
            retryable=True,
        ) from error


def _check_facebook_login(driver) -> None:
    current_url = str(driver.current_url or "").lower()

    try:
        path = urlsplit(current_url).path.lower()
    except ValueError:
        path = ""

    login_paths = (
        "/login",
        "/checkpoint",
        "/recover",
    )

    if any(
        path == login_path
        or path.startswith(f"{login_path}/")
        or path.startswith(f"{login_path}.")
        for login_path in login_paths
    ):
        raise FacebookSwitchError(
            "Facebook requires login or checkpoint verification.",
            retryable=False,
        )

    try:
        email_fields = driver.find_elements(
            By.CSS_SELECTOR,
            'input[name="email"], input[type="email"]',
        )

        password_fields = driver.find_elements(
            By.CSS_SELECTOR,
            'input[name="pass"], input[type="password"]',
        )

        has_visible_email = any(element.is_displayed() for element in email_fields)

        has_visible_password = any(
            element.is_displayed() for element in password_fields
        )

        if has_visible_email and has_visible_password:
            raise FacebookSwitchError(
                "Facebook login is required. "
                "Please log in to the AdsPower profile first.",
                retryable=False,
            )

    except FacebookSwitchError:
        raise

    except WebDriverException as error:
        raise FacebookSwitchError(
            f"Cannot check Facebook login status: {error}",
            retryable=True,
        ) from error


# ----- Facebook Open Page Link -----
def open_page_link(driver, page_link: str) -> str:
    url = _normalize_page_link(page_link)

    try:
        driver.get(url)

    except TimeoutException:
        pass

    except WebDriverException as error:
        raise FacebookSwitchError(
            f"Cannot open page_link: {url}. Error: {error}",
            retryable=True,
        ) from error

    _wait_for_page_ready(driver)
    _check_facebook_login(driver)

    current_url = str(driver.current_url or "").strip()

    if not current_url or current_url == "about:blank":
        raise FacebookSwitchError(
            "Facebook page did not open successfully.",
            retryable=True,
        )

    return current_url


def switch_to_page(
    driver,
    page_link: str = "",
) -> str:
    return open_page_link(driver, page_link)
