import re
import time
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse, urlsplit, urlunsplit

import pyperclip

from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

PAGE_READY_TIMEOUT = 30
PROFILE_SWITCH_TIMEOUT = 12


POST_BUTTON_TIMEOUT = 60
POST_PUBLISH_WAIT_SECONDS = 10
POST_TIMESTAMP_CYCLES = 3
class FacebookPostError(RuntimeError):
    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


class PublishUnknownError(FacebookPostError):
    def __init__(self, message: str):
        super().__init__(message, retryable=False)


POST_ACTIONS = {
    "post",
    "publish",
    "share",
    "đăng",
    "chia sẻ",
}

NEXT_ACTIONS = {
    "next",
    "continue",
    "proceed",
    "tiếp",
    "tiếp theo",
    "tiếp tục",
}

SEE_ALL_PROFILES_ACTIONS = {
    "see all profiles",
    "view all profiles",
    "see all pages",
    "view all pages",
    "manage profiles",
    "xem tất cả trang cá nhân",
    "xem tất cả hồ sơ",
    "xem tất cả trang",
    "xem tất cả các trang",
    "xem tất cả trang và hồ sơ",
    "quản lý hồ sơ",
    "quản lý trang cá nhân",
}

SWITCH_PROFILE_ACTIONS = {
    "switch profile",
    "switch profiles",
    "switch account",
    "switch page",
    "switch to page",
    "chuyển trang cá nhân",
    "chuyển đổi trang cá nhân",
    "chuyển tài khoản",
    "chuyển đổi tài khoản",
    "chuyển sang trang",
    "đổi trang cá nhân",
    "đổi tài khoản",
}

CONFIRM_SWITCH_ACTIONS = {
    "switch now",
    "switch profile now",
    "switch page now",
    "chuyển ngay",
    "chuyển trang cá nhân ngay",
    "chuyển đổi ngay",
    "chuyển sang ngay",
}

_ACTION_SELECTOR = (
    "button, [role='button'], [role='menuitem'], [role='option'], "
    "a[role='button'], a[href], [tabindex='0']"
)
_POPUP_SELECTOR = (
    "[role='menu'], [role='dialog'], [role='listbox'], "
    "[data-pagelet*='ProfilePlusActionsMenu'], "
    "[data-pagelet*='ProfileSwitcher'], "
    "[data-testid*='profile_switcher']"
)


class FacebookSwitchError(RuntimeError):
    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


# ----- Facebook Helpers -----
def _normalize_page_id(page_id: str) -> str:
    value = str(page_id or "").strip()
    if value.endswith(".0") and value[:-2].isdigit():
        value = value[:-2]
    return value


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


def _derive_page_identity(
    page_link: str,
    page_id: str = "",
    page_name: str = "",
) -> tuple[str, str]:
    target_id = _normalize_page_id(page_id)
    target_name = str(page_name or "").strip()
    parsed = urlsplit(page_link)
    path_parts = [unquote(part).strip() for part in parsed.path.split("/") if part]

    query_id = parse_qs(parsed.query).get("id", [""])[0].strip()
    if not target_id and query_id:
        target_id = query_id

    if path_parts and path_parts[-1].isdigit() and not target_id:
        target_id = path_parts[-1]

    if not target_name and path_parts:
        if len(path_parts) >= 3 and path_parts[-3].casefold() == "pages":
            target_name = path_parts[-2]
        elif len(path_parts) >= 2 and path_parts[-2].casefold() == "pages":
            target_name = path_parts[-1]
        elif path_parts[-1].casefold() not in {
            "profile.php",
            "pages",
            "watch",
            "groups",
            "posts",
        } and not path_parts[-1].isdigit():
            target_name = path_parts[-1].lstrip("@")

    return target_id, target_name


def _wait_for_page_ready(driver, timeout: int = PAGE_READY_TIMEOUT) -> None:
    try:
        WebDriverWait(driver, timeout).until(
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

    login_paths = ("/login", "/checkpoint", "/recover")
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
                "Facebook login is required. Please log in to the AdsPower "
                "profile first.",
                retryable=False,
            )
    except FacebookSwitchError:
        raise
    except WebDriverException as error:
        raise FacebookSwitchError(
            f"Cannot check Facebook login status: {error}",
            retryable=True,
        ) from error


def _visible(element) -> bool:
    try:
        return element.is_displayed()
    except Exception:
        return False


def _click(element, driver) -> None:
    try:
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});",
            element,
        )
    except Exception:
        pass

    try:
        element.click()
    except Exception:
        driver.execute_script("arguments[0].click();", element)


def _dom_find_action(driver, labels: set[str], root=None, exact: bool = False):
    return driver.execute_script(
        r"""
        const root = arguments[0] || document;
        const wanted = arguments[1].map(value =>
            String(value || '').normalize('NFC')
                .toLocaleLowerCase().replace(/\s+/g, ' ').trim()
        );
        const exact = arguments[2];
        const selector = arguments[3];
        const visible = element => {
            const style = window.getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            return rect.width > 0 &&
                rect.height > 0 &&
                style.display !== 'none' &&
                style.visibility !== 'hidden' &&
                Number(style.opacity || 1) > 0;
        };
        const norm = value => String(value || '')
            .normalize('NFC')
            .toLocaleLowerCase()
            .replace(/\s+/g, ' ')
            .trim();
        const candidates = Array.from(root.querySelectorAll(selector));
        for (let index = candidates.length - 1; index >= 0; index -= 1) {
            const element = candidates[index];
            if (
                !visible(element) ||
                element.getAttribute('aria-disabled') === 'true' ||
                element.disabled
            ) {
                continue;
            }
            const values = [
                element.getAttribute('aria-label'),
                element.getAttribute('title'),
                element.innerText,
                element.textContent
            ].map(norm).filter(Boolean);
            const matched = wanted.some(label =>
                values.some(value => {
                    if (exact) {
                        return value === label || value.startsWith(label + ' ');
                    }
                    return value === label ||
                        value.startsWith(label) ||
                        value.includes(label);
                })
            );
            if (matched) {
                return element;
            }
        }
        return null;
        """,
        root,
        sorted(labels),
        exact,
        _ACTION_SELECTOR,
    )


def _find_account_menu_candidates(driver):
    return driver.execute_script(r"""
        const visible = element => {
            const style = window.getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            return rect.width > 0 &&
                rect.height > 0 &&
                style.display !== 'none' &&
                style.visibility !== 'hidden' &&
                Number(style.opacity || 1) > 0;
        };
        const norm = value => String(value || '')
            .normalize('NFC')
            .toLocaleLowerCase()
            .replace(/\s+/g, ' ')
            .trim();
        const selectors = [
            '[data-testid="blue_bar_profile_link"]',
            '[aria-label*="account, your profile and settings" i]',
            '[aria-label*="your profile and settings" i]',
            '[aria-label*="tài khoản, trang cá nhân của bạn" i]',
            '[aria-label*="your profile" i]',
            '[aria-label*="your account" i]',
            '[aria-label*="profile and settings" i]',
            '[aria-label*="account menu" i]',
            '[aria-label*="tài khoản" i]',
            '[aria-label*="trang cá nhân" i]',
            '[aria-label*="profile" i]',
            'button[title*="account" i]',
            '[role="button"][title*="account" i]'
        ];
        const found = new Map();
        for (const selector of selectors) {
            for (const matched of document.querySelectorAll(selector)) {
                const element = matched.closest(
                    'button, [role="button"], [tabindex="0"]'
                ) || matched;
                if (!visible(element)) continue;
                // Do not click a normal profile link: it navigates instead of opening the menu.
                if (element.tagName === 'A' &&
                    !element.matches('[role="button"], [tabindex="0"], [data-testid="blue_bar_profile_link"]')) {
                    continue;
                }
                const rect = element.getBoundingClientRect();
                const label = norm([
                    element.getAttribute('aria-label'),
                    element.getAttribute('title'),
                    matched.getAttribute('aria-label'),
                    matched.getAttribute('title'),
                    element.getAttribute('data-testid'),
                    matched.getAttribute('data-testid')
                ].filter(Boolean).join(' '));

                // These are different header controls, not the account/profile menu.
                const unrelated = [
                    'cài đặt và kiểm soát tài khoản',
                    'settings and account controls',
                    'messenger', 'thông báo', 'notifications',
                    'menu trên facebook', 'facebook menu',
                    'trung tâm quảng cáo', 'ads manager',
                    'bảng điều khiển dành cho doanh nghiệp', 'business dashboard',
                    'business suite'
                ];
                const exactAccount = [
                    'tài khoản, trang cá nhân của bạn',
                    'account, your profile and settings',
                    'account, profile and settings',
                    'your profile and settings',
                    'profile and settings',
                    'your account and settings'
                ].some(value => label.includes(value));
                if (!exactAccount && unrelated.some(value => label.includes(value))) {
                    continue;
                }

                const centerX = rect.left + rect.width / 2;
                let score = 0;
                if (centerX >= window.innerWidth * 0.70) score += 100;
                else if (centerX >= window.innerWidth * 0.50) score += 35;
                else score -= 30;
                if (rect.top < 150) score += 40;
                else if (rect.top < 240) score += 15;
                if (exactAccount) score += 220;
                if (label.includes('blue_bar_profile_link')) score += 180;
                if (label.includes('tài khoản, trang cá nhân của bạn')) score += 60;
                if (label.includes('your profile and settings')) score += 60;
                if (label.includes('your profile')) score += 35;
                if (label.includes('trang cá nhân')) score += 25;
                if (label.includes('tài khoản')) score += 15;
                if (element.matches('button, [role="button"], [tabindex="0"]')) score += 10;
                if (element.querySelector('img, svg')) score += 5;
                if (!found.has(element) || found.get(element).score < score) {
                    found.set(element, {element, score});
                }
            }
        }
        return Array.from(found.values())
            .sort((left, right) => right.score - left.score)
            .map(item => item.element);
    """)


def _find_account_menu(driver):
    candidates = _find_account_menu_candidates(driver)
    return candidates[0] if candidates else None


def _visible_popup(driver, page_name: str = "", page_id: str = ""):
    return driver.execute_script(
        r"""
        const pageName = String(arguments[1] || '')
            .normalize('NFC').toLocaleLowerCase().replace(/\s+/g, ' ').trim();
        const pageId = String(arguments[2] || '').trim();
        const selectors = arguments[0];
        const actionSelector =
            'button, [role="button"], [role="menuitem"], [role="option"], '
            + '[role="link"], a[href], [tabindex="0"]';
        const visible = element => {
            const style = window.getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            return rect.width > 0 &&
                rect.height > 0 &&
                style.display !== 'none' &&
                style.visibility !== 'hidden' &&
                Number(style.opacity || 1) > 0;
        };
        const norm = value => String(value || '')
            .normalize('NFC')
            .toLocaleLowerCase()
            .replace(/\s+/g, ' ')
            .trim();
        const accountHints = [
            'see all profiles', 'view all profiles', 'see all pages',
            'view all pages', 'settings & privacy', 'settings and privacy',
            'account center', 'help & support', 'log out', 'manage profiles',
            'xem tất cả trang cá nhân', 'xem tất cả hồ sơ',
            'xem tất cả trang', 'xem tất cả các trang',
            'cài đặt và quyền riêng tư', 'cài đặt & quyền riêng tư',
            'trung tâm tài khoản', 'trợ giúp và hỗ trợ', 'đăng xuất',
            'quản lý trang cá nhân', 'chọn trang cá nhân', 'chọn hồ sơ'
        ];
        const switchHints = [
            'switch profile', 'switch profiles', 'switch account',
            'switch page', 'switch to page', 'profile switcher',
            'select a profile', 'choose a profile', 'select profile',
            'chuyển trang cá nhân', 'chuyển đổi trang cá nhân',
            'chuyển tài khoản', 'chuyển đổi tài khoản',
            'chuyển sang trang', 'chọn trang cá nhân', 'chọn hồ sơ',
            'xem tất cả trang cá nhân', 'xem tất cả hồ sơ'
        ];
        const profileAttributes = [
            'profileplusactionsmenu', 'profileswitcher', 'profile_switcher'
        ];
        const candidates = Array.from(document.querySelectorAll(selectors))
            .filter(visible)
            .map(element => {
                const rect = element.getBoundingClientRect();
                const style = window.getComputedStyle(element);
                const text = norm([
                    element.getAttribute('aria-label'),
                    element.getAttribute('title'),
                    element.getAttribute('data-pagelet'),
                    element.getAttribute('data-testid'),
                    element.innerText,
                    element.textContent
                ].filter(Boolean).join(' '));
                const attrs = norm([
                    element.getAttribute('data-pagelet'),
                    element.getAttribute('data-testid'),
                    element.id
                ].filter(Boolean).join(' '));
                const actions = Array.from(
                    element.querySelectorAll(actionSelector)
                ).filter(visible);
                const hasAccountHint = accountHints.some(hint => text.includes(hint));
                const hasSwitchHint = switchHints.some(hint => text.includes(hint));
                const hasTargetName = Boolean(pageName && text.includes(pageName));
                const hasTargetId = Boolean(pageId && text.includes(pageId));
                const profileTagged = profileAttributes.some(value => attrs.includes(value));
                const compact = rect.width >= 150 &&
                    rect.width < window.innerWidth * 0.92 &&
                    rect.height >= 50 &&
                    rect.height < window.innerHeight * 0.98;
                const floating = style.position === 'fixed' ||
                    style.position === 'absolute' ||
                    Number(style.zIndex || 0) > 0;
                const dialogOrList = element.matches(
                    '[role="dialog"], [role="listbox"], [data-pagelet*="ProfileSwitcher"], '
                    + '[data-testid*="profile_switcher"]'
                );
                let score = 0;
                if (profileTagged) score += 160;
                if (hasAccountHint) score += 90;
                if (hasSwitchHint) score += 80;
                if (hasTargetName) score += 100;
                if (hasTargetId) score += 120;
                if (dialogOrList) score += 15;
                if (compact) score += 20;
                if (floating) score += 20;
                if (actions.length >= 3) score += 10;
                if (rect.right > window.innerWidth * 0.45) score += 5;
                // Generic header/navigation menus must not be mistaken for the profile selector.
                if (!compact || actions.length < 2) score -= 100;
                if (!profileTagged && !hasAccountHint && !hasSwitchHint &&
                    !hasTargetName && !hasTargetId) score -= 150;
                return {element, score, area: rect.width * rect.height};
            })
            .filter(item => item.score > 0)
            .sort((left, right) =>
                right.score - left.score || left.area - right.area
            );
        if (candidates.length) return candidates[0].element;

        // Fallback for Facebook variants that do not mark the profile popup with ARIA roles.
        const actions = Array.from(document.querySelectorAll(actionSelector))
            .filter(visible);
        const hintMatches = element => {
            const values = [
                element.getAttribute('aria-label'),
                element.getAttribute('title'),
                element.innerText,
                element.textContent
            ].map(norm).filter(Boolean);
            return values.some(value =>
                accountHints.some(hint => value.includes(hint)) ||
                switchHints.some(hint => value.includes(hint)) ||
                (pageName && value.includes(pageName)) ||
                (pageId && value.includes(pageId))
            );
        };
        for (const action of actions) {
            if (!hintMatches(action)) continue;
            let parent = action;
            for (let depth = 0; parent && depth < 9; depth += 1) {
                if (visible(parent)) {
                    const rect = parent.getBoundingClientRect();
                    const style = window.getComputedStyle(parent);
                    const descendants = parent.querySelectorAll(actionSelector).length;
                    const compact = rect.width >= 150 &&
                        rect.width < window.innerWidth * 0.92 &&
                        rect.height >= 50 &&
                        rect.height < window.innerHeight * 0.98;
                    const floating = style.position === 'fixed' ||
                        style.position === 'absolute' ||
                        Number(style.zIndex || 0) > 0;
                    if (descendants >= 2 && compact && floating) return parent;
                }
                parent = parent.parentElement;
            }
        }
        return null;
        """,
        _POPUP_SELECTOR,
        page_name,
        page_id,
    )

def _wait_for_popup(
    driver,
    timeout: int = PROFILE_SWITCH_TIMEOUT,
    page_name: str = "",
    page_id: str = "",
):
    return WebDriverWait(driver, timeout, poll_frequency=0.3).until(
        lambda current: _visible_popup(current, page_name, page_id) or False
    )


def _visible_account_controls_summary(driver) -> str:
    try:
        return driver.execute_script(r"""
            const visible = element => {
                const style = window.getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0 &&
                    style.display !== 'none' && style.visibility !== 'hidden' &&
                    Number(style.opacity || 1) > 0;
            };
            const controls = Array.from(document.querySelectorAll(
                'button, [role="button"], [aria-label], [data-testid]'
            )).filter(visible).map(element => {
                const rect = element.getBoundingClientRect();
                return {
                    x: Math.round(rect.left + rect.width / 2),
                    y: Math.round(rect.top),
                    label: String(
                        element.getAttribute('aria-label') ||
                        element.getAttribute('title') ||
                        element.getAttribute('data-testid') ||
                        element.innerText || ''
                    ).replace(/\s+/g, ' ').trim().slice(0, 60),
                    expanded: element.getAttribute('aria-expanded') || ''
                };
            }).filter(item => item.x > window.innerWidth * 0.55 && item.y < 220)
              .sort((left, right) => right.x - left.x);
            return controls.slice(0, 12).map(item =>
                `${item.label || '(unlabelled)'}@${item.x},${item.y}` +
                `${item.expanded ? `[expanded=${item.expanded}]` : ''}`
            ).join('; ');
        """) or '(none detected)'
    except WebDriverException:
        return '(could not inspect controls)'


def _visible_menu_items_summary(driver, popup=None) -> str:
    try:
        return driver.execute_script(r"""
            const root = arguments[0] || document;
            const visible = element => {
                const style = window.getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0 &&
                    style.display !== 'none' && style.visibility !== 'hidden' &&
                    Number(style.opacity || 1) > 0;
            };
            const norm = value => String(value || '')
                .replace(/\s+/g, ' ').trim();
            const selector = 'button, [role="button"], [role="menuitem"], '
                + '[role="link"], a[href], [tabindex="0"]';
            const items = Array.from(root.querySelectorAll(selector))
                .filter(visible)
                .map(element => {
                    const rect = element.getBoundingClientRect();
                    const label = norm(
                        element.getAttribute('aria-label') ||
                        element.getAttribute('title') ||
                        element.innerText || element.textContent || ''
                    );
                    return {label, x: Math.round(rect.left + rect.width / 2),
                        y: Math.round(rect.top)};
                })
                .filter(item => item.label && item.label.length <= 90)
                .filter(item => item.x > window.innerWidth * 0.35)
                .filter((item, index, all) =>
                    all.findIndex(other => other.label === item.label) === index
                );
            return items.slice(0, 18).map(item =>
                `${item.label}@${item.x},${item.y}`
            ).join('; ') || '(no visible menu items detected)';
        """, popup)
    except WebDriverException:
        return '(could not inspect menu items)'


def _account_control_is_expanded(driver, candidate) -> bool:
    try:
        return bool(driver.execute_script(r"""
            const element = arguments[0];
            if (!element) return false;
            const controls = [element];
            const parentControl = element.closest(
                'button, [role="button"], [tabindex="0"]'
            );
            if (parentControl) controls.push(parentControl);
            controls.push(...element.querySelectorAll('[aria-expanded]'));
            return controls.some(control =>
                control.getAttribute('aria-expanded') === 'true'
            );
        """, candidate))
    except WebDriverException:
        return False


def _click_account_menu_candidate(driver, candidate):
    try:
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'nearest', inline: 'nearest'});",
            candidate,
        )
    except WebDriverException:
        pass

    for method in ("native", "action_chains", "javascript"):
        try:
            if method == "native":
                candidate.click()
            elif method == "action_chains":
                ActionChains(driver).move_to_element(candidate).pause(0.15).click().perform()
            else:
                driver.execute_script("arguments[0].click();", candidate)
        except WebDriverException:
            continue

        try:
            return _wait_for_popup(driver, timeout=2)
        except TimeoutException:
            if _account_control_is_expanded(driver, candidate):
                try:
                    return _wait_for_popup(driver, timeout=4)
                except TimeoutException as error:
                    raise FacebookSwitchError(
                        "The Facebook account control expanded, but its profile menu "
                        "could not be identified. Check the current Facebook layout.",
                        retryable=True,
                    ) from error

    return None


def _open_account_menu(driver):
    # Prefer Facebook's actual account/profile control, not Settings or a profile link.
    attempted = set()
    for _ in range(4):
        candidates = _find_account_menu_candidates(driver)
        candidate = next(
            (element for element in candidates if element.id not in attempted),
            None,
        )
        if candidate is None:
            break
        attempted.add(candidate.id)
        previous_url = str(getattr(driver, 'current_url', '') or '')

        popup = _click_account_menu_candidate(driver, candidate)
        current_url = str(getattr(driver, 'current_url', '') or '')
        if current_url != previous_url:
            # Preserve the requested target Page if a fallback control navigates away.
            try:
                open_page_link(driver, previous_url)
            except FacebookSwitchError:
                pass
            continue
        if popup is not None:
            return popup

    summary = _visible_account_controls_summary(driver)
    current_url = str(getattr(driver, 'current_url', '') or '')
    menu_items = _visible_menu_items_summary(driver)
    raise FacebookSwitchError(
        "Facebook's account/profile menu did not open. The code avoided the "
        "Settings, Messenger, Notifications, and normal profile-link controls. "
        f"URL: {current_url}; top-right controls: {summary}; "
        f"visible actions: {menu_items}",
        retryable=True,
    )


def _find_page_option(driver, page_name: str, popup, page_id: str = ""):
    if popup is None:
        return None

    return driver.execute_script(
        r"""
        const root = arguments[0];
        const target = String(arguments[1] || '')
            .normalize('NFC')
            .toLocaleLowerCase()
            .replace(/\s+/g, ' ')
            .trim();
        const targetId = String(arguments[2] || '').trim();
        const selector = arguments[3];
        const visible = element => {
            const style = window.getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            return rect.width > 0 &&
                rect.height > 0 &&
                style.display !== 'none' &&
                style.visibility !== 'hidden' &&
                Number(style.opacity || 1) > 0;
        };
        const norm = value => String(value || '')
            .normalize('NFC')
            .toLocaleLowerCase()
            .replace(/\s+/g, ' ')
            .trim();
        const candidates = Array.from(root.querySelectorAll(selector));
        for (let index = candidates.length - 1; index >= 0; index -= 1) {
            const element = candidates[index];
            if (
                !visible(element) ||
                element.getAttribute('aria-disabled') === 'true' ||
                element.disabled
            ) {
                continue;
            }
            const values = [
                element.getAttribute('aria-label'),
                element.getAttribute('title'),
                element.innerText,
                element.textContent,
                ...Array.from(element.querySelectorAll('img[alt]'))
                    .map(image => image.alt)
            ].map(norm).filter(Boolean);
            const attributes = [
                element.getAttribute('href'),
                element.getAttribute('id'),
                element.getAttribute('data-id'),
                element.getAttribute('data-page-id'),
                element.getAttribute('data-pageid'),
                element.getAttribute('data-testid')
            ].map(value => String(value || '')).join(' ');
            const nameMatched = target && values.some(value =>
                value === target ||
                value.startsWith(target + ' ') ||
                value === 'switch to ' + target ||
                value === 'chuyển sang ' + target
            );
            const idMatched = targetId && attributes.includes(targetId);
            if (nameMatched || idMatched) {
                return element;
            }
        }
        return null;
        """,
        popup,
        page_name,
        page_id,
        _ACTION_SELECTOR,
    )



def _find_switch_confirmation(driver, popup, page_name: str = ""):
    if popup is None:
        return None

    labels = set(CONFIRM_SWITCH_ACTIONS)
    target = str(page_name or "").strip()
    if target:
        labels.update({
            f"switch to {target}",
            f"switch to page {target}",
            f"switch profile to {target}",
            f"switch to profile {target}",
            f"chuyển sang {target}",
            f"chuyển sang trang {target}",
            f"chuyển sang trang cá nhân {target}",
            f"chuyển đổi sang {target}",
            f"tiếp tục với {target}",
        })
    return _dom_find_action(driver, labels, popup, exact=False)


def _target_page_is_selected(driver, page_name: str, page_id: str, popup) -> bool:
    if popup is None:
        return False

    try:
        return bool(driver.execute_script(
            r"""
            const root = arguments[0];
            const target = String(arguments[1] || '')
                .normalize('NFC').toLocaleLowerCase()
                .replace(/\s+/g, ' ').trim();
            const targetId = String(arguments[2] || '').trim();
            const selector = arguments[3];
            const norm = value => String(value || '')
                .normalize('NFC').toLocaleLowerCase()
                .replace(/\s+/g, ' ').trim();
            const visible = element => {
                const style = window.getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0 &&
                    style.display !== 'none' && style.visibility !== 'hidden' &&
                    Number(style.opacity || 1) > 0;
            };
            const candidates = Array.from(root.querySelectorAll(selector))
                .filter(visible);
            for (const element of candidates) {
                const values = [
                    element.getAttribute('aria-label'),
                    element.getAttribute('title'),
                    element.innerText,
                    element.textContent,
                    ...Array.from(element.querySelectorAll('img[alt]'))
                        .map(image => image.alt)
                ].map(norm).filter(Boolean);
                const attributes = [
                    element.getAttribute('href'),
                    element.getAttribute('id'),
                    element.getAttribute('data-id'),
                    element.getAttribute('data-page-id'),
                    element.getAttribute('data-pageid'),
                    element.getAttribute('data-testid')
                ].map(value => String(value || '')).join(' ');
                const matchesName = target && values.some(value =>
                    value === target || value.startsWith(target + ' ')
                );
                const matchesId = targetId && attributes.includes(targetId);
                if (!matchesName && !matchesId) continue;

                let probe = element;
                for (let depth = 0; probe && depth < 4; depth += 1) {
                    const selected =
                        probe.getAttribute('aria-selected') === 'true' ||
                        probe.getAttribute('aria-checked') === 'true' ||
                        probe.getAttribute('aria-current') === 'page' ||
                        probe.getAttribute('aria-pressed') === 'true' ||
                        probe.getAttribute('data-selected') === 'true' ||
                        probe.getAttribute('data-checked') === 'true' ||
                        probe.getAttribute('data-state') === 'selected';
                    if (selected) return true;
                    probe = probe.parentElement;
                    if (probe === root.parentElement) break;
                }
            }
            return false;
            """,
            popup,
            page_name,
            page_id,
            _ACTION_SELECTOR,
        ))
    except WebDriverException:
        return False


def _wait_for_switch_complete(
    driver,
    page_name: str = "",
    page_id: str = "",
    timeout: int = 15,
) -> None:
    try:
        WebDriverWait(driver, timeout, poll_frequency=0.3).until(
            lambda current: (
                True
                if _visible_popup(current, page_name, page_id) is None
                else _target_page_is_selected(
                    current,
                    page_name,
                    page_id,
                    _visible_popup(current, page_name, page_id),
                )
            )
        )
    except TimeoutException as error:
        popup = _visible_popup(driver, page_name, page_id)
        menu_items = _visible_menu_items_summary(driver, popup)
        raise FacebookSwitchError(
            "Facebook kept the profile selector open and the target Page was not "
            "marked as selected. "
            f"Target: {page_name or page_id}; URL: {driver.current_url}; "
            f"visible items: {menu_items}",
            retryable=True,
        ) from error



# ----- Facebook Page Management Switch Button -----
def _find_page_management_switch_button(driver):
    """Find the actual left-panel switch control, not a large ancestor container."""
    return driver.execute_script(r"""
        const norm = value => String(value || '')
            .normalize('NFC').toLocaleLowerCase()
            .replace(/\s+/g, ' ').trim();
        const visible = element => {
            const style = window.getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            return rect.width >= 45 && rect.height >= 16 && rect.height <= 100 &&
                rect.right > 0 && rect.left < Math.min(650, window.innerWidth * 0.70) &&
                rect.width < Math.min(520, window.innerWidth * 0.80) &&
                style.display !== 'none' && style.visibility !== 'hidden' &&
                Number(style.opacity || 1) > 0 && element.getClientRects().length > 0;
        };
        const wanted = new Set([
            'chuyển', 'switch', 'switch page', 'switch to page',
            'switch profile', 'switch to profile', 'switch identity',
            'switch to this page'
        ]);
        const candidates = [];
        const selector = '[aria-label], [title], button, [role="button"], a, [tabindex="0"]';
        for (const element of document.querySelectorAll(selector)) {
            if (!visible(element)) continue;
            const aria = norm(element.getAttribute('aria-label'));
            const title = norm(element.getAttribute('title'));
            const text = norm(element.innerText || element.textContent);
            const ariaExact = wanted.has(aria);
            const titleExact = wanted.has(title);
            const textExact = wanted.has(text) &&
                element.matches('button, [role="button"], a, [tabindex="0"]');
            if (!ariaExact && !titleExact && !textExact) continue;

            const rect = element.getBoundingClientRect();
            const style = window.getComputedStyle(element);
            let inPageManagementPanel = false;
            let ancestor = element;
            for (let depth = 0; ancestor && depth < 10; depth += 1) {
                const context = norm(ancestor.innerText || ancestor.textContent);
                if (context.length > 0 && context.length < 12000 &&
                    (context.includes('quản lý trang') ||
                     context.includes('manage page') ||
                     context.includes('page management'))) {
                    inPageManagementPanel = true;
                    break;
                }
                ancestor = ancestor.parentElement;
            }

            // Strongly prefer the exact aria-label seen on the real button in the UI.
            let score = 0;
            if (ariaExact) score += 1000;
            if (titleExact) score += 700;
            if (textExact) score += 500;
            if (inPageManagementPanel) score += 100;
            if (element.matches('button, [role="button"], a, [tabindex="0"]')) score += 80;
            if (style.cursor === 'pointer') score += 40;
            if (rect.width >= 100 && rect.height >= 24 && rect.height <= 60) score += 30;
            if (element.disabled || element.getAttribute('aria-disabled') === 'true' ||
                style.pointerEvents === 'none') score -= 500;
            // Avoid returning body/sidebar ancestors even if they contain the word.
            if (rect.width > Math.min(520, window.innerWidth * 0.80) || rect.height > 100) score -= 1000;
            candidates.push({element, score, top: rect.top});
        }
        candidates.sort((a, b) => b.score - a.score || b.top - a.top);
        return candidates.length && candidates[0].score > 0
            ? candidates[0].element
            : null;
    """)


def _describe_page_management_switch_button(driver, button=None) -> str:
    try:
        details = driver.execute_script(r"""
            const element = arguments[0];
            if (!element) return 'none';
            const rect = element.getBoundingClientRect();
            const norm = value => String(value || '')
                .normalize('NFC').toLocaleLowerCase()
                .replace(/\s+/g, ' ').trim();
            const style = window.getComputedStyle(element);
            return {
                tag: element.tagName.toLowerCase(),
                role: element.getAttribute('role') || '',
                aria: element.getAttribute('aria-label') || '',
                title: element.getAttribute('title') || '',
                text: norm(element.innerText || element.textContent).slice(0, 100),
                x: Math.round(rect.left), y: Math.round(rect.top),
                width: Math.round(rect.width), height: Math.round(rect.height),
                cursor: style.cursor,
                disabled: element.disabled || element.getAttribute('aria-disabled') === 'true'
            };
        """, button)
        if isinstance(details, dict):
            return (
                f"tag={details['tag']}; role={details['role'] or '-'}; "
                f"aria={details['aria'] or '-'}; title={details['title'] or '-'}; "
                f"text={details['text'] or '-'}; "
                f"rect=({details['x']},{details['y']},{details['width']},{details['height']}); "
                f"cursor={details['cursor']}; disabled={details['disabled']}"
            )
        return str(details)
    except WebDriverException:
        return 'unavailable'


def _page_management_switch_button_summary(driver) -> str:
    try:
        items = driver.execute_script(r"""
            const norm = value => String(value || '')
                .normalize('NFC').toLocaleLowerCase()
                .replace(/\s+/g, ' ').trim();
            const visible = element => {
                const style = window.getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return rect.width >= 45 && rect.height >= 16 && rect.height <= 100 &&
                    rect.right > 0 && rect.left < Math.min(650, window.innerWidth * 0.70) &&
                    rect.width < Math.min(520, window.innerWidth * 0.80) &&
                    style.display !== 'none' && style.visibility !== 'hidden' &&
                    Number(style.opacity || 1) > 0 && element.getClientRects().length > 0;
            };
            const wanted = new Set([
                'chuyển', 'switch', 'switch page', 'switch to page',
                'switch profile', 'switch to profile', 'switch identity',
                'switch to this page'
            ]);
            const results = [];
            const selector = '[aria-label], [title], button, [role="button"], a, [tabindex="0"]';
            for (const element of document.querySelectorAll(selector)) {
                if (!visible(element)) continue;
                const rect = element.getBoundingClientRect();
                const aria = norm(element.getAttribute('aria-label'));
                const title = norm(element.getAttribute('title'));
                const text = norm(element.innerText || element.textContent);
                if (!wanted.has(aria) && !wanted.has(title) &&
                    !(wanted.has(text) && element.matches('button, [role="button"], a, [tabindex="0"]'))) {
                    continue;
                }
                results.push(
                    `${element.tagName.toLowerCase()} aria=${aria || '-'} title=${title || '-'} ` +
                    `text=${text.slice(0, 50) || '-'}@${Math.round(rect.left)},${Math.round(rect.top)} ` +
                    `${Math.round(rect.width)}x${Math.round(rect.height)}`
                );
            }
            return results.slice(0, 8);
        """)
        return '; '.join(str(item) for item in items) or 'none'
    except WebDriverException:
        return 'unavailable'

def _target_page_has_follow_button(driver) -> bool:
    try:
        return bool(driver.execute_script(r"""
            const norm = value => String(value || '')
                .normalize('NFC').toLocaleLowerCase()
                .replace(/\s+/g, ' ').trim();
            const visible = element => {
                const style = window.getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0 &&
                    style.display !== 'none' && style.visibility !== 'hidden' &&
                    Number(style.opacity || 1) > 0;
            };
            const selector = 'button, [role="button"], a[role="button"], [tabindex="0"]';
            return Array.from(document.querySelectorAll(selector)).some(element => {
                if (!visible(element)) return false;
                const rect = element.getBoundingClientRect();
                if (rect.top < 90 || rect.top > window.innerHeight * 0.60 ||
                    rect.left < window.innerWidth * 0.15) return false;
                const labels = [
                    element.getAttribute('aria-label'),
                    element.getAttribute('title'),
                    element.innerText,
                    element.textContent
                ].map(norm).filter(Boolean);
                return labels.some(label => label === 'theo dõi' || label === 'follow');
            });
        """))
    except WebDriverException:
        return False


def _find_page_switch_dialog(driver, page_name: str = ""):
    try:
        return driver.execute_script(r"""
            const target = String(arguments[0] || '')
                .normalize('NFC').toLocaleLowerCase()
                .replace(/\s+/g, ' ').trim();
            const norm = value => String(value || '')
                .normalize('NFC').toLocaleLowerCase()
                .replace(/\s+/g, ' ').trim();
            const visible = element => {
                const style = window.getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0 &&
                    style.display !== 'none' && style.visibility !== 'hidden' &&
                    Number(style.opacity || 1) > 0;
            };
            const dialogs = Array.from(document.querySelectorAll(
                '[role="dialog"], [role="alertdialog"], [aria-modal="true"]'
            )).filter(visible);
            for (let index = dialogs.length - 1; index >= 0; index -= 1) {
                const dialog = dialogs[index];
                const text = norm(dialog.innerText || dialog.textContent);
                const hasSwitchLanguage = [
                    'chuyển', 'switch', 'switch profile', 'switch page',
                    'chuyển trang cá nhân', 'chuyển sang trang'
                ].some(value => text.includes(value));
                if (hasSwitchLanguage || (target && text.includes(target))) return dialog;
            }
            return null;
        """, page_name)
    except WebDriverException:
        return None


def _confirm_page_management_switch(driver, page_name: str = "") -> bool:
    dialog = _find_page_switch_dialog(driver, page_name)
    if dialog is None:
        return False

    labels = {
        'chuyển', 'switch', 'switch now', 'switch profile now',
        'switch page now', 'continue', 'confirm', 'tiếp tục',
        'xác nhận', 'chuyển ngay', 'chuyển đổi ngay',
        'chuyển sang ngay',
    }
    target = str(page_name or '').strip()
    if target:
        labels.update({
            f'switch to {target}',
            f'switch to page {target}',
            f'chuyển sang {target}',
            f'chuyển sang trang {target}',
            f'chuyển sang trang cá nhân {target}',
        })
    action = _dom_find_action(driver, labels, dialog, exact=True)
    if action is None:
        return False
    _click(action, driver)
    return True


def _page_switch_success_notice_visible(driver, page_name: str = "") -> bool:
    try:
        return bool(driver.execute_script(r"""
            const target = String(arguments[0] || '')
                .normalize('NFC').toLocaleLowerCase()
                .replace(/\s+/g, ' ').trim();
            const norm = value => String(value || '')
                .normalize('NFC').toLocaleLowerCase()
                .replace(/\s+/g, ' ').trim();
            const visible = element => {
                const style = window.getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0 &&
                    style.display !== 'none' && style.visibility !== 'hidden' &&
                    Number(style.opacity || 1) > 0;
            };
            const successPhrases = [
                'you are now interacting as', 'you’re now interacting as',
                'you switched to', 'now interacting as', 'now using facebook as',
                'bạn đang tương tác với tư cách', 'đã chuyển sang trang',
                'đã chuyển sang trang cá nhân', 'đã chuyển danh tính'
            ];
            const nodes = document.querySelectorAll(
                '[role="alert"], [role="status"], [aria-live], [data-testid*="toast"]'
            );
            return Array.from(nodes).some(element => {
                if (!visible(element)) return false;
                const text = norm(element.innerText || element.textContent);
                if (!text) return false;
                const hasSuccess = successPhrases.some(phrase => text.includes(phrase));
                return hasSuccess && (!target || text.includes(target));
            });
        """, page_name))
    except WebDriverException:
        return False


def _switch_via_page_management_button(driver, page_name: str, page_id: str) -> None:
    """Use the visible left-panel 'Chuyển' control instead of the avatar menu."""
    button = _find_page_management_switch_button(driver)
    if button is None:
        summary = _page_management_switch_button_summary(driver)
        raise FacebookSwitchError(
            "Could not find the 'Chuyển' button in Facebook's left Page Management panel. "
            "The target Page was opened first, but its Page Management switch control "
            "was not detected. Confirm that the panel is visible. "
            f"URL: {driver.current_url}; switch-like controls: {summary}",
            retryable=True,
        )

    try:
        disabled = button.get_attribute('aria-disabled') == 'true' or not button.is_enabled()
    except WebDriverException:
        disabled = False
    if disabled:
        raise FacebookSwitchError(
            "Facebook's left-panel 'Chuyển' button is visible but disabled. "
            "Check whether this AdsPower profile has permission to switch into the Page. "
            f"Target: {page_name or page_id}; URL: {driver.current_url}",
            retryable=False,
        )

    had_follow_button = _target_page_has_follow_button(driver)
    previous_url = str(driver.current_url or '').strip()
    clicked_control = _describe_page_management_switch_button(driver, button)

    def interaction_observed(browser) -> bool:
        try:
            if _find_page_switch_dialog(browser, page_name) is not None:
                return True
            if _page_switch_success_notice_visible(browser, page_name):
                return True
            if str(browser.current_url or '').strip() != previous_url:
                return True
            if had_follow_button and not _target_page_has_follow_button(browser):
                return True
            return False
        except WebDriverException:
            return False

    def wait_for_interaction(timeout: float = 1.5) -> bool:
        try:
            WebDriverWait(driver, timeout, poll_frequency=0.2).until(
                interaction_observed
            )
            return True
        except TimeoutException:
            return False

    # Try a normal WebDriver click first. If Facebook ignores it, retry with a
    # pointer action and then a DOM click, checking for a state change between tries.
    try:
        _click(button, driver)
    except WebDriverException:
        pass

    if not wait_for_interaction():
        button_again = _find_page_management_switch_button(driver)
        if button_again is not None:
            try:
                ActionChains(driver).move_to_element(button_again).pause(0.2).click().perform()
            except WebDriverException:
                pass

    if not interaction_observed(driver):
        if not wait_for_interaction(timeout=0.4):
            button_again = _find_page_management_switch_button(driver)
            if button_again is not None:
                try:
                    driver.execute_script("arguments[0].click();", button_again)
                except WebDriverException:
                    pass

    # Facebook may ask for confirmation after the first click. Detect the modal,
    # click the explicit confirmation action, and wait for the identity transition.
    try:
        WebDriverWait(driver, 3, poll_frequency=0.2).until(
            lambda browser: _find_page_switch_dialog(browser, page_name) is not None
        )
    except TimeoutException:
        pass
    _confirm_page_management_switch(driver, page_name)

    def switch_confirmed(browser) -> bool:
        try:
            ready_state = browser.execute_script('return document.readyState')
            if ready_state not in ('interactive', 'complete'):
                return False
            if _find_page_switch_dialog(browser, page_name) is not None:
                return False
            if _page_switch_success_notice_visible(browser, page_name):
                return True
            follow_button_visible = _target_page_has_follow_button(browser)
            if had_follow_button and not follow_button_visible:
                return True
            current_url = str(browser.current_url or '').strip()
            if current_url != previous_url and not follow_button_visible:
                return True
            # The Page Management switch control normally disappears after the
            # identity transition. Require the Follow control to be gone as well
            # when it was visible before, to avoid accepting a transient rerender.
            if _find_page_management_switch_button(browser) is None and not follow_button_visible:
                return True
            return False
        except WebDriverException:
            return False

    try:
        WebDriverWait(driver, 20, poll_frequency=0.3).until(switch_confirmed)
    except TimeoutException as error:
        summary = _page_management_switch_button_summary(driver)
        has_follow_button = _target_page_has_follow_button(driver)
        current_url = str(driver.current_url or '').strip()
        raise FacebookSwitchError(
            "Clicked Facebook's left-panel 'Chuyển' button, but the Page identity "
            "switch could not be confirmed. The browser may still be using the "
            "personal profile, the Page may require confirmation, or this profile "
            "may not have permission. "
            f"Target: {page_name or page_id}; URL: {current_url}; "
            f"Follow button still visible: {has_follow_button}; "
            f"Clicked control: {clicked_control}; "
            f"switch controls now visible: {summary}",
            retryable=True,
        ) from error

    _wait_for_page_ready(driver)
    _check_facebook_login(driver)


def _switch_profile_identity(driver, page_id: str, page_name: str) -> str:
    page_name = str(page_name or "").strip()
    page_id = _normalize_page_id(page_id)

    account_menu = _find_account_menu(driver)
    if account_menu is None:
        summary = _visible_account_controls_summary(driver)
        raise FacebookSwitchError(
            "Could not find Facebook's account menu in the DOM. "
            f"Top-right controls: {summary}. Check login status and Facebook page load.",
            retryable=True,
        )

    popup = _open_account_menu(driver)

    attempted_actions = set()
    for _ in range(3):
        page_option = _find_page_option(driver, page_name, popup, page_id)
        if page_option is not None:
            _click(page_option, driver)
            break

        action = None
        for action_name, labels in (
            ("see_all_profiles", SEE_ALL_PROFILES_ACTIONS),
            ("switch_profile", SWITCH_PROFILE_ACTIONS),
        ):
            if action_name in attempted_actions:
                continue
            action = _dom_find_action(driver, labels, popup, exact=False)
            if action is not None:
                attempted_actions.add(action_name)
                break

        if action is None:
            menu_items = _visible_menu_items_summary(driver, popup)
            raise FacebookSwitchError(
                f"Could not find the Page '{page_name or page_id}' in Facebook's profile menu. "
                "Check the PAGE sheet and confirm that this AdsPower profile has access. "
                f"Detected menu items: {menu_items}",
                retryable=False,
            )

        _click(action, driver)
        try:
            popup = _wait_for_popup(
                driver,
                page_name=page_name,
                page_id=page_id,
            )
        except TimeoutException as error:
            raise FacebookSwitchError(
                "Facebook did not open the profile list after the menu action.",
                retryable=True,
            ) from error
    else:
        raise FacebookSwitchError(
            f"Could not select the Facebook Page '{page_name or page_id}'.",
            retryable=False,
        )

    popup = _visible_popup(driver, page_name, page_id)
    confirm_button = _find_switch_confirmation(driver, popup, page_name)
    if confirm_button is not None:
        _click(confirm_button, driver)

    _wait_for_switch_complete(driver, page_name, page_id)
    _check_facebook_login(driver)
    return page_name or page_id


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




def _check_facebook_session(driver) -> None:
    _check_facebook_login(driver)


def _normalise(value: str) -> str:
    return " ".join((value or "").casefold().split())


def _caption_key(value: str) -> str:
    value = (value or "").casefold()
    value = re.sub(r"[^\w\s]", " ", value)
    return " ".join(value.split())

def switch_to_page(
    driver,
    page_link: str = "",
    page_id: str = "",
    page_name: str = "",
) -> str:
    """Open the target Page, then switch identity through Page Management."""
    url = _normalize_page_link(page_link)
    target_id, target_name = _derive_page_identity(url, page_id, page_name)

    if not target_id and not target_name:
        raise FacebookSwitchError(
            "Excel must provide page_name or page_id so Facebook can identify the Page.",
            retryable=False,
        )

    # Open the target Page first, then click the left-panel Page Management button.
    open_page_link(driver, url)
    _switch_via_page_management_button(driver, target_name, target_id)

    # Switching identity should keep the target Page in the current browser tab.
    current_url = str(driver.current_url or "").strip()
    if not current_url or current_url == "about:blank":
        raise FacebookSwitchError(
            "Facebook switched identity but did not keep a valid Page URL.",
            retryable=True,
        )
    return current_url


# ----- Facebook Posting Helpers (ported from the previous implementation) -----
def _visible_dialog(driver):
    return driver.execute_script(r"""
        const visible = element => {
            const style = window.getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            return rect.width > 0 &&
                rect.height > 0 &&
                style.display !== 'none' &&
                style.visibility !== 'hidden' &&
                Number(style.opacity || 1) > 0;
        };
        const norm = value => String(value || '')
            .normalize('NFC')
            .toLocaleLowerCase()
            .replace(/\s+/g, ' ')
            .trim();
        const selector = [
            '[role="dialog"]',
            '[aria-modal="true"]',
            '[data-pagelet*="Composer"]',
            '[data-testid*="composer" i]',
            '[aria-label*="create post" i]',
            '[aria-label*="tạo bài viết" i]'
        ].join(',');
        const actionSelector =
            "button, [role='button'], [role='menuitem'], [tabindex='0'], [aria-label]";
        const photoLabels = [
            'photo/video',
            'photo / video',
            'photos/videos',
            'add photos/videos',
            'add photo/video',
            'photos and videos',
            'photo and video',
            'ảnh/video',
            'ảnh và video'
        ];
        const isPhotoAction = element => {
            const values = [
                element.getAttribute('aria-label'),
                element.getAttribute('title'),
                element.innerText,
                element.textContent,
                element.getAttribute('data-testid')
            ].map(norm);
            return values.some(value =>
                photoLabels.some(label => value.includes(label))
            );
        };
        const candidates = Array.from(
            document.querySelectorAll(selector)
        ).filter(visible);
        let best = null;
        let bestScore = 0;
        for (const element of candidates) {
            const text = norm(element.innerText || element.textContent);
            const label = norm(element.getAttribute('aria-label'));
            const hasTextbox = Boolean(element.querySelector(
                "[contenteditable='true'][role='textbox'], " +
                "[contenteditable='true'], textarea"
            ));
            const hasPhotoAction = Array.from(
                element.querySelectorAll(actionSelector)
            ).some(action => visible(action) && isPhotoAction(action));
            let score = 0;
            if (element.matches('[role="dialog"], [aria-modal="true"]')) {
                score += 1;
            }
            if (hasTextbox) score += 2;
            if (hasPhotoAction) score += 4;
            if (
                /create post|create a post|what's on your mind|add to your post|tạo bài viết|bạn đang nghĩ gì|bạn viết gì/.test(text)
            ) {
                score += 2;
            }
            if (/create post|create a post|tạo bài viết/.test(label)) {
                score += 3;
            }
            if (score > bestScore) {
                best = element;
                bestScore = score;
            }
        }
        return bestScore >= 3 ? best : null;
        """)


def _wait_for_dialog(driver, timeout: int = 15):
    return WebDriverWait(driver, timeout).until(
        lambda current: _visible_dialog(current) or False
    )


def _find_composer_trigger(driver):
    return driver.execute_script(r"""
        const visible = element => {
            const style = window.getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            return rect.width > 0 &&
                rect.height > 0 &&
                style.display !== 'none' &&
                style.visibility !== 'hidden' &&
                Number(style.opacity || 1) > 0;
        };
        const norm = value => String(value || '')
            .normalize('NFC')
            .toLocaleLowerCase()
            .replace(/\s+/g, ' ')
            .trim();
        const selector = [
            '[data-pagelet*="ProfileCometComposer"]',
            '[data-pagelet*="Composer"]',
            '[data-testid*="composer" i]'
        ].join(',');
        const composerContainers = Array.from(
            document.querySelectorAll(selector)
        ).filter(visible);
        const composerHints = [
            'create post',
            'create a post',
            'write something',
            "what's on your mind",
            'tạo bài viết',
            'bạn đang nghĩ gì',
            'bạn viết gì đi'
        ];
        const actionSelector = "button, [role='button']";
        for (const container of composerContainers) {
            const candidates = [];
            if (container.matches(actionSelector)) {
                candidates.push(container);
            }
            candidates.push(...container.querySelectorAll(actionSelector));
            for (const element of candidates) {
                if (!visible(element)) continue;
                const value = norm([
                    element.getAttribute('aria-label'),
                    element.getAttribute('title'),
                    element.innerText,
                    element.textContent
                ].filter(Boolean).join(' '));
                if (composerHints.some(hint =>
                    value === hint || value.includes(hint)
                )) {
                    return element;
                }
            }
            const textbox = Array.from(
                container.querySelectorAll(
                    "[contenteditable='true'][role='textbox']"
                )
            ).find(visible);
            if (textbox) {
                return textbox;
            }
        }
        const main = document.querySelector('[role="main"]') || document.body;
        const candidates = Array.from(
            main.querySelectorAll(actionSelector)
        ).filter(visible);
        for (const element of candidates) {
            const value = norm([
                element.getAttribute('aria-label'),
                element.getAttribute('title'),
                element.innerText,
                element.textContent
            ].filter(Boolean).join(' '));
            if (composerHints.some(hint =>
                value === hint || value.includes(hint)
            )) {
                return element;
            }
        }
        return null;
        """)


# ----- Media Upload and Caption Editor -----
def _find_file_input(driver, dialog, timeout: int = 15):
    def locate(current):
        roots = [dialog, _visible_dialog(current), current]

        for root in roots:
            if root is None:
                continue

            try:
                inputs = root.find_elements(
                    By.CSS_SELECTOR,
                    "input[type='file']",
                )
            except StaleElementReferenceException:
                continue

            if inputs:
                return inputs[-1]

        return False

    return WebDriverWait(driver, timeout).until(locate)


def _find_caption_box(dialog):
    candidates = dialog.find_elements(
        By.CSS_SELECTOR,
        "[contenteditable='true'][role='textbox'], "
        "div[contenteditable='true'], textarea",
    )

    candidates = [item for item in candidates if _visible(item)]

    if not candidates:
        return None

    preferred = (
        "what's on your mind",
        "bạn đang nghĩ gì",
        "write something",
        "bạn viết gì",
    )

    for item in candidates:
        label = _normalise(
            item.get_attribute("aria-label") or item.get_attribute("placeholder")
        )

        if any(value in label for value in preferred):
            return item

    return candidates[0]


def input_caption(driver, caption_box, caption: str) -> None:
    caption = str(caption or "")

    if not caption.strip():
        raise ValueError("Caption is required.")

    try:
        # Save the existing clipboard content.
        previous_clipboard = None

        try:
            previous_clipboard = pyperclip.paste()
        except Exception:
            pass

        # Focus the Facebook caption editor.
        caption_box.click()
        time.sleep(0.2)

        # Copy Unicode text, including emoji.
        pyperclip.copy(caption)
        time.sleep(0.2)

        # Paste into Facebook.
        caption_box.send_keys(Keys.CONTROL, "v")
        time.sleep(0.5)

        # Restore the clipboard only after the paste
        # has had time to reach the editor.
        if previous_clipboard is not None:
            try:
                pyperclip.copy(previous_clipboard)
            except Exception:
                pass

    except WebDriverException as error:
        raise RuntimeError(f"Failed to input Facebook caption: {error}") from error


def paste_text(element, text: str) -> None:
    text = str(text or "")

    if not text:
        return

    pyperclip.copy(text)

    element.click()
    element.send_keys(Keys.CONTROL, "v")


# ----- Published Post Detection -----
def _find_post_article(driver, caption: str, timeout: int = 15):
    snippet = " ".join(_caption_key(caption).split()[:12])
    if not snippet:
        return None

    def locate(current):
        result = current.execute_script(
            r"""
            const needle = arguments[0];
            const norm = s => String(s || '').normalize('NFKC').toLowerCase()
                .replace(/[^\p{L}\p{N}\s]/gu, ' ').replace(/\s+/g, ' ').trim();
            const main = document.querySelector('[role="main"]') || document.body;
            const matches = [...main.querySelectorAll('span,p,div')]
                .filter(el => {
                    const t = el.innerText || '';
                    return t.length >= needle.length && t.length < 1500 && norm(t).includes(needle);
                })
                .sort((a,b) => (a.innerText||'').length - (b.innerText||'').length);
            const leaves = matches.filter(el => !matches.some(other => other !== el && el.contains(other)));
            const cards = [];
            for (const leaf of leaves) {
                let node = leaf;
                let chosen = null;
                for (let depth=0; node && node!==main && depth<18; depth++, node=node.parentElement) {
                    const len=(node.innerText||'').length;
                    if (len>6000) break;
                    if (node.matches('[role="article"], [data-pagelet*="FeedUnit"], [data-pagelet*="TimelineFeedUnit"]')) {
                        chosen=node; break;
                    }
                    // Fallback: compact container with a post header and interaction controls.
                    const hasPageHeader = !!node.querySelector('a[href*="profile.php"], a[href*="/reel/"], a[href*="/posts/"]');
                    const hasActions = [...node.querySelectorAll('[role="button"],button')]
                        .some(x => /^(like|comment|share|thích|bình luận|chia sẻ)$/i.test((x.getAttribute('aria-label')||x.innerText||'').trim()));
                    if (len >= (leaf.innerText||'').length && len < 4500 && hasPageHeader && hasActions) {
                        chosen=node; break;
                    }
                }
                if (chosen && !cards.includes(chosen)) cards.push(chosen);
            }
            const unique=cards.filter(n => !cards.some(other => other!==n && other.contains(n)));
            return {element:unique.length===1 ? unique[0] : null,
                captionMatches:matches.length, leafMatches:leaves.length, cardCount:unique.length,
                reason: !matches.length ? 'caption not in DOM' :
                    !unique.length ? 'caption present but no bounded post card' :
                    unique.length>1 ? 'ambiguous matching post cards' : 'ok'};
        """,
            snippet,
        )
        if result.get("element") is not None:
            return result["element"]
        return False

    try:
        return WebDriverWait(driver, timeout, poll_frequency=0.5).until(locate)
    except TimeoutException:
        return None


# ----- Post and Next Button Detection -----
def _inspect_post_button(driver):
    return driver.execute_script(
        r"""
        const labels = new Set([
            ...arguments[0].map(value =>
                String(value || '').normalize('NFC')
                    .toLocaleLowerCase().replace(/\s+/g, ' ').trim()
            ),
            'post now',
            'publish now',
            'share now',
            'publish post',
            'share post',
            'đăng bài',
            'đăng bài viết',
            'đăng ngay',
            'chia sẻ bài viết'
        ]);
        const saveLabels = new Set(['save', 'lưu']);
        const controlSelector =
            "button, [role='button'], [role='menuitem'], [tabindex='0']";
        const rootSelector = [
            '[role="dialog"]',
            '[aria-modal="true"]',
            '[data-pagelet*="Composer"]',
            '[data-testid*="composer" i]',
            '[data-pagelet*="Video"]',
            '[data-testid*="video" i]'
        ].join(',');
        const norm = value => String(value || '')
            .normalize('NFC')
            .toLocaleLowerCase()
            .replace(/\s+/g, ' ')
            .trim();
        const visible = element => {
            const style = window.getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            return rect.width > 0 &&
                rect.height > 0 &&
                style.display !== 'none' &&
                style.visibility !== 'hidden' &&
                Number(style.opacity || 1) > 0;
        };
        const valuesOf = element => [
            element.getAttribute('aria-label'),
            element.getAttribute('title'),
            element.innerText,
            element.textContent
        ].map(norm).filter(Boolean);
        const isPostButton = element => {
            const values = valuesOf(element);
            if (
                values.some(value =>
                    Array.from(labels).some(label =>
                        value === label || value.startsWith(label + ' ')
                    )
                )
            ) {
                return true;
            }
            const testId = norm(element.getAttribute('data-testid'));
            return /(?:post|publish|share).*(?:button|submit)|(?:button|submit).*(?:post|publish|share)/i.test(testId);
        };
        const isSaveButton = element => {
            return visible(element) &&
                valuesOf(element).some(value => saveLabels.has(value));
        };
        const isDisabled = element => {
            return element.disabled ||
                element.getAttribute('aria-disabled') === 'true';
        };
        const allControls = Array.from(
            document.querySelectorAll(controlSelector)
        ).filter(visible);
        const editorRoots = Array.from(
            document.querySelectorAll(rootSelector)
        ).filter(visible);
        const scopedControls = allControls.filter(element =>
            editorRoots.some(root => root === element || root.contains(element))
        );
        // Nếu đã xác định được vùng composer, không tìm nút Đăng ngoài vùng đó.
        const candidates = editorRoots.length
            ? scopedControls.filter(isPostButton)
            : allControls.filter(isPostButton);
        if (!candidates.length) {
            return {status: 'not_found', element: null};
        }
        const enabledCandidates = candidates.filter(
            element => !isDisabled(element)
        );
        if (!enabledCandidates.length) {
            return {status: 'disabled', element: null};
        }
        const scoreButton = element => {
            let score = element.tagName === 'BUTTON' ? 2 : 0;
            let node = element;
            for (let depth = 0; node && depth < 12; depth += 1) {
                const isRoot = node.matches &&
                    node.matches(rootSelector);
                const hasTextbox = Boolean(node.querySelector(
                    "[contenteditable='true'][role='textbox'], " +
                    "[contenteditable='true'], textarea"
                ));
                const hasSaveButton = Array.from(
                    node.querySelectorAll(controlSelector)
                ).some(isSaveButton);
                const text = norm(
                    (node.innerText || node.textContent || '').slice(0, 3000)
                );
                const hasVideoEditor =
                    /edit video|video editor|trim video|chỉnh sửa video|cắt video/.test(text);
                if (isRoot) score += 8;
                if (hasTextbox) score += 2;
                if (hasSaveButton) score += 4;
                if (hasVideoEditor) score += 1;
                if (isRoot || (hasSaveButton && hasTextbox)) {
                    break;
                }
                node = node.parentElement;
            }
            return score;
        };
        const ranked = enabledCandidates
            .map(element => ({
                element,
                score: scoreButton(element)
            }))
            .sort((a, b) => b.score - a.score);
        if (
            ranked.length > 1 &&
            ranked[0].score === ranked[1].score &&
            ranked[0].score < 4
        ) {
            return {status: 'ambiguous', element: null};
        }
        return {
            status: 'found',
            element: ranked[0].element
        };
        """,
        sorted(POST_ACTIONS),
    )


def _inspect_next_button(driver):
    return driver.execute_script(
        r"""
        const labels = new Set(arguments[0].map(value =>
            String(value || '')
                .normalize('NFC')
                .toLocaleLowerCase()
                .replace(/\s+/g, ' ')
                .trim()
        ));
        const controlSelector =
            "button, [role='button'], [role='menuitem'], [tabindex='0']";
        const rootSelector = [
            '[role="dialog"]',
            '[aria-modal="true"]',
            '[data-pagelet*="Composer"]',
            '[data-testid*="composer" i]',
            '[data-pagelet*="Video"]',
            '[data-testid*="video" i]'
        ].join(',');
        const norm = value => String(value || '')
            .normalize('NFC')
            .toLocaleLowerCase()
            .replace(/\s+/g, ' ')
            .trim();
        const visible = element => {
            const style = window.getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            return rect.width > 0 &&
                rect.height > 0 &&
                style.display !== 'none' &&
                style.visibility !== 'hidden' &&
                Number(style.opacity || 1) > 0;
        };
        const isDisabled = element =>
            element.disabled ||
            element.getAttribute('aria-disabled') === 'true';
        const valuesOf = element => [
            element.getAttribute('aria-label'),
            element.getAttribute('title'),
            element.innerText,
            element.textContent
        ].map(norm).filter(Boolean);
        const isNextButton = element => {
            const values = valuesOf(element);
            if (values.some(value =>
                Array.from(labels).some(label =>
                    value === label || value.startsWith(label + ' ')
                )
            )) {
                return true;
            }
            const testId = norm(element.getAttribute('data-testid'));
            return /(?:next|continue).*(?:button|submit)|(?:button|submit).*(?:next|continue)/i.test(testId);
        };
        const allControls = Array.from(
            document.querySelectorAll(controlSelector)
        ).filter(visible);
        const roots = Array.from(
            document.querySelectorAll(rootSelector)
        ).filter(visible);
        const scopedControls = allControls.filter(element =>
            roots.some(root => root === element || root.contains(element))
        );
        // Không lấy nhầm nút Tiếp từ vùng khác của Facebook.
        const candidates = roots.length
            ? scopedControls.filter(isNextButton)
            : allControls.filter(isNextButton);
        if (!candidates.length) {
            return {status: 'not_found', element: null};
        }
        const enabledCandidates = candidates.filter(
            element => !isDisabled(element)
        );
        if (!enabledCandidates.length) {
            return {status: 'disabled', element: null};
        }
        const scoreButton = element => {
            let score = element.tagName === 'BUTTON' ? 2 : 0;
            let node = element;
            for (let depth = 0; node && depth < 12; depth += 1) {
                const isRoot = node.matches &&
                    node.matches(rootSelector);
                const hasTextbox = Boolean(node.querySelector(
                    "[contenteditable='true'][role='textbox'], " +
                    "[contenteditable='true'], textarea"
                ));
                if (isRoot) score += 8;
                if (hasTextbox) score += 2;
                if (isRoot) break;
                node = node.parentElement;
            }
            return score;
        };
        const ranked = enabledCandidates
            .map(element => ({
                element,
                score: scoreButton(element)
            }))
            .sort((a, b) => b.score - a.score);
        return {
            status: 'found',
            element: ranked[0].element
        };
        """,
        sorted(NEXT_ACTIONS),
    )


# ----- Call Now Popup Handling -----
def _find_call_now_popup_root(driver):
    return driver.execute_script(r"""
        const norm = value => String(value || '')
            .normalize('NFKC')
            .toLocaleLowerCase()
            .replace(/[“”"]/g, '')
            .replace(/\s+/g, ' ')
            .trim();

        const visible = element => {
            const rect = element.getBoundingClientRect();

            if (rect.width <= 0 || rect.height <= 0) {
                return false;
            }

            for (let node = element; node; node = node.parentElement) {
                const style = window.getComputedStyle(node);

                if (
                    style.display === 'none' ||
                    style.visibility === 'hidden' ||
                    Number(style.opacity || 1) <= 0.01 ||
                    node.getAttribute('aria-hidden') === 'true'
                ) {
                    return false;
                }
            }

            return true;
        };

        const title = 'speak with people directly';
        const closeLabels = new Set([
            'close',
            'close dialog',
            'close popup',
            'dismiss',
            'đóng',
            'đóng hộp thoại'
        ]);

        const hasCloseButton = root => {
            const controls = root.querySelectorAll(
                'button, [role="button"], [aria-label], [title], [tabindex="0"]'
            );

            return Array.from(controls).some(element => {
                const labels = [
                    element.getAttribute('aria-label'),
                    element.getAttribute('title')
                ].map(norm);

                return labels.some(label => closeLabels.has(label));
            });
        };

        const matchesPopup = element => {
            if (!visible(element)) {
                return false;
            }

            const text = norm(element.innerText || element.textContent);

            return text.includes(title) &&
                text.length <= 1800 &&
                (
                    text.includes('not now') ||
                    text.includes('add button') ||
                    text.includes('call now')
                );
        };

        const candidates = Array.from(document.querySelectorAll(
            '[role="dialog"], [aria-modal="true"], div'
        )).filter(matchesPopup);

        candidates.sort((a, b) => {
            const closeDifference =
                Number(hasCloseButton(b)) - Number(hasCloseButton(a));

            if (closeDifference !== 0) {
                return closeDifference;
            }

            const aLength = norm(a.innerText || a.textContent).length;
            const bLength = norm(b.innerText || b.textContent).length;

            return aLength - bLength;
        });

        return candidates[0] || null;
    """)


def _call_now_popup_visible(driver) -> bool:
    return _find_call_now_popup_root(driver) is not None


def _find_call_now_close_button(driver):
    popup = _find_call_now_popup_root(driver)

    if popup is None:
        return None

    return driver.execute_script(
        r"""
        const root = arguments[0];

        const norm = value => String(value || '')
            .normalize('NFKC')
            .toLocaleLowerCase()
            .replace(/[“”"]/g, '')
            .replace(/\s+/g, ' ')
            .trim();

        const visible = element => {
            const rect = element.getBoundingClientRect();

            if (rect.width <= 0 || rect.height <= 0) {
                return false;
            }

            for (let node = element; node; node = node.parentElement) {
                const style = window.getComputedStyle(node);

                if (
                    style.display === 'none' ||
                    style.visibility === 'hidden' ||
                    Number(style.opacity || 1) <= 0.01 ||
                    node.getAttribute('aria-hidden') === 'true'
                ) {
                    return false;
                }
            }

            return true;
        };

        const closeLabels = new Set([
            'not now',
            'close',
            'close dialog',
            'close popup',
            'dismiss',
            'đóng',
            'đóng hộp thoại'
        ]);

        const controls = Array.from(root.querySelectorAll(
            'button, [role="button"], [aria-label], [title], [tabindex="0"]'
        )).filter(visible);

        for (const element of controls) {
            const labels = [
                element.getAttribute('aria-label'),
                element.getAttribute('title')
            ].map(norm);

            if (labels.some(label => closeLabels.has(label))) {
                return element;
            }
        }

        return null;
    """,
        popup,
    )


def _dismiss_call_now_popup(
    driver,
    timeout: int = 5,
    appearance_timeout: float = 0,
) -> bool:
    if appearance_timeout > 0:
        try:
            WebDriverWait(
                driver,
                appearance_timeout,
                poll_frequency=0.2,
            ).until(lambda current: _find_call_now_popup_root(current) or False)
        except TimeoutException:
            return False

    elif not _call_now_popup_visible(driver):
        return False

    try:
        close_button = WebDriverWait(
            driver,
            timeout,
            poll_frequency=0.2,
        ).until(lambda current: _find_call_now_close_button(current) or False)
    except TimeoutException as error:
        raise FacebookPostError(
            "Facebook's Call Now popup is visible, but its X button "
            "could not be located."
        ) from error

    try:
        _click_once(close_button, driver)

    except Exception as click_error:
        if not _call_now_popup_visible(driver):
            return True

        close_button = _find_call_now_close_button(driver)

        if close_button is None:
            raise FacebookPostError(
                "Could not locate the popup's X button after the initial click failed."
            ) from click_error

        try:
            driver.execute_script("arguments[0].click();", close_button)
        except Exception as error:
            raise FacebookPostError(
                "Could not click the X button on Facebook's Call Now popup."
            ) from error

    try:
        WebDriverWait(
            driver,
            timeout,
            poll_frequency=0.2,
        ).until(lambda current: not _call_now_popup_visible(current))
    except TimeoutException as error:
        raise FacebookPostError(
            "Facebook's Call Now popup remained visible after clicking X."
        ) from error

    return True


# ----- Workflow State and Composer Status -----
def _workflow_snapshot(driver) -> str:
    return driver.execute_script(r"""
        const visible = element => {
            const style = window.getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            return rect.width > 0 &&
                rect.height > 0 &&
                style.display !== 'none' &&
                style.visibility !== 'hidden' &&
                Number(style.opacity || 1) > 0;
        };
        const rootSelector = [
            '[role="dialog"]',
            '[aria-modal="true"]',
            '[data-pagelet*="Composer"]',
            '[data-testid*="composer" i]',
            '[data-pagelet*="Video"]',
            '[data-testid*="video" i]'
        ].join(',');
        const controlSelector =
            "button, [role='button'], [role='menuitem'], [tabindex='0']";
        const roots = Array.from(
            document.querySelectorAll(rootSelector)
        ).filter(visible);
        const targets = roots.length ? roots : [document.body];
        const snapshots = targets.map(root => {
            const text = String(
                root.innerText || root.textContent || ''
            ).replace(/\s+/g, ' ').trim();
            const controls = Array.from(
                root.querySelectorAll(controlSelector)
            )
                .filter(visible)
                .map(element => [
                    element.tagName,
                    element.getAttribute('aria-label') || '',
                    element.getAttribute('title') || '',
                    element.getAttribute('data-testid') || '',
                    String(element.innerText || element.textContent || '')
                        .replace(/\s+/g, ' ').trim(),
                    element.disabled ? 'disabled' : 'enabled',
                    element.getAttribute('aria-disabled') || ''
                ].join('\~'));
            return {
                label: root.getAttribute('aria-label') || '',
                testId: root.getAttribute('data-testid') || '',
                text,
                controls
            };
        });
        return JSON.stringify(snapshots).slice(0, 15000);
        """) or ""


def _composer_status(driver) -> str:
    try:
        return driver.execute_script(r"""
            const visible = element => {
                const style = window.getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return rect.width > 0 &&
                    rect.height > 0 &&
                    style.display !== 'none' &&
                    style.visibility !== 'hidden' &&
                    Number(style.opacity || 1) > 0;
            };
            const norm = value => String(value || '')
                .replace(/\s+/g, ' ')
                .trim();
            const alertSelector = [
                '[role="alert"]',
                '[aria-live="assertive"]',
                '[data-testid*="error" i]',
                '[data-testid*="upload" i]'
            ].join(',');
            const alerts = Array.from(
                document.querySelectorAll(alertSelector)
            )
                .filter(visible)
                .map(element => norm(
                    element.innerText || element.textContent
                ))
                .filter(Boolean);
            const dialogSelector = [
                '[role="dialog"]',
                '[aria-modal="true"]',
                '[data-pagelet*="Composer"]',
                '[data-testid*="composer" i]',
                '[data-pagelet*="Video"]',
                '[data-testid*="video" i]'
            ].join(',');
            const dialogTexts = Array.from(
                document.querySelectorAll(dialogSelector)
            )
                .filter(visible)
                .map(element => norm(
                    element.innerText || element.textContent
                ))
                .filter(Boolean);
            return [...new Set([...alerts, ...dialogTexts])]
                .join(' | ')
                .replace(/\s+/g, ' ')
                .slice(-900);
            """) or ""
    except Exception:
        return ""


# ----- Workflow Action Detection -----
def _wait_for_workflow_action(driver, timeout: int = POST_BUTTON_TIMEOUT):
    last_state = {
        "next": "not_found",
        "post": "not_found",
    }

    def locate(current):
        try:
            _dismiss_call_now_popup(current)

            next_result = _inspect_next_button(current)
            last_state["next"] = next_result.get("status", "not_found")

            if last_state["next"] == "found":
                button = next_result.get("element")

                if button is not None and _visible(button) and button.is_enabled():
                    return "next", button

            if last_state["next"] == "disabled":
                return False

            post_result = _inspect_post_button(current)
            last_state["post"] = post_result.get("status", "not_found")

            if last_state["post"] == "found":
                button = post_result.get("element")

                if button is not None and _visible(button) and button.is_enabled():
                    return "post", button

            return False

        except StaleElementReferenceException:
            return False

    try:
        return WebDriverWait(
            driver,
            timeout,
            poll_frequency=0.5,
        ).until(locate)

    except TimeoutException as error:
        status_text = _composer_status(driver)

        if last_state["next"] == "disabled":
            reason = "Facebook's Next button remained disabled."
        elif last_state["post"] == "disabled":
            reason = "Facebook's Post button remained disabled."
        elif last_state["post"] == "ambiguous":
            reason = "Multiple Post buttons were found."
        else:
            reason = (
                "Neither an enabled Next button nor an enabled Post button appeared."
            )

        detail = f" Facebook composer status: {status_text}" if status_text else ""

        raise FacebookPostError(
            f"Facebook did not expose the next workflow action within "
            f"{timeout} seconds. {reason}{detail}"
        ) from error


def _wait_for_step_transition(
    driver,
    previous_button,
    previous_snapshot: str,
    timeout: int = 20,
) -> None:
    def transitioned(current):
        _dismiss_call_now_popup(current)

        try:
            if not previous_button.is_displayed():
                return True
        except StaleElementReferenceException:
            return True

        current_snapshot = _workflow_snapshot(current)

        if current_snapshot != previous_snapshot:
            return True

        next_result = _inspect_next_button(current)

        if next_result.get("status") == "found":
            next_button = next_result.get("element")

            if next_button is not None and next_button != previous_button:
                return True

        post_result = _inspect_post_button(current)

        if post_result.get("status") in {"found", "disabled", "ambiguous"}:
            return True

        return False

    try:
        WebDriverWait(
            driver,
            timeout,
            poll_frequency=0.5,
        ).until(transitioned)

    except TimeoutException as error:
        raise FacebookPostError(
            "Facebook did not confirm the transition after clicking Next. "
            "The workflow has been stopped to avoid clicking the same step repeatedly."
        ) from error


# ----- Facebook Feed Scrolling -----
def _scroll_to_render_posts(driver, pixels=600, wait=1.5):
    try:
        scroll_area = driver.execute_script("""
            const main = document.querySelector('[role="main"]');
            const feed = document.querySelector('[role="feed"]');

            return feed || main || document.body;
        """)

        before = driver.execute_script("""
            return {
                windowY: window.scrollY,
                documentY: document.scrollingElement.scrollTop
            };
        """)

        try:
            ActionChains(driver).move_to_element(scroll_area).scroll_by_amount(
                0, pixels
            ).perform()

        except Exception:
            pass

        time.sleep(0.5)

        driver.execute_script(
            """
            const main = document.querySelector('[role="main"]');
            let node = main;

            while (node) {
                const style = getComputedStyle(node);

                if (
                    node.scrollHeight > node.clientHeight &&
                    ['auto', 'scroll'].includes(style.overflowY)
                ) {
                    node.scrollTop += arguments[0];
                    return;
                }

                node = node.parentElement;
            }

            window.scrollBy(0, arguments[0]);
        """,
            pixels,
        )

        time.sleep(wait)

        after = driver.execute_script("""
            return {
                windowY: window.scrollY,
                documentY: document.scrollingElement.scrollTop
            };
        """)

        return True

    except Exception:
        return False


# ----- Post Button and Publish Confirmation -----
def _wait_for_post_button(driver, timeout: int = POST_BUTTON_TIMEOUT):
    last_state = {"status": "not_found"}

    def locate(current):
        try:
            _dismiss_call_now_popup(current)

            result = _inspect_post_button(current)
            status = result.get("status", "not_found")
            last_state["status"] = status

            if status != "found":
                return False

            button = result.get("element")

            if button is None:
                last_state["status"] = "not_found"
                return False

            if _visible(button) and button.is_enabled():
                return button

            last_state["status"] = "disabled"
            return False

        except StaleElementReferenceException:
            return False

    try:
        return WebDriverWait(
            driver,
            timeout,
            poll_frequency=0.5,
        ).until(locate)

    except TimeoutException as error:
        status_text = _composer_status(driver)
        button_state = last_state["status"]

        if button_state == "disabled":
            reason = "A Post button was found, but it remained disabled."
        elif button_state == "ambiguous":
            reason = (
                "Multiple Post buttons were found, and the active composer "
                "could not be identified safely."
            )
        else:
            reason = "No enabled Post button appeared."

        detail = f" Facebook composer status: {status_text}" if status_text else ""

        raise FacebookPostError(
            f"Facebook did not expose an enabled Post button within "
            f"{timeout} seconds. {reason} "
            "The media upload may still be processing or may have failed. "
            "Check the composer for an upload error before retrying."
            f"{detail}"
        ) from error


def _find_publish_success_notice(driver) -> str:
    return driver.execute_script(r"""
        const selectors = [
            '[role="alert"]',
            '[role="status"]',
            '[aria-live="polite"]',
            '[aria-live="assertive"]',
            '[data-testid*="toast" i]',
            '[data-testid*="notification" i]'
        ].join(',');

        const norm = value => String(value || '')
            .normalize('NFKC')
            .toLocaleLowerCase()
            .replace(/\s+/g, ' ')
            .trim();

        const visible = element => {
            const rect = element.getBoundingClientRect();

            if (rect.width <= 0 || rect.height <= 0) {
                return false;
            }

            for (let node = element; node; node = node.parentElement) {
                const style = window.getComputedStyle(node);

                if (
                    style.display === 'none' ||
                    style.visibility === 'hidden' ||
                    Number(style.opacity || 1) <= 0.01 ||
                    node.getAttribute('aria-hidden') === 'true'
                ) {
                    return false;
                }
            }

            return true;
        };

        const successPhrases = [
            'your post has been published',
            'your post was published',
            'your post has been shared',
            'your post is published',
            'your reel has been published',
            'your reel has been shared',
            'your reel is ready',
            'your video has been published',
            'post has been published',
            'post has been shared',
            'reel has been published',
            'reel has been shared',
            'published successfully',
            'bài viết của bạn đã được đăng',
            'bài viết của bạn đã được chia sẻ',
            'bài viết đã được đăng',
            'bài viết đã được chia sẻ',
            'reel của bạn đã được đăng',
            'reel của bạn đã được chia sẻ',
            'video của bạn đã được đăng',
            'đã đăng bài viết',
            'đã chia sẻ bài viết',
            'đã đăng reel',
            'đã chia sẻ reel'
        ];

        const pendingPhrases = [
            'being published',
            'is publishing',
            'publishing',
            'processing',
            'uploading',
            'đang đăng',
            'đang xử lý',
            'đang tải lên'
        ];

        const elements = Array.from(
            document.querySelectorAll(selectors)
        ).filter(visible);

        for (const element of elements) {
            const text = norm(element.innerText || element.textContent);

            if (!text || text.length > 600) {
                continue;
            }

            if (pendingPhrases.some(phrase => text.includes(phrase))) {
                continue;
            }

            if (successPhrases.some(phrase => text.includes(phrase))) {
                return text.slice(0, 300);
            }
        }

        return '';
    """) or ""


def _wait_for_publish_confirmation(driver, timeout: int = 90) -> str:
    state = {"composer_closed_at": None}

    def check(current):
        try:
            if _call_now_popup_visible(current):
                try:
                    _dismiss_call_now_popup(current, timeout=2)
                except Exception:
                    pass
        except Exception:
            pass

        notice = _find_publish_success_notice(current)

        if notice:
            return f"notification: {notice}"

        if _visible_dialog(current) is None:
            if state["composer_closed_at"] is None:
                state["composer_closed_at"] = time.monotonic()
            elif time.monotonic() - state["composer_closed_at"] >= 3:
                return "composer_closed"
        else:
            state["composer_closed_at"] = None

        return False

    try:
        return WebDriverWait(
            driver,
            timeout,
            poll_frequency=0.5,
        ).until(check)

    except TimeoutException as error:
        raise PublishUnknownError(
            "Facebook did not show a publish confirmation or close the "
            "post composer within the allowed time. Check the Page before "
            "retrying to avoid publishing a duplicate."
        ) from error

def publish_photo(driver, row: dict, before_submit=None) -> None:
    page_link = str(row.get("page_link") or "").strip()
    caption = str(row.get("caption") or "").strip()
    media_path = str(
        row.get("_validated_image") or row.get("media") or row.get("image") or ""
    ).strip()

    if not page_link:
        raise FacebookPostError("Facebook Page URL is missing from Excel.", retryable=False)

    if not caption:
        raise FacebookPostError("Post caption is missing from Excel.", retryable=False)

    if not media_path:
        raise FacebookPostError("Media path is missing from Excel.", retryable=False)

    try:
        driver.get(page_link)
    except WebDriverException as error:
        raise FacebookPostError(
            f"Could not open the target Facebook Page: {page_link}",
            retryable=True,
        ) from error
    _wait_for_page_ready(driver)
    _check_facebook_session(driver)
    _dismiss_call_now_popup(driver, appearance_timeout=1)

    composer = _find_composer_trigger(driver)

    if composer is None:
        raise FacebookPostError(
            "Could not locate the Page composer in Facebook's DOM structure."
        )

    try:
        _click(composer, driver)
    except Exception as error:
        raise FacebookPostError(
            "Could not open the Facebook post composer.",
            retryable=True,
        ) from error

    _dismiss_call_now_popup(driver, appearance_timeout=3)
    dialog = _wait_for_dialog(driver)

    file_input = _find_file_input(driver, dialog)

    try:
        file_input.send_keys(media_path)
    except Exception as error:
        raise FacebookPostError(
            "Could not upload media through Facebook's file input. "
            "The Windows file dialog should not be opened manually."
        ) from error

    dialog = _visible_dialog(driver) or dialog

    def locate_caption(_):
        try:
            current_dialog = _visible_dialog(driver) or dialog
            return _find_caption_box(current_dialog) or False
        except StaleElementReferenceException:
            return False

    try:
        caption_box = WebDriverWait(driver, 20).until(locate_caption)
    except TimeoutException as error:
        raise FacebookPostError(
            "Facebook did not expose the caption editor after media upload.",
            retryable=True,
        ) from error

    try:
        _click(caption_box, driver)
        input_caption(driver, caption_box, caption)
        entered_caption = driver.execute_script(
            """
            const element = arguments[0];
            return (
                element.innerText ||
                element.textContent ||
                element.value ||
                ''
            ).trim();
            """,
            caption_box,
        )
    except Exception as error:
        raise FacebookPostError(
            "Could not enter or verify the post caption.",
            retryable=True,
        ) from error

    if " ".join(str(entered_caption).split()) != " ".join(caption.split()):
        raise FacebookPostError(
            "Facebook caption input verification failed.",
            retryable=True,
        )

    video_extensions = {
        ".mp4",
        ".mov",
        ".avi",
        ".mkv",
        ".webm",
        ".m4v",
        ".mpeg",
        ".mpg",
        ".3gp",
    }

    is_video = Path(media_path).suffix.casefold() in video_extensions
    next_click_count = 2 if is_video else 1

    for step in range(1, next_click_count + 1):
        action, action_button = _wait_for_workflow_action(
            driver,
            timeout=POST_BUTTON_TIMEOUT,
        )

        if action != "next":
            raise FacebookPostError(
                f"Expected Facebook's Next button at step "
                f"{step}/{next_click_count}, but found {action!r}. "
                "The post was not submitted."
            )

        previous_snapshot = _workflow_snapshot(driver)

        try:
            _click_once(action_button, driver)
        except Exception as error:
            raise FacebookPostError(
                f"Could not safely click Facebook's Next button at step "
                f"{step}/{next_click_count}. The workflow was stopped to avoid "
                "accidentally skipping a step."
            ) from error

        _wait_for_step_transition(
            driver,
            action_button,
            previous_snapshot,
            timeout=20,
        )

    post_button = _wait_for_post_button(
        driver,
        timeout=POST_BUTTON_TIMEOUT,
    )

    if before_submit is not None:
        before_submit()

    try:
        _click_once(post_button, driver)
    except Exception as error:
        raise PublishUnknownError(
            "Facebook did not confirm whether the Post click was accepted. "
            "Check the Page before retrying to avoid publishing a duplicate."
        ) from error

    try:
        _dismiss_call_now_popup(
            driver,
            timeout=5,
            appearance_timeout=5,
        )
    except FacebookPostError as error:
        raise PublishUnknownError(
            "The Post button was clicked, but Facebook's popup could not "
            "be closed safely. The post may already have been submitted. "
            "Check the Page before retrying to avoid a duplicate."
        ) from error

    _wait_for_publish_confirmation(driver, timeout=90)


# ----- Open Published Post -----
def click_published_post_timestamp(
    driver,
    caption: str,
    attempts: int = POST_TIMESTAMP_CYCLES,
    page_link: str = "",
) -> None:
    import time

    from selenium.common.exceptions import (
        StaleElementReferenceException,
        TimeoutException,
        WebDriverException,
    )
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.support.ui import WebDriverWait

    attempts = max(1, int(attempts))
    time.sleep(POST_PUBLISH_WAIT_SECONDS)

    for cycle in range(1, attempts + 1):

        try:
            if page_link:
                driver.get(page_link)
            else:
                driver.refresh()
        except WebDriverException as error:
            raise FacebookPostError(
                "Could not reload the Facebook Page while locating the published post.",
                retryable=True,
            ) from error

        _wait_for_page_ready(driver, timeout=30)
        _check_facebook_session(driver)

        try:
            _dismiss_call_now_popup(driver, timeout=3)
        except FacebookPostError:
            pass

        article = _find_post_article(driver, caption, timeout=8)

        if article is None:
            for _ in range(3):
                _scroll_to_render_posts(driver, pixels=450, wait=1)
                article = _find_post_article(driver, caption, timeout=5)
                if article is not None:
                    break

        if article is None:
            continue

        # Get visible header anchors. Do not require
        # a permalink before hovering.
        anchors = driver.execute_script(
            """
            const article = arguments[0];
            const root = article.getBoundingClientRect();

            return [...article.querySelectorAll('a[href]')]
                .filter(a => {
                    const r = a.getBoundingClientRect();
                    if (r.width <= 0 || r.height <= 0)
                        return false;

                    const top = r.top - root.top;
                    if (top < -10 || top > 250)
                        return false;

                    const href = a.href || '';

                    // Exclude links to the Page profile.
                    if (/profile\\.php\\?id=/i.test(href))
                        return false;

                    if (/facebook\\.com\\/(people|pages)\\//i.test(href))
                        return false;

                    // Exclude avatars.
                    if (a.querySelector('svg image, img'))
                        return false;

                    const text = (
                        (a.innerText || '') + ' ' +
                        (a.getAttribute('aria-label') || '')
                    ).toLowerCase();

                    if (/ai content|published by|được đăng bởi/i
                        .test(text))
                        return false;

                    return true;
                });
            """,
            article,
        )

        matched = []

        for index, anchor in enumerate(anchors):
            try:
                # Hover before checking href.
                driver.execute_script(
                    """
                    arguments[0].scrollIntoView({
                        block: 'center',
                        inline: 'nearest'
                    });
                    """,
                    anchor,
                )

                ActionChains(driver).move_to_element(anchor).perform()

                try:
                    WebDriverWait(
                        driver,
                        3,
                        poll_frequency=0.2,
                    ).until(
                        lambda d: bool(
                            _post_permalink(anchor.get_attribute("href") or "")
                        )
                    )
                except TimeoutException:
                    pass

                href = anchor.get_attribute("href") or ""
                permalink = _post_permalink(href)

                if permalink:
                    matched.append((anchor, permalink))

            except (StaleElementReferenceException, WebDriverException):
                continue

        if len(matched) != 1:
            continue

        target, expected_permalink = matched[0]

        old_handle = driver.current_window_handle
        old_handles = set(driver.window_handles)
        old_url = driver.current_url

        try:
            ActionChains(driver).move_to_element(target).click().perform()
        except (StaleElementReferenceException, WebDriverException):
            continue

        try:
            WebDriverWait(driver, 15, poll_frequency=0.25).until(
                lambda d: (
                    bool(set(d.window_handles) - old_handles)
                    or d.current_url != old_url
                )
            )
        except TimeoutException:
            continue

        new_handles = set(driver.window_handles) - old_handles

        if new_handles:
            driver.switch_to.window(next(iter(new_handles)))

        _wait_for_page_ready(driver, timeout=30)

        permalink = _post_permalink(driver.current_url)

        if permalink and permalink == expected_permalink:
            return

        if new_handles:
            driver.close()
            driver.switch_to.window(old_handle)

    raise FacebookPostError(
        "Published post timestamp/permalink could not be verified after hovering.",
        retryable=True,
    )


# ----- Post Permalink Normalization -----
def _post_permalink(url: str) -> str:

    if not url:
        return ""

    try:
        parsed = urlparse(str(url).strip())
    except ValueError:
        return ""

    hostname = (parsed.hostname or "").lower()

    if hostname not in {
        "facebook.com",
        "www.facebook.com",
        "m.facebook.com",
        "web.facebook.com",
    }:
        return ""

    path = parsed.path.rstrip("/")
    query = parse_qs(parsed.query)

    # Standard Page post, video and Reel URLs.
    if re.search(
        r"/(?:posts|videos|reel|permalink)/\d+$",
        path,
        flags=re.IGNORECASE,
    ):
        return "https://www.facebook.com" + path + "/"

    # Facebook story permalink.
    if path.lower() == "/story.php":
        story_ids = query.get("story_fbid", [])
        page_ids = query.get("id", [])

        if story_ids and story_ids[0].isdigit():
            result = "https://www.facebook.com/story.php" f"?story_fbid={story_ids[0]}"

            if page_ids and page_ids[0].isdigit():
                result += f"&id={page_ids[0]}"

            return result

    # Alternative Facebook permalink format.
    if path.lower() == "/permalink.php":
        story_ids = query.get("story_fbid", [])
        page_ids = query.get("id", [])

        if story_ids and story_ids[0].isdigit():
            result = "https://www.facebook.com/story.php" f"?story_fbid={story_ids[0]}"

            if page_ids and page_ids[0].isdigit():
                result += f"&id={page_ids[0]}"

            return result

    return ""


# ----- Reel Comment Panel -----
def ensure_reel_comment_open(driver, timeout: int = 15) -> bool:
    if not re.search(r"facebook\.com/reel/\d+", driver.current_url, re.IGNORECASE):
        return False

    selector = '[role="button"][aria-label="Comment"][aria-expanded]'

    def find_button(current):
        buttons = current.find_elements(By.CSS_SELECTOR, selector)

        for button in buttons:
            try:
                if button.is_displayed() and button.is_enabled():
                    return button
            except StaleElementReferenceException:
                continue

        return False

    try:
        button = WebDriverWait(driver, timeout, poll_frequency=0.3).until(find_button)
    except TimeoutException as error:
        raise FacebookPostError("Cannot find Reel comment button.") from error

    state = button.get_attribute("aria-expanded")

    if state == "true":
        return True

    if state != "false":
        raise FacebookPostError(f"Unexpected Reel comment panel state: {state}")

    try:
        _click_once(button, driver)
    except Exception as error:
        raise FacebookPostError("Cannot click Reel comment button.") from error

    def panel_opened(current):
        current_button = find_button(current)

        if not current_button:
            return False

        return current_button.get_attribute("aria-expanded") == "true"

    try:
        WebDriverWait(driver, timeout, poll_frequency=0.3).until(panel_opened)
    except TimeoutException as error:
        raise FacebookPostError("Reel comment panel did not open.") from error

    return True


# ----- Publish Comment -----


def _comment_snapshot(driver, comment: str):
    return driver.execute_script(
        r"""
        const expected = arguments[0];

        const normalize = value => String(value || '')
        .normalize('NFC')
        .replace(/[\u200B-\u200F\u034F\uFEFF]/g, '')
        .replace(/\p{Extended_Pictographic}/gu, '')
        .replace(/[\uFE0E\uFE0F]/g, '')
        .replace(/\s+/g, ' ')
        .trim()
        .toLowerCase();

        const normalizeUrl = value => String(value || '')
        .replace(/^https?:\/\//i, '')
        .replace(/^www\./i, '')
        .replace(/\/+$/, '')
        .toLowerCase();

        const expectedUrls = (
        expected.match(/https?:\/\/[^\s]+/gi) || []
        ).map(normalizeUrl);

        const expectedText = normalize(
        expected.replace(/https?:\/\/[^\s]+/gi, '')
        ).replace(/[^\p{L}\p{N}\s]/gu, '')
         .replace(/\s+/g, ' ')
         .trim();

        const containers = Array.from(
        document.querySelectorAll(
            'div[data-virtualized="false"]'
        )
        );

        const matches = [];
        const samples = [];

        for (let i = 0; i < containers.length; i++) {
        const raw = containers[i].innerText || '';
        const normalized = normalize(raw);

        const visibleText = normalized
            .replace(/[^\p{L}\p{N}\s]/gu, '')
            .replace(/\s+/g, ' ')
            .trim();

        const textMatched = expectedText
            ? visibleText.includes(expectedText)
            : true;

        const urlMatched = expectedUrls.every(url =>
            normalizeUrl(normalized).includes(url)
        );

        const matched = textMatched && urlMatched;

        samples.push({
            index: i,
            matched,
            textMatched,
            urlMatched,
            preview: raw.slice(-500)
        });

        if (matched) {
            matches.push(i);
        }
        }

        return {
        count: matches.length,
        containers: containers.length,
        matches,
        samples
        };
        """,
        comment,
)

def post_comment_on_opened_post(driver, comment: str, before_send=None) -> bool:
    comment = str(comment or "").strip()

    if not comment:
        return False

    permalink = _post_permalink(driver.current_url)

    if not permalink:
        raise FacebookPostError("Invalid post URL.", retryable=False)

    _wait_for_page_ready(driver, timeout=30)

    if "/reel/" in permalink.lower():
        ensure_reel_comment_open(driver)

    normalized = " ".join(comment.split())

    def find_editor():
        elements = driver.find_elements(
            By.CSS_SELECTOR, '[contenteditable="true"], [role="textbox"], textarea'
        )

        for element in elements:
            try:
                if not element.is_displayed():
                    continue

                label = " ".join(
                    filter(
                        None,
                        [
                            element.get_attribute("aria-label"),
                            element.get_attribute("aria-placeholder"),
                            element.get_attribute("data-placeholder"),
                            element.get_attribute("placeholder"),
                        ],
                    )
                ).casefold()

                if "comment" in label or "bình luận" in label:
                    return element

            except StaleElementReferenceException:
                continue

        return False

    try:
        editor = WebDriverWait(driver, 15, poll_frequency=0.3).until(
            lambda d: find_editor()
        )
    except TimeoutException as error:
        raise FacebookPostError("Comment editor not found.") from error

    before = _comment_snapshot(driver, comment)

    if before.get("count", 0) > 0:
        return True

    previous_clipboard = None

    try:
        previous_clipboard = pyperclip.paste()
    except Exception:
        pass

    try:
        editor.click()
        pyperclip.copy(comment)
        editor.send_keys(Keys.CONTROL, "v")
        time.sleep(0.5)
    except Exception as error:
        raise FacebookPostError("Failed to enter comment.") from error
    finally:
        if previous_clipboard is not None:
            try:
                pyperclip.copy(previous_clipboard)
            except Exception:
                pass

    typed = driver.execute_script(
        """
        const el = arguments[0];
        return (
            el.innerText ||
            el.textContent ||
            el.value ||
            ''
        ).trim();
        """,
        editor,
    )

    if " ".join(str(typed).split()) != normalized:
        raise FacebookPostError("Comment input verification failed.")

    def find_send_button():
        return driver.execute_script(
            r"""
            const editor = arguments[0];

            const visible = element => {
                const r = element.getBoundingClientRect();
                return r.width > 0 && r.height > 0;
            };

            let root = editor.closest('form');

            if (!root) {
                let node = editor.parentElement;

                for (let i = 0; node && i < 7; i++) {
                    const buttons = node.querySelectorAll(
                        'button, [role="button"]'
                    );

                    if (buttons.length > 0 && buttons.length <= 12) {
                        root = node;
                        break;
                    }

                    node = node.parentElement;
                }
            }

            if (!root) return null;

            const buttons = [
                ...root.querySelectorAll(
                    'button, [role="button"]'
                )
            ].filter(el =>
                visible(el) &&
                !el.disabled &&
                el.getAttribute('aria-disabled') !== 'true'
            );

            const named = buttons.filter(el => {
                const label = [
                    el.getAttribute('aria-label'),
                    el.getAttribute('title'),
                    el.getAttribute('data-testid')
                ].filter(Boolean).join(' ').toLowerCase();

                return /post comment|send comment|submit comment|^send$|^post$|^gửi$|^đăng$/.test(label);
            });

            if (named.length === 1) return named[0];

            const editorRect = editor.getBoundingClientRect();

            const candidates = buttons.filter(el => {
                const r = el.getBoundingClientRect();

                return r.left >= editorRect.left &&
                    r.left <= editorRect.right + 100 &&
                    r.top >= editorRect.top - 20 &&
                    r.top <= editorRect.bottom + 100;
            });

            const iconButtons = candidates.filter(el =>
                el.querySelector('svg')
            );

            return iconButtons.length === 1
                ? iconButtons[0]
                : null;
            """,
            editor,
        )

    send_button = find_send_button()

    try:
        latest = _comment_snapshot(driver, comment)
    except WebDriverException as error:
        raise FacebookPostError(
            "Could not recheck existing comments before sending.",
            retryable=True,
        ) from error

    if latest.get("count", 0) > before.get("count", 0):
        return True

    if before_send is not None:
        before_send()

    try:
        if send_button is not None:
            _click_once(send_button, driver)
        else:
            editor.send_keys(Keys.ENTER)

    except Exception as error:
        raise PublishUnknownError(
            "Comment submission attempted but not confirmed. " "Do not resend."
        ) from error

    def comment_is_visible():
        result = _comment_snapshot(driver, comment)

        if result["count"] > before["count"]:
            return True, result

        return False, result

    deadline = time.monotonic() + 30
    last_result = before

    while time.monotonic() < deadline:
        try:
            confirmed, last_result = comment_is_visible()

            if confirmed:
                return True

        except WebDriverException:
            pass
        time.sleep(0.5)

    raise PublishUnknownError(
        "Comment may have been submitted, "
        "but no new matching comment was confirmed. "
        "Do not resend automatically."
    )


# ----- Get Opened Post URL -----
def get_opened_post_url(driver) -> str:
    url = _post_permalink(driver.current_url)
    if not url:
        raise FacebookPostError(
            "Current browser address is not a verified post permalink; URL not saved.",
            retryable=True,
        )
    return url


def open_and_verify_post_url(driver, post_url: str, caption: str = "") -> str:
    expected_url = _post_permalink(post_url)
    if not expected_url:
        raise FacebookPostError(
            "Saved post_url is not a valid Facebook post permalink.",
            retryable=False,
        )

    try:
        driver.get(expected_url)
    except WebDriverException as error:
        raise FacebookPostError(
            f"Could not open saved Facebook post URL: {expected_url}",
            retryable=True,
        ) from error

    _wait_for_page_ready(driver, timeout=30)
    _check_facebook_session(driver)

    actual_url = get_opened_post_url(driver)
    if actual_url != expected_url:
        raise FacebookPostError(
            "Opened Facebook URL does not match the saved post permalink.",
            retryable=True,
        )

    if caption:
        try:
            article = _find_post_article(driver, caption, timeout=10)
        except WebDriverException as error:
            raise FacebookPostError(
                "Could not inspect the opened Facebook post.",
                retryable=True,
            ) from error

        if article is None:
            raise FacebookPostError(
                "The opened permalink does not contain the expected post caption.",
                retryable=True,
            )

    return actual_url


def comment_exists_on_opened_post(
    driver,
    comment: str,
    timeout: int = 8,
) -> bool:
    comment = str(comment or "").strip()
    if not comment:
        return True

    permalink = _post_permalink(driver.current_url)
    if not permalink:
        raise FacebookPostError(
            "Cannot verify a comment because the current URL is not a post permalink.",
            retryable=False,
        )

    if "/reel/" in permalink.lower():
        ensure_reel_comment_open(driver)

    deadline = time.monotonic() + max(0, timeout)
    while True:
        try:
            result = _comment_snapshot(driver, comment)
            if result.get("count", 0) > 0:
                return True
        except WebDriverException as error:
            raise FacebookPostError(
                f"Could not inspect existing Facebook comments: {error}",
                retryable=True,
            ) from error

        if time.monotonic() >= deadline:
            return False
        time.sleep(0.5)
