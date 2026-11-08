import time

from pathlib import Path
from urllib.parse import urlsplit

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

# ----- Facebook Settings -----
FACEBOOK_HOME_URL = "https://www.facebook.com/"
PAGE_READY_TIMEOUT = 30
ACCOUNT_MENU_TIMEOUT = 15
POST_BUTTON_TIMEOUT = 60
POST_PUBLISH_WAIT_SECONDS = 10
POST_TIMESTAMP_CYCLES = 3
POST_ACTIONS = {"post", "publish", "share", "đăng", "chia sẻ"}
NEXT_ACTIONS = {"next", "continue", "proceed", "tiếp", "tiếp theo", "tiếp tục"}


# ----- Facebook Exceptions -----
class FacebookSwitchError(RuntimeError):
    def __init__(
        self,
        message: str,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.retryable = bool(retryable)


class FacebookPostError(RuntimeError):
    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = bool(retryable)


class PublishUnknownError(FacebookPostError):
    def __init__(self, message: str):
        super().__init__(message, retryable=False)


# ----- Switch Facebook Page -----
def open_facebook_home(driver) -> str:
    if driver is None:
        raise RuntimeError("AdsPower WebDriver is not available.")

    try:
        driver.get(FACEBOOK_HOME_URL)
    except TimeoutException:
        pass
    except WebDriverException as error:
        raise RuntimeError(f"Cannot open Facebook Home: {error}") from error

    try:
        WebDriverWait(driver, PAGE_READY_TIMEOUT).until(
            lambda browser: browser.execute_script("return document.readyState")
            in ("interactive", "complete")
        )
    except TimeoutException as error:
        raise RuntimeError("Facebook Home loading timed out.") from error

    current_url = driver.current_url or ""

    try:
        parsed = urlsplit(current_url)
        hostname = (parsed.hostname or "").lower()
        path = parsed.path.lower()
    except ValueError as error:
        raise RuntimeError("Facebook returned an invalid URL.") from error

    if not (hostname == "facebook.com" or hostname.endswith(".facebook.com")):
        raise RuntimeError(f"Unexpected Facebook URL: {current_url}")

    if any(
        path == item or path.startswith(f"{item}/")
        for item in ("/login", "/checkpoint", "/recover")
    ):
        raise RuntimeError("Facebook requires login or checkpoint verification.")

    email_fields = driver.find_elements(
        By.CSS_SELECTOR,
        'input[name="email"], input[type="email"]',
    )
    password_fields = driver.find_elements(
        By.CSS_SELECTOR,
        'input[name="pass"], input[type="password"]',
    )

    if any(element.is_displayed() for element in email_fields) and any(
        element.is_displayed() for element in password_fields
    ):
        raise RuntimeError("Facebook login is required.")

    return current_url


def open_account_menu(driver) -> bool:
    if driver is None:
        raise RuntimeError("AdsPower WebDriver is not available.")

    popup_selector = (
        "[role='menu'], [role='dialog'], [role='listbox'], "
        "[data-pagelet*='ProfilePlusActionsMenu'], "
        "[data-pagelet*='ProfileSwitcher'], "
        "[data-testid*='profile_switcher']"
    )

    def is_menu_open(browser):
        return browser.execute_script(
            """
            const selector = arguments[0];
            const visible = element => {
                const style = getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0 &&
                    style.display !== 'none' &&
                    style.visibility !== 'hidden' &&
                    Number(style.opacity || 1) > 0;
            };
            return [...document.querySelectorAll(selector)].some(visible);
            """,
            popup_selector,
        )

    # Avoid clicking again if the menu is already open.
    if is_menu_open(driver):
        return True

    # Find the Account Menu button.
    try:
        button = WebDriverWait(driver, ACCOUNT_MENU_TIMEOUT).until(
            lambda browser: browser.execute_script(r"""
                const selectors = [
                    '[data-testid="blue_bar_profile_link"]',
                    '[aria-label*="account, your profile and settings" i]',
                    '[aria-label*="your profile and settings" i]',
                    '[aria-label*="your profile" i]',
                    '[aria-label*="account menu" i]',
                    '[aria-label*="tài khoản" i]',
                    '[aria-label*="trang cá nhân" i]',
                    'button[title*="account" i]',
                    '[role="button"][title*="account" i]'
                ];

                const visible = element => {
                    const style = getComputedStyle(element);
                    const rect = element.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0 &&
                        style.display !== 'none' &&
                        style.visibility !== 'hidden' &&
                        Number(style.opacity || 1) > 0;
                };

                const norm = value => String(value || '')
                    .normalize('NFC')
                    .toLowerCase()
                    .replace(/\s+/g, ' ')
                    .trim();

                const found = new Map();

                for (const selector of selectors) {
                    for (const matched of document.querySelectorAll(selector)) {
                        const element = matched.closest(
                            'button, [role="button"], [tabindex="0"]'
                        ) || matched;

                        if (!visible(element)) continue;

                        const label = norm([
                            element.getAttribute('aria-label'),
                            element.getAttribute('title'),
                            matched.getAttribute('aria-label'),
                            matched.getAttribute('title'),
                            element.getAttribute('data-testid')
                        ].join(' '));

                        if (/messenger|notifications|facebook menu|business suite|ads manager/.test(label)) {
                            continue;
                        }

                        if (
                            element.tagName === 'A' &&
                            !element.matches('[role="button"], [tabindex="0"], [data-testid]')
                        ) {
                            continue;
                        }

                        const rect = element.getBoundingClientRect();
                        let score = 0;

                        if (rect.left + rect.width / 2 > window.innerWidth * 0.7) {
                            score += 100;
                        }

                        if (rect.top < 150) score += 40;
                        if (label.includes('blue_bar_profile_link')) score += 180;
                        if (label.includes('your profile')) score += 50;
                        if (label.includes('tài khoản')) score += 50;
                        if (label.includes('trang cá nhân')) score += 50;

                        if (!found.has(element) || found.get(element) < score) {
                            found.set(element, score);
                        }
                    }
                }

                return [...found.entries()]
                    .sort((a, b) => b[1] - a[1])[0]?.[0] || null;
                """)
        )
    except TimeoutException as error:
        raise RuntimeError("Facebook Account Menu button was not found.") from error

    # Click the Account Menu button.
    try:
        button.click()
    except WebDriverException:
        try:
            driver.execute_script("arguments[0].click();", button)
        except WebDriverException as error:
            raise RuntimeError(
                f"Cannot click Facebook Account Menu: {error}"
            ) from error

    # Confirm that the menu is visible.
    try:
        WebDriverWait(driver, ACCOUNT_MENU_TIMEOUT).until(is_menu_open)
    except TimeoutException as error:
        raise RuntimeError(
            "Account Menu was clicked, but the menu did not open."
        ) from error

    return True


def verify_facebook_page(driver, page_name: str) -> bool:
    if driver is None:
        raise RuntimeError("AdsPower WebDriver is not available.")

    page_name = (page_name or "").strip()

    if not page_name:
        raise ValueError("Page name is empty.")

    if not open_account_menu(driver):
        raise RuntimeError("Could not open Facebook Account Menu.")

    script = r"""
        const target = String(arguments[0] || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/\s+/g, " ")
            .trim()
            .toLowerCase();

        const normalize = value => String(value || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/\s+/g, " ")
            .trim()
            .toLowerCase();

        const visible = element => {
            const style = window.getComputedStyle(element);
            const rect = element.getBoundingClientRect();

            return rect.width > 0 &&
                rect.height > 0 &&
                style.display !== "none" &&
                style.visibility !== "hidden" &&
                Number(style.opacity || 1) > 0;
        };

        const selectors = [
            "[role='menu']",
            "[role='dialog']",
            "[aria-modal='true']",
            "[data-pagelet*='ProfilePlusActionsMenu']",
            "[data-pagelet*='ProfileSwitcher']",
            "[data-testid*='profile_switcher']"
        ].join(",");

        const roots = [...document.querySelectorAll(selectors)]
            .filter(visible);

        const allLabels = [
            "see all profiles",
            "view all profiles",
            "xem tat ca trang ca nhan",
            "xem tat ca trang"
        ];

        for (const root of roots) {
            const controls = [
                ...root.querySelectorAll(
                    "button, [role='button'], a, [tabindex='0']"
                )
            ].filter(visible);

            const switchControl = controls.find(element => {
                const text = normalize([
                    element.innerText,
                    element.getAttribute("aria-label"),
                    element.getAttribute("title")
                ].filter(Boolean).join(" "));

                return allLabels.some(label =>
                    text.includes(normalize(label))
                );
            });

            if (!switchControl) {
                continue;
            }

            const controlRect = switchControl.getBoundingClientRect();
            let ancestor = switchControl;

            for (
                let depth = 0;
                ancestor && depth < 7 && root.contains(ancestor);
                depth++, ancestor = ancestor.parentElement
            ) {
                const candidates = [
                    ancestor,
                    ...ancestor.querySelectorAll("*")
                ];

                const matches = candidates.filter(element => {
                    if (!visible(element)) {
                        return false;
                    }

                    if (normalize(element.innerText) !== target) {
                        return false;
                    }

                    return ![...element.children].some(child =>
                        normalize(child.innerText) === target
                    );
                });

                const matched = matches.some(element => {
                    const rect = element.getBoundingClientRect();
                    const verticalDistance = Math.abs(
                        (rect.top + rect.height / 2) -
                        (controlRect.top + controlRect.height / 2)
                    );

                    const horizontalOverlap =
                        rect.right >= controlRect.left - 80 &&
                        rect.left <= controlRect.right + 80;

                    return verticalDistance <= 220 &&
                        horizontalOverlap;
                });

                if (matched) {
                    return {
                        menu_open: true,
                        verified: true
                    };
                }
            }
        }

        return {
            menu_open: roots.length > 0,
            verified: false
        };
    """

    try:
        result = WebDriverWait(driver, ACCOUNT_MENU_TIMEOUT).until(
            lambda browser: browser.execute_script(script, page_name)
        )
    except TimeoutException as error:
        raise RuntimeError(
            f"Could not verify active Facebook Page: '{page_name}'."
        ) from error

    if not result.get("verified"):
        raise RuntimeError(f"Active Facebook Page does not match: '{page_name}'.")

    return True


def find_page_in_account_menu(driver, page_name: str) -> bool:
    if not page_name or not page_name.strip():
        raise ValueError("Page name is empty.")

    script = r"""
        const action = arguments[0];
        const pageName = arguments[1] || "";

        const normalize = value => String(value || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/\s+/g, " ")
            .trim()
            .toLowerCase();

        const visible = element => {
            const style = window.getComputedStyle(element);
            const rect = element.getBoundingClientRect();

            return rect.width > 0 &&
                rect.height > 0 &&
                style.display !== "none" &&
                style.visibility !== "hidden" &&
                Number(style.opacity || 1) > 0;
        };

        const popupSelector = [
            "[role='menu']",
            "[role='dialog']",
            "[role='listbox']",
            "[aria-modal='true']",
            "[data-pagelet*='ProfilePlusActionsMenu']",
            "[data-pagelet*='ProfileSwitcher']",
            "[data-testid*='profile_switcher']"
        ].join(",");

        const allRoots = Array.from(
            document.querySelectorAll(popupSelector)
        ).filter(visible);

        const pickerMarkers = [
            "chon trang ca nhan",
            "trang ca nhan cua ban",
            "choose a profile",
            "select a profile",
            "profiles and pages",
            "pages and profiles",
            "your profiles and pages",
            "profils et pages",
            "profile und seiten",
            "perfiles y paginas",
            "perfis e paginas",
            "profil dan halaman",
        ];

        const pickerRoots = allRoots.filter(root => {
            const text = normalize(root.innerText);

            const hasPickerTitle = pickerMarkers.some(
                marker => text.includes(normalize(marker))
            );

            const searchInput = root.querySelector(
                "input, [role='searchbox'], [role='combobox']"
            );

            const searchLabel = normalize([
                searchInput?.getAttribute("placeholder"),
                searchInput?.getAttribute("aria-label")
            ].filter(Boolean).join(" "));

            const hasPageSearch = [
                "profile", "page", "trang", "profil",
                "pagina", "perfil", "seite", "halaman"
            ].some(term => searchLabel.includes(term));

            const isDialog = root.matches(
                "[role='dialog'], [aria-modal='true']"
            );

            return hasPickerTitle || (isDialog && hasPageSearch);
        });

        const roots = action === "click_all"
            ? allRoots
            : pickerRoots;

        const signature = roots
            .map(root => normalize(root.innerText))
            .join("|");

        const controls = roots.length
            ? roots.flatMap(root => Array.from(
                root.querySelectorAll(
                    "button, [role='button'], a, [tabindex='0']"
                )
            ))
            : Array.from(document.querySelectorAll(
                "button, [role='button'], a, [tabindex='0']"
            ));

        const uniqueControls = Array.from(new Set(controls))
            .filter(visible);

        const findControl = labels => uniqueControls.find(element => {
            const text = normalize([
                element.innerText,
                element.getAttribute("aria-label"),
                element.getAttribute("title")
            ].filter(Boolean).join(" "));

            return labels.some(label => text.includes(normalize(label)));
        });

        const allLabels = [
            "see all profiles",
            "see all pages",
            "view all profiles",
            "view all pages",
            "xem tat ca trang ca nhan",
            "xem tat ca cac trang",
            "xem tat ca trang",
            "voir tous les profils",
            "voir toutes les pages",
            "alle profile anzeigen",
            "alle seiten anzeigen",
            "ver todos los perfiles",
            "ver todas las paginas",
            "ver todos os perfis",
            "ver todas as paginas",
            "lihat semua profil",
            "lihat semua halaman",
            "查看所有个人主页",
            "查看所有主页",
            "すべてのプロフィールを見る",
            "すべてのページを見る",
            "모든 프로필 보기",
            "ทุกโปรไฟล์"
        ];

        const moreLabels = [
            "see more pages",
            "see more page",
            "see more",
            "show more pages",
            "show more",
            "load more pages",
            "load more",
            "view more",
            "xem them cac trang",
            "xem them trang",
            "xem them",
            "voir plus de pages",
            "voir plus",
            "afficher plus",
            "weitere seiten anzeigen",
            "mehr anzeigen",
            "ver mas paginas",
            "ver mas",
            "ver mais paginas",
            "ver mais",
            "lihat halaman lainnya",
            "lihat selengkapnya",
            "查看更多主页",
            "查看更多",
            "もっと見る",
            "さらに表示",
            "더 보기",
            "ดูเพิ่มเติม"
        ];

        if (action === "click_all" || action === "click_more") {
            const labels = action === "click_all"
                ? allLabels
                : moreLabels;

            const button = findControl(labels);

            if (!button) {
                return {
                    clicked: false,
                    signature: signature
                };
            }

            const before = signature;
            button.scrollIntoView({ block: "center" });
            button.click();

            return {
                clicked: true,
                before: before
            };
        }

        if (!roots.length) {
            return {
                menu_open: false,
                found: false,
                has_more: false,
                signature: ""
            };
        }

        const target = normalize(pageName);

        const found = roots.some(root => {
            const elements = [
                root,
                ...root.querySelectorAll("*")
            ];

            return elements.some(element => {
                if (!visible(element)) {
                    return false;
                }

                const values = [
                    element.innerText,
                    element.getAttribute("aria-label"),
                    element.getAttribute("title")
                ];

                return values.some(value =>
                    normalize(value) === target
                );
            });
        });

        const moreButton = findControl(moreLabels);

        const loading = roots.some(root =>
            root.querySelector(
                "[aria-busy='true'], [role='progressbar'], " +
                "[data-visualcompletion='loading-state']"
            )
        );

        return {
            menu_open: true,
            found: found,
            has_more: Boolean(moreButton),
            more_disabled: Boolean(
                moreButton && (
                    moreButton.disabled ||
                    moreButton.getAttribute("aria-disabled") === "true"
                )
            ),
            loading: loading,
            signature: signature
        };
    """

    # ----- Open the Page Picker Only When Necessary -----
    initial_state = driver.execute_script(
        script,
        "inspect",
        page_name,
    )

    if not initial_state["menu_open"]:
        result = driver.execute_script(
            script,
            "click_all",
            page_name,
        )

        if not result["clicked"]:
            raise RuntimeError("Could not find the See all profiles button.")

        try:
            WebDriverWait(
                driver,
                ACCOUNT_MENU_TIMEOUT,
            ).until(
                lambda current_driver: (
                    lambda state: state["menu_open"]
                    and (
                        state["found"]
                        or state["has_more"]
                        or state["signature"] != result["before"]
                    )
                )(
                    current_driver.execute_script(
                        script,
                        "inspect",
                        page_name,
                    )
                )
            )

        except TimeoutException as error:
            raise RuntimeError("Facebook did not open the Pages list.") from error

    # ----- Find Page -----
    while True:
        state = driver.execute_script(
            script,
            "inspect",
            page_name,
        )

        if not state["menu_open"]:
            raise RuntimeError("Facebook Pages list is not open.")

        if state["found"]:
            return True

        if not state["has_more"]:
            raise RuntimeError(
                f"Target Page '{page_name}' was not found. "
                "No more Pages are available."
            )

        # ----- Load more Pages -----
        result = driver.execute_script(
            script,
            "click_more",
            page_name,
        )

        if not result["clicked"]:
            raise RuntimeError("Could not click See more Pages.")

        try:
            WebDriverWait(
                driver,
                ACCOUNT_MENU_TIMEOUT,
            ).until(
                lambda current_driver: (
                    lambda current: current["found"]
                    or (
                        current["signature"] != result["before"]
                        and not current["loading"]
                        and not current["more_disabled"]
                    )
                )(
                    current_driver.execute_script(
                        script,
                        "inspect",
                        page_name,
                    )
                )
            )
        except TimeoutException as exc:
            raise RuntimeError("Facebook did not load additional Pages.") from exc


def select_page_in_account_menu(driver, page_name: str) -> str:
    if not page_name or not page_name.strip():
        raise ValueError("Page name is empty.")

    script = r"""
        const target = String(arguments[0] || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/[^\p{L}\p{N}\s]/gu, " ")
            .replace(/\s+/g, " ")
            .trim()
            .toLowerCase();

        const normalize = value => String(value || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/[^\p{L}\p{N}\s]/gu, " ")
            .replace(/\s+/g, " ")
            .trim()
            .toLowerCase();

        const visible = element => {
            const style = window.getComputedStyle(element);
            const rect = element.getBoundingClientRect();

            return rect.width > 0 &&
                rect.height > 0 &&
                style.display !== "none" &&
                style.visibility !== "hidden" &&
                Number(style.opacity || 1) > 0;
        };

        const selectors = [
            "[role='menu']",
            "[role='dialog']",
            "[role='listbox']",
            "[aria-modal='true']",
            "[data-pagelet*='ProfileSwitcher']",
            "[data-testid*='profile_switcher']"
        ].join(",");

        const roots = Array.from(
            document.querySelectorAll(selectors)
        ).filter(visible);

        const markers = [
            "chon trang ca nhan",
            "trang trang ca nhan cua ban",
            "choose a profile",
            "profiles and pages",
            "pages and profiles",
            "your profiles and pages"
        ];

        const pickerRoots = roots.filter(root => {
            const text = normalize(root.innerText);

            const hasTitle = markers.some(
                marker => text.includes(marker)
            );

            const search = root.querySelector(
                "input, [role='searchbox'], [role='combobox']"
            );

            const searchText = normalize([
                search?.getAttribute("placeholder"),
                search?.getAttribute("aria-label")
            ].filter(Boolean).join(" "));

            const hasSearch = [
                "trang", "page", "profile", "profil", "pagina"
            ].some(term => searchText.includes(term));

            return hasTitle || hasSearch;
        });

        const candidates = pickerRoots.flatMap(root => [
            root,
            ...root.querySelectorAll("*")
        ]).filter(element =>
            visible(element) &&
            normalize(element.innerText) === target
        );

        if (!candidates.length) {
            return null;
        }

        candidates.sort((a, b) =>
            a.querySelectorAll("*").length -
            b.querySelectorAll("*").length
        );

        const element = candidates[0];

        // Expand the text node to the matching visual row. The check icon
        // belongs to this row, not necessarily to the text element itself.
        let row = element;
        for (let parent = element.parentElement;
             parent && pickerRoots.some(root => root.contains(parent));
             parent = parent.parentElement) {
            const rect = parent.getBoundingClientRect();
            if (normalize(parent.innerText) !== target) break;
            if (rect.height > 120) break;
            if (rect.width >= 100 && rect.height >= 30) row = parent;
        }

        // Facebook shows a check mark on the currently active profile/Page.
        // Clicking that row does nothing and the picker does not close.
        const checkedSelector = [
            "[aria-selected='true']",
            "[aria-checked='true']",
            "[aria-current='page']",
            "[aria-current='true']",
            "[data-state='checked']",
            "input:checked"
        ].join(",");

        const explicitSelected =
            row.matches(checkedSelector) ||
            Boolean(row.querySelector(checkedSelector));

        const isBlue = value => {
            const m = String(value || "").match(
                /rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i
            );
            if (!m) return false;
            const [r, g, b] = m.slice(1).map(Number);
            return b > 135 && b > r * 1.5 && b > g * 1.15 && g > r * 1.3;
        };

        const rowRect = row.getBoundingClientRect();
        const blueCheckAtRight = [...row.querySelectorAll("svg, path, i, span, div")]
            .some(icon => {
                const rect = icon.getBoundingClientRect();
                if (rect.width < 10 || rect.height < 10 ||
                    rect.width > 34 || rect.height > 34 ||
                    rect.left < rowRect.right - 48) return false;
                const style = getComputedStyle(icon);
                return [
                    style.color, style.fill, style.backgroundColor,
                    icon.getAttribute("fill")
                ].some(isBlue);
            });

        const clickTarget = element.closest(
            "button, [role='button'], [role='menuitem'], " +
            "[role='option'], [role='radio'], a, [tabindex='0']"
        ) || row;

        return {
            element: clickTarget,
            already_selected: explicitSelected || blueCheckAtRight
        };
    """

    selection = driver.execute_script(script, page_name)

    if not selection or selection.get("element") is None:
        raise RuntimeError(f"Could not locate Page '{page_name}' in the Page list.")

    if selection.get("already_selected"):
        # The selected row is intentionally not clickable on Facebook.
        return "already_active"

    target_element = selection["element"]
    try:
        target_element.click()
    except WebDriverException:
        driver.execute_script(
            "arguments[0].click();",
            target_element,
        )

    # ----- Wait for Page picker to close -----
    try:
        WebDriverWait(
            driver,
            ACCOUNT_MENU_TIMEOUT,
        ).until(
            lambda current_driver: not current_driver.execute_script(r"""
                const normalize = value => String(value || "")
                    .normalize("NFD")
                    .replace(/[\u0300-\u036f]/g, "")
                    .replace(/\s+/g, " ")
                    .trim()
                    .toLowerCase();

                const visible = element => {
                    const style = window.getComputedStyle(element);
                    const rect = element.getBoundingClientRect();

                    return rect.width > 0 &&
                        rect.height > 0 &&
                        style.display !== "none" &&
                        style.visibility !== "hidden" &&
                        Number(style.opacity || 1) > 0;
                };

                const selectors = [
                    "[role='menu']",
                    "[role='dialog']",
                    "[role='listbox']",
                    "[aria-modal='true']",
                    "[data-pagelet*='ProfileSwitcher']",
                    "[data-testid*='profile_switcher']"
                ].join(",");

                const markers = [
                    "chon trang ca nhan",
                    "trang trang ca nhan cua ban",
                    "choose a profile",
                    "profiles and pages",
                    "pages and profiles",
                    "your profiles and pages"
                ];

                return Array.from(
                    document.querySelectorAll(selectors)
                ).filter(visible).some(root => {
                    const text = normalize(root.innerText);

                    return markers.some(marker =>
                        text.includes(marker)
                    ) || Boolean(root.querySelector(
                        "input[placeholder*='Search'], " +
                        "input[placeholder*='Tìm kiếm']"
                    ));
                });
            """)
        )
    except TimeoutException as exc:
        raise RuntimeError(
            f"Facebook did not close the Page picker after selecting " f"'{page_name}'."
        ) from exc

    return "switched"


def open_page_link(driver, page_link: str) -> str:
    page_link = (page_link or "").strip()

    if not page_link:
        raise ValueError("Missing Page link.")

    if not page_link.startswith(("http://", "https://")):
        page_link = f"https://{page_link.lstrip('/')}"

    parsed = urlsplit(page_link)
    hostname = (parsed.hostname or "").lower()

    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Invalid Page link protocol.")

    if hostname != "facebook.com" and not hostname.endswith(".facebook.com"):
        raise ValueError(f"Invalid Facebook Page link: {page_link}")

    # ----- Open Page URL -----
    driver.get(page_link)

    # ----- Wait for Page Load -----
    try:
        WebDriverWait(
            driver,
            ACCOUNT_MENU_TIMEOUT,
        ).until(
            lambda current_driver: (
                current_driver.execute_script("return document.readyState")
                in {"interactive", "complete"}
            )
        )

        WebDriverWait(
            driver,
            ACCOUNT_MENU_TIMEOUT,
        ).until(
            lambda current_driver: current_driver.find_elements(
                By.TAG_NAME,
                "body",
            )
        )

    except TimeoutException as exc:
        raise RuntimeError(f"Page did not load: {page_link}") from exc

    current_url = driver.current_url
    current_host = (urlsplit(current_url).hostname or "").lower()

    if current_host != "facebook.com" and not current_host.endswith(".facebook.com"):
        raise RuntimeError(f"Unexpected URL after opening Page: {current_url}")

    return current_url


def switch_facebook_page(driver, page_name: str, page_link: str) -> str:
    try:
        page_name = (page_name or "").strip()
        page_link = (page_link or "").strip()

        if not page_name:
            raise FacebookSwitchError(
                "Missing page_name.",
                retryable=False,
            )

        if not page_link:
            raise FacebookSwitchError(
                "Missing page_link.",
                retryable=False,
            )

        # ----- Open Facebook Home -----
        open_facebook_home(driver)

        # ----- Open Account Menu -----
        if not open_account_menu(driver):
            raise FacebookSwitchError(
                "Could not open Facebook Account Menu.",
                retryable=True,
            )

        # ----- Find Target Page -----
        if not find_page_in_account_menu(driver, page_name):
            raise FacebookSwitchError(
                f"Page not found: {page_name}",
                retryable=False,
            )

        # ----- Select Target Page -----
        selection_result = select_page_in_account_menu(driver, page_name)

        # The picker stays open if the target Page is already selected.
        # Its checked state was verified inside select_page_in_account_menu.
        if selection_result == "switched":
            verify_facebook_page(driver, page_name)
        elif selection_result != "already_active":
            raise FacebookSwitchError(
                f"Could not select Page: {page_name}",
                retryable=True,
            )

        # ----- Open Page Link -----
        return open_page_link(driver, page_link)

    except FacebookSwitchError:
        raise

    except TimeoutException as error:
        raise FacebookSwitchError(
            f"Facebook operation timed out: {error}",
            retryable=True,
        ) from error

    except WebDriverException as error:
        raise FacebookSwitchError(
            f"Facebook WebDriver error: {error}",
            retryable=True,
        ) from error

    except ValueError as error:
        raise FacebookSwitchError(
            str(error),
            retryable=False,
        ) from error

    except RuntimeError as error:
        message = str(error)
        lowered = message.casefold()
        non_retryable = any(
            term in lowered
            for term in (
                "requires login",
                "login is required",
                "checkpoint",
                "missing page",
                "page not found",
                "invalid facebook",
                "invalid url",
                "missing page_name",
                "missing page_link",
                "does not have access",
            )
        )
        raise FacebookSwitchError(
            message,
            retryable=not non_retryable,
        ) from error


# ----- Facebook Post -----
def open_create_post_dialog(driver, timeout: int = 20) -> bool:
    if driver is None:
        raise FacebookPostError(
            "AdsPower WebDriver is not available.",
            retryable=True,
        )

    # ----- Check Active Composer Dialog -----
    check_dialog_script = r"""
        const visible = element => {
            const rect = element.getBoundingClientRect();
            const style = getComputedStyle(element);

            return rect.width > 0 &&
                rect.height > 0 &&
                style.visibility !== "hidden" &&
                style.display !== "none";
        };

        const normalize = value => String(value || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/đ/g, "d")
            .toLowerCase()
            .replace(/\s+/g, " ")
            .trim();

        const dialogs = Array.from(document.querySelectorAll(
            '[role="dialog"], [aria-modal="true"]'
        )).filter(visible);

        for (const dialog of dialogs) {
            const editor = Array.from(dialog.querySelectorAll(
                '[contenteditable="true"], textarea'
            )).find(visible);

            if (!editor) continue;

            const heading = normalize(
                Array.from(dialog.querySelectorAll(
                    '[role="heading"], h1, h2, h3'
                )).map(el => el.innerText).join(" ") + " " +
                (dialog.getAttribute("aria-label") || "")
            );

            const hasPostButton = Array.from(
                dialog.querySelectorAll(
                    'button, [role="button"]'
                )
            ).some(button => {
                if (!visible(button)) return false;

                const label = normalize(
                    button.getAttribute("aria-label") ||
                    button.innerText
                );

                return /^(post|publish|dang|dang bai)$/.test(label);
            });

            if (
                /create post|tao bai viet/.test(heading) ||
                hasPostButton
            ) {
                return true;
            }
        }

        return false;
    """

    # ----- Return If Composer Is Already Open -----
    try:
        if driver.execute_script(check_dialog_script):
            return True
    except WebDriverException as error:
        raise FacebookPostError(
            f"Cannot inspect Facebook composer: {error}",
            retryable=True,
        ) from error

    # ----- Find Create Post Trigger -----
    find_trigger_script = r"""
        const visible = element => {
            const rect = element.getBoundingClientRect();
            const style = getComputedStyle(element);

            return rect.width > 0 &&
                rect.height > 0 &&
                style.display !== "none" &&
                style.visibility !== "hidden";
        };

        const normalize = value => String(value || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/đ/g, "d")
            .toLowerCase()
            .replace(/\s+/g, " ")
            .trim();

        const root = document.querySelector(
            '[role="main"], main'
        ) || document.body;

        const candidates = Array.from(root.querySelectorAll(
            'button, [role="button"], [contenteditable="true"]'
        )).filter(element => (
            visible(element) &&
            !element.closest(
                '[role="dialog"], [aria-modal="true"]'
            )
        ));

        const matches = [];

        for (const element of candidates) {
            const label = normalize([
                element.getAttribute("aria-label"),
                element.getAttribute("title"),
                element.getAttribute("data-placeholder"),
                element.innerText
            ].filter(Boolean).join(" "));

            if (!label || label.length > 180) continue;

            const isComposer = (
                /create post|tao bai viet/.test(label) ||
                /what.s on your mind|ban dang nghi gi/.test(label) ||
                /write something|viet gi do|ban viet gi/.test(label)
            );

            if (!isComposer) continue;

            let score = 0;

            if (/what.s on your mind|ban dang nghi gi/.test(label)) {
                score += 100;
            }

            if (/create post|tao bai viet/.test(label)) {
                score += 50;
            }

            if (label.length < 60) {
                score += 10;
            }

            matches.push({element, score});
        }

        matches.sort((a, b) => b.score - a.score);

        return matches.length ? matches[0].element : null;
    """

    try:
        trigger = WebDriverWait(
            driver,
            timeout,
            poll_frequency=0.5,
        ).until(lambda browser: browser.execute_script(find_trigger_script) or False)

    except TimeoutException as error:
        raise FacebookPostError(
            "Create Post button was not found.",
            retryable=True,
        ) from error

    except WebDriverException as error:
        raise FacebookPostError(
            f"Cannot locate Create Post button: {error}",
            retryable=True,
        ) from error

    # ----- Click Create Post -----
    try:
        trigger.click()

    except WebDriverException as error:
        try:
            if not driver.execute_script(check_dialog_script):
                driver.execute_script(
                    "arguments[0].click();",
                    trigger,
                )
        except WebDriverException as fallback_error:
            raise FacebookPostError(
                f"Cannot click Create Post: {fallback_error}",
                retryable=True,
            ) from error

    # ----- Verify Composer Dialog -----
    try:
        WebDriverWait(
            driver,
            timeout,
            poll_frequency=0.5,
        ).until(lambda browser: browser.execute_script(check_dialog_script))

    except TimeoutException as error:
        raise FacebookPostError(
            "Create Post was clicked, but the dialog did not open.",
            retryable=True,
        ) from error

    except WebDriverException as error:
        raise FacebookPostError(
            f"Cannot verify Create Post dialog: {error}",
            retryable=True,
        ) from error

    return True


def upload_post_media(
    driver,
    row: dict,
    timeout: int = 30,
) -> bool:
    media_value = (
        row.get("_validated_media")
        or row.get("_validated_image")
        or row.get("media")
        or row.get("image")
        or ""
    )

    media_path = Path(str(media_value).strip().strip('"').strip("'")).expanduser()

    # ----- Validate Media File -----
    if not str(media_value).strip() or not media_path.is_file():
        raise FacebookPostError(
            f"Media file does not exist: {media_value}",
            retryable=False,
        )

    media_path = media_path.resolve()

    # ----- Find Facebook File Input -----
    def locate_file_input(browser):
        return browser.execute_script(r"""
            const visible = element => {
                const rect = element.getBoundingClientRect();
                const style = getComputedStyle(element);

                return rect.width > 0 &&
                    rect.height > 0 &&
                    style.display !== "none" &&
                    style.visibility !== "hidden";
            };

            const dialogs = Array.from(
                document.querySelectorAll(
                    '[role="dialog"], [aria-modal="true"]'
                )
            ).filter(visible).reverse();

            const composer = dialogs.find(dialog =>
                dialog.querySelector(
                    '[contenteditable="true"], textarea'
                )
            );

            if (!composer) return null;

            const localInputs = Array.from(
                composer.querySelectorAll('input[type="file"]')
            ).filter(input => !input.disabled);

            if (localInputs.length) {
                return localInputs[localInputs.length - 1];
            }

            const globalInputs = Array.from(
                document.querySelectorAll('input[type="file"]')
            ).filter(input =>
                !input.disabled &&
                /image|video|\.jpg|\.png|\.mp4/i.test(
                    input.accept || ""
                )
            );

            return globalInputs.length === 1
                ? globalInputs[0]
                : null;
        """)

    # ----- Locate File Input -----
    try:
        file_input = WebDriverWait(
            driver,
            8,
            poll_frequency=0.5,
        ).until(lambda browser: locate_file_input(browser) or False)

    except TimeoutException:
        # ----- Reveal Photo/Video Input -----
        photo_button = driver.execute_script(r"""
            const visible = element => {
                const rect = element.getBoundingClientRect();

                return rect.width > 0 && rect.height > 0;
            };

            const dialog = Array.from(
                document.querySelectorAll(
                    '[role="dialog"], [aria-modal="true"]'
                )
            ).reverse().find(element =>
                visible(element) &&
                element.querySelector(
                    '[contenteditable="true"], textarea'
                )
            );

            if (!dialog) return null;

            return Array.from(
                dialog.querySelectorAll(
                    'button, [role="button"]'
                )
            ).find(element => {
                if (!visible(element)) return false;

                const label = [
                    element.getAttribute("aria-label"),
                    element.innerText
                ].filter(Boolean).join(" ").toLowerCase();

                return /photo\s*\/\s*video|photos? and videos?|ảnh\s*\/\s*video|ảnh và video/.test(label);
            }) || null;
        """)

        if photo_button is None:
            raise FacebookPostError(
                "Facebook media input and Photo/Video control were not found.",
                retryable=True,
            )

        try:
            photo_button.click()

            file_input = WebDriverWait(
                driver,
                timeout,
                poll_frequency=0.5,
            ).until(lambda browser: locate_file_input(browser) or False)

        except (TimeoutException, WebDriverException) as error:
            raise FacebookPostError(
                "Facebook did not expose a media file input.",
                retryable=True,
            ) from error

    # ----- Select Media File -----
    try:
        file_input.send_keys(str(media_path))

    except WebDriverException as error:
        raise FacebookPostError(
            f"Cannot select Facebook media: {error}",
            retryable=True,
        ) from error

    # ----- Verify Selected Media -----
    try:
        WebDriverWait(
            driver,
            timeout,
            poll_frequency=0.5,
        ).until(
            lambda browser: browser.execute_script(
                r"""
                const expected = arguments[0].toLowerCase();

                const inputs = Array.from(
                    document.querySelectorAll('input[type="file"]')
                );

                const selected = inputs.some(input =>
                    Array.from(input.files || []).some(
                        file => file.name.toLowerCase() === expected
                    )
                );

                if (selected) return true;

                const dialogs = Array.from(
                    document.querySelectorAll(
                        '[role="dialog"], [aria-modal="true"]'
                    )
                ).filter(dialog => {
                    const rect = dialog.getBoundingClientRect();

                    return rect.width > 0 && rect.height > 0;
                });

                return dialogs.some(dialog =>
                    Boolean(dialog.querySelector(
                        'img[src^="blob:"], video[src^="blob:"], ' +
                        'img[src^="data:"], video[src^="data:"]'
                    ))
                );
            """,
                media_path.name,
            )
        )

    except TimeoutException as error:
        raise FacebookPostError(
            "Facebook did not confirm the selected media.",
            retryable=True,
        ) from error

    return True


def fill_post_caption(
    driver,
    caption: str,
    timeout: int = 20,
) -> bool:
    caption = str(caption or "")

    # ----- Validate Caption -----
    if not caption.strip():
        raise FacebookPostError(
            "Post caption is empty.",
            retryable=False,
        )

    # ----- Find Caption Editor -----
    find_editor_script = r"""
        const visible = element => {
            const rect = element.getBoundingClientRect();
            const style = getComputedStyle(element);

            return rect.width > 0 &&
                rect.height > 0 &&
                style.display !== "none" &&
                style.visibility !== "hidden";
        };

        const normalize = value => String(value || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/đ/g, "d")
            .toLowerCase()
            .replace(/\s+/g, " ")
            .trim();

        const dialogs = Array.from(
            document.querySelectorAll(
                '[role="dialog"], [aria-modal="true"]'
            )
        ).filter(visible).reverse();

        for (const dialog of dialogs) {
            const editors = Array.from(
                dialog.querySelectorAll(
                    '[contenteditable="true"], textarea'
                )
            ).filter(visible);

            if (!editors.length) continue;

            const preferred = editors.find(editor => {
                const label = normalize([
                    editor.getAttribute("aria-label"),
                    editor.getAttribute("aria-placeholder"),
                    editor.getAttribute("data-placeholder"),
                    editor.getAttribute("placeholder")
                ].filter(Boolean).join(" "));

                return /what.s on your mind|ban dang nghi gi|write something|viet gi/.test(label);
            });

            return preferred || editors[0];
        }

        return null;
    """

    try:
        editor = WebDriverWait(
            driver,
            timeout,
            poll_frequency=0.5,
        ).until(lambda browser: browser.execute_script(find_editor_script) or False)

    except TimeoutException as error:
        raise FacebookPostError(
            "Caption editor was not found.",
            retryable=True,
        ) from error

    # ----- Normalize Caption Text -----
    def normalize(value):
        return " ".join(str(value or "").replace("\u200b", "").split())

    # ----- Read Editor Content -----
    def read_editor():
        return (
            driver.execute_script(
                """
            const editor = arguments[0];

            return editor.tagName === "TEXTAREA"
                ? editor.value
                : editor.innerText;
            """,
                editor,
            )
            or ""
        )

    expected = normalize(caption)

    try:
        # ----- Avoid Duplicate Caption -----
        if normalize(read_editor()) == expected:
            return True

        # ----- Clear Existing Caption -----
        editor.click()
        editor.send_keys(Keys.CONTROL, "a")
        editor.send_keys(Keys.BACKSPACE)

        WebDriverWait(
            driver,
            5,
            poll_frequency=0.2,
        ).until(lambda browser: not normalize(read_editor()))

        # ----- Input Unicode Caption -----
        try:
            driver.execute_cdp_cmd(
                "Input.insertText",
                {"text": caption},
            )

        except (AttributeError, WebDriverException):
            editor.send_keys(caption)

        # ----- Verify Caption -----
        WebDriverWait(
            driver,
            timeout,
            poll_frequency=0.5,
        ).until(lambda browser: (normalize(read_editor()) == expected))

    except (TimeoutException, WebDriverException) as error:
        raise FacebookPostError(
            f"Cannot fill or verify Facebook caption: {error}",
            retryable=True,
        ) from error

    return True


# ----- Shared Facebook Composer Action Detection -----
def _inspect_post_composer_action(driver, allow_global_post: bool = False) -> dict:
    """Inspect the visible composer actions without clicking anything."""
    script = r"""
        const allowGlobalPost = Boolean(arguments[0]);
        const normalize = value => String(value || '')
            .toLowerCase()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .replace(/đ/g, 'd')
            .replace(/\u200b/g, '')
            .replace(/\s+/g, ' ')
            .trim();

        const visible = element => {
            if (!element || !element.isConnected) return false;
            const rect = element.getBoundingClientRect();
            if (rect.width <= 0 || rect.height <= 0) return false;
            for (let node = element; node; node = node.parentElement) {
                const style = getComputedStyle(node);
                if (style.display === 'none' ||
                    style.visibility === 'hidden' ||
                    Number(style.opacity || 1) <= 0.01 ||
                    node.getAttribute('aria-hidden') === 'true' ||
                    node.hasAttribute('inert')) return false;
            }
            return true;
        };

        const enabled = element =>
            !element.disabled &&
            element.getAttribute('aria-disabled') !== 'true' &&
            getComputedStyle(element).pointerEvents !== 'none';

        const labels = element => [
            element.getAttribute('aria-label'),
            element.getAttribute('title'),
            element.getAttribute('value'),
            element.innerText,
            element.textContent
        ].map(normalize).filter(Boolean);

        const nextPattern = /^(next|continue|proceed|tiep|tiep theo|tiep tuc)$/;
        const postPattern = /^(post|post now|publish|publish now|publish post|share post|share now|dang|dang bai|dang bai viet|dang ngay|chia se bai viet)$/;

        const isNext = element => labels(element).some(label =>
            nextPattern.test(label));
        const isPost = element => labels(element).some(label =>
            postPattern.test(label));

        const controlSelector =
            'button, [role="button"], input[type="submit"], [tabindex="0"]';
        const controls = [...document.querySelectorAll(controlSelector)]
            .filter(element => visible(element) &&
                !element.matches('[contenteditable="true"]') &&
                (isNext(element) || isPost(element)))
            .map(element => element.closest(
                'button, [role="button"], input[type="submit"]'
            ) || element);
        const unique = [...new Set(controls)].filter(element =>
            !controls.some(other => other !== element &&
                other.contains(element) &&
                isNext(other) === isNext(element) &&
                isPost(other) === isPost(element))
        );

        const rootSelector = [
            '[role="dialog"]', '[aria-modal="true"]',
            '[data-pagelet*="Composer" i]',
            '[data-testid*="composer" i]',
            '[data-pagelet*="Video" i]',
            '[data-testid*="video_editor" i]',
            '[data-testid*="reel" i]'
        ].join(',');

        const roots = [...document.querySelectorAll(rootSelector)]
            .filter(visible).reverse();
        const relevantRoots = roots.filter(root => unique.some(
            control => root.contains(control)
        ));

        const summarize = actions => actions.map(action => ({
            label: labels(action)[0] || '',
            enabled: enabled(action)
        }));

        const result = (state, button, mode, actions) => ({
            state,
            button: button || null,
            mode,
            signature: JSON.stringify({
                mode,
                actions: summarize(actions),
                heading: roots.filter(root => root.contains(button))
                    .map(root => normalize((root.innerText || '').slice(0, 300)))
                    .slice(0, 2)
            }),
            debug: JSON.stringify({
                mode,
                scopedRoots: relevantRoots.length,
                next: summarize(actions.filter(isNext)),
                post: summarize(actions.filter(isPost))
            })
        });

        let actions = [];
        let mode = 'none';
        if (relevantRoots.length) {
            // The last visible dialog/composer wins over background controls.
            const preferred = relevantRoots[0];
            actions = unique.filter(control => preferred.contains(control));
            mode = 'composer';
        } else if (allowGlobalPost) {
            // A Facebook video wizard can move the Post button outside a dialog.
            // Only accept a single visible Post action, never guess among many.
            const globalPosts = unique.filter(isPost);
            const globalNext = unique.filter(isNext);
            if (globalPosts.length === 1 && globalNext.length === 0) {
                actions = globalPosts;
                mode = 'unique-post-after-next';
            } else {
                return result(
                    globalPosts.length > 1 ? 'ambiguous' : 'missing',
                    null, 'global-rejected', unique
                );
            }
        } else {
            return result('missing', null, 'not-found', unique);
        }

        const next = actions.filter(isNext);
        const post = actions.filter(isPost);
        if (next.length) {
            const available = next.filter(enabled);
            return result(
                available.length === 1 ? 'next' :
                    available.length > 1 ? 'ambiguous' : 'waiting',
                available.length === 1 ? available[0] : null,
                mode, actions
            );
        }

        if (post.length) {
            const available = post.filter(enabled);
            return result(
                available.length === 1 ? 'ready' :
                    available.length > 1 ? 'ambiguous' : 'waiting',
                available.length === 1 ? available[0] : null,
                mode, actions
            );
        }
        return result('missing', null, mode, actions);
    """
    try:
        state = driver.execute_script(script, allow_global_post)
    except WebDriverException as error:
        raise FacebookPostError(
            f"Cannot inspect Facebook composer buttons: {error}",
            retryable=True,
        ) from error
    return (
        state
        if isinstance(state, dict)
        else {
            "state": "missing",
            "button": None,
            "signature": "",
            "debug": "DOM inspection returned no result",
        }
    )


# ----- Dismiss Optional Facebook Call Now Prompt -----
def dismiss_call_now_popup(
    driver,
    timeout: int = 7,
    appearance_timeout: float = 0,
) -> bool:
    """Dismiss the specific Call Now CTA popup using Later, or its Close button."""
    inspect_script = r"""
        const normalize = value => String(value || '')
            .toLowerCase()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .replace(/đ/g, 'd')
            .replace(/[“”"]/g, '')
            .replace(/\s+/g, ' ')
            .trim();

        const visible = element => {
            if (!element || !element.isConnected) return false;
            const rect = element.getBoundingClientRect();
            if (rect.width <= 0 || rect.height <= 0) return false;
            for (let node = element; node; node = node.parentElement) {
                const style = getComputedStyle(node);
                if (style.display === 'none' ||
                    style.visibility === 'hidden' ||
                    Number(style.opacity || 1) <= 0.01 ||
                    node.getAttribute('aria-hidden') === 'true' ||
                    node.hasAttribute('inert')) return false;
            }
            return true;
        };

        const titles = new Set([
            'tro chuyen truc tiep voi moi nguoi',
            'speak with people directly',
            'chat with people directly'
        ]);
        const laterLabels = new Set(['luc khac', 'not now', 'maybe later']);
        const addLabels = new Set(['them nut', 'add button']);
        const closeLabels = new Set([
            'dong', 'close', 'close dialog', 'close popup', 'dismiss'
        ]);
        const controlSelector = 'button, [role="button"], [tabindex="0"], a';

        const labelsOf = element => [
            element.getAttribute('aria-label'),
            element.getAttribute('title'),
            element.innerText,
            element.textContent
        ].map(normalize).filter(Boolean);

        const isNamed = (element, expected) =>
            labelsOf(element).some(value => expected.has(value));

        const enabled = element =>
            !element.disabled &&
            element.getAttribute('aria-disabled') !== 'true';

        const controlsIn = root => [...root.querySelectorAll(controlSelector)]
            .filter(element => visible(element) && enabled(element));

        const findNamed = (root, names) => {
            // Prefer an actual clickable control over a decorative text node.
            const matchingControls = controlsIn(root)
                .filter(element => isNamed(element, names))
                .sort((a, b) =>
                    a.querySelectorAll('*').length - b.querySelectorAll('*').length
                );
            if (matchingControls.length) return matchingControls[0];

            // Facebook sometimes renders text in a non-semantic clickable div.
            const texts = [...root.querySelectorAll('span, div, a')]
                .filter(visible)
                .filter(element => names.has(normalize(element.innerText)))
                .sort((a, b) =>
                    a.querySelectorAll('*').length - b.querySelectorAll('*').length
                );
            return texts[0] || null;
        };

        const isTitle = element => {
            const text = normalize(element.innerText);
            return titles.has(text);
        };

        const titleNodes = [...document.querySelectorAll(
            'h1, h2, h3, [role="heading"], span, div'
        )].filter(visible).filter(isTitle);

        const potentialRoots = [];
        // Search from the exact title toward its own popup, not from page body.
        for (const title of titleNodes) {
            for (let root = title.parentElement, depth = 0;
                 root && depth < 12;
                 root = root.parentElement, depth++) {
                if (!visible(root)) break;
                const text = normalize(root.innerText);
                if (text.length > 2400) break;
                const later = findNamed(root, laterLabels);
                const add = findNamed(root, addLabels);
                const close = findNamed(root, closeLabels);
                if (later || (add && close)) {
                    potentialRoots.push({root, later, close});
                }
            }
        }

        // Some variants label the whole dialog but not its title element.
        for (const root of document.querySelectorAll(
            '[role="dialog"], [aria-modal="true"]'
        )) {
            if (!visible(root)) continue;
            const text = normalize(root.innerText);
            if (text.length > 2400 ||
                ![...titles].some(title => text.includes(title))) continue;
            const later = findNamed(root, laterLabels);
            const add = findNamed(root, addLabels);
            const close = findNamed(root, closeLabels);
            if (later || (add && close)) {
                potentialRoots.push({root, later, close});
            }
        }

        if (!potentialRoots.length) {
            return {visible: false, button: null, action: ''};
        }

        // The smallest containing popup avoids toolbar/background controls.
        potentialRoots.sort((a, b) => {
            const ar = a.root.getBoundingClientRect();
            const br = b.root.getBoundingClientRect();
            return ar.width * ar.height - br.width * br.height;
        });
        const match = potentialRoots[0];
        const button = match.later || match.close;
        return {
            visible: true,
            button: button || null,
            action: match.later ? 'later' : 'close'
        };
    """

    def inspect():
        result = driver.execute_script(inspect_script)
        return result if isinstance(result, dict) else {"visible": False}

    try:
        if appearance_timeout > 0:
            try:
                state = WebDriverWait(
                    driver, appearance_timeout, poll_frequency=0.25
                ).until(
                    lambda _: (lambda s: s if s.get("visible") else False)(inspect())
                )
            except TimeoutException:
                return False
        else:
            state = inspect()
            if not state.get("visible"):
                return False

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not state.get("visible"):
                return True

            button = state.get("button")
            if button is None:
                time.sleep(0.25)
                state = inspect()
                continue

            try:
                button.click()
            except WebDriverException:
                # Locate again: the original element may have been replaced.
                state = inspect()
                if not state.get("visible"):
                    return True
                button = state.get("button")
                if button is None:
                    time.sleep(0.25)
                    continue
                driver.execute_script("arguments[0].click();", button)

            try:
                WebDriverWait(driver, 2, poll_frequency=0.25).until(
                    lambda _: not inspect().get("visible")
                )
                return True
            except TimeoutException:
                state = inspect()

        raise FacebookPostError(
            "Facebook Call Now popup is visible, but Later/Close "
            "did not dismiss it.",
            retryable=True,
        )

    except WebDriverException as error:
        raise FacebookPostError(
            f"Cannot dismiss Facebook Call Now popup: {error}",
            retryable=True,
        ) from error


# ----- Advance Facebook Composer to Publish -----
def advance_post_composer(
    driver,
    timeout: int = 150,
    max_next_steps: int = 3,
) -> bool:
    """Click Next as required, then confirm Post exists without clicking it."""
    if driver is None:
        raise FacebookPostError("AdsPower WebDriver is not available.", retryable=True)
    if timeout <= 0 or max_next_steps < 0:
        raise FacebookPostError("Invalid composer limits.", retryable=False)

    deadline = time.monotonic() + timeout
    next_count = 0
    prior_button = None
    prior_signature = ""
    transition_deadline = 0.0
    last_state = {"state": "missing", "debug": ""}

    while time.monotonic() < deadline:
        # ----- Dismiss Optional Live-Chat CTA Before Inspecting Post -----
        if dismiss_call_now_popup(driver):
            continue

        # Global lookup is enabled only after a successful Next click.
        state = _inspect_post_composer_action(driver, allow_global_post=next_count > 0)
        last_state = state
        kind = state.get("state")

        if kind == "ready":
            return True

        if prior_button is not None:
            # Never click Next twice until the previous step has transitioned.
            different_step = (
                kind == "next"
                and state.get("button") is not None
                and (
                    state["button"] != prior_button
                    or state.get("signature") != prior_signature
                )
            )
            if different_step:
                prior_button = None
            elif time.monotonic() >= transition_deadline:
                raise FacebookPostError(
                    f"Next was clicked but no new composer step appeared. "
                    f"Details: {state.get('debug', '')}",
                    retryable=True,
                )
            else:
                time.sleep(0.5)
                continue

        if kind == "next":
            if next_count >= max_next_steps:
                raise FacebookPostError(
                    f"Composer still displays Next after {next_count} clicks. "
                    f"Details: {state.get('debug', '')}",
                    retryable=True,
                )
            button = state.get("button")
            if button is None:
                time.sleep(0.5)
                continue
            try:
                button.click()
            except WebDriverException as error:
                raise FacebookPostError(
                    f"Cannot click Facebook Next: {error}", retryable=True
                ) from error
            next_count += 1
            prior_button = button
            prior_signature = state.get("signature") or ""
            transition_deadline = min(deadline, time.monotonic() + 25)
            time.sleep(0.7)
            continue

        time.sleep(0.5)

    raise FacebookPostError(
        f"Post button not found after {next_count} Next click(s). "
        f"Last state: {last_state.get('state')}; "
        f"details: {last_state.get('debug', '')}",
        retryable=True,
    )


# ----- Submit Facebook Post Exactly Once -----
def submit_facebook_post(
    driver,
    on_before_submit,
    timeout: int = 30,
) -> str:
    """Click Publish once and dismiss a possible post-click Call Now popup."""
    if driver is None:
        raise FacebookPostError("AdsPower WebDriver is not available.", retryable=True)
    if not callable(on_before_submit):
        raise FacebookPostError(
            "Publish requires a durable before-submit callback.",
            retryable=False,
        )

    last_state = {"state": "missing", "debug": ""}

    def locate(browser):
        nonlocal last_state
        dismiss_call_now_popup(browser)
        last_state = _inspect_post_composer_action(browser, allow_global_post=True)
        if last_state.get("state") == "ready":
            return last_state.get("button") or False
        return False

    try:
        publish_button = WebDriverWait(driver, timeout, poll_frequency=0.5).until(
            locate
        )
    except TimeoutException as error:
        raise FacebookPostError(
            "No safe Publish button was found. "
            f"Last state: {last_state.get('state')}; "
            f"details: {last_state.get('debug', '')}",
            retryable=True,
        ) from error

    try:
        if not publish_button.is_displayed() or not publish_button.is_enabled():
            raise FacebookPostError(
                "Publish button disappeared before submission.", retryable=True
            )
    except WebDriverException as error:
        raise FacebookPostError(
            f"Publish button became stale before submission: {error}",
            retryable=True,
        ) from error

    # ----- Recheck the Optional Popup Before Publishing -----
    if dismiss_call_now_popup(driver):
        refreshed = _inspect_post_composer_action(driver, allow_global_post=True)
        if refreshed.get("state") != "ready" or refreshed.get("button") is None:
            raise FacebookPostError(
                "Publish button was not ready after closing the Call Now popup.",
                retryable=True,
            )
        publish_button = refreshed["button"]

    # ----- Persist Publishing Before the Irreversible Click -----
    on_before_submit()

    try:
        publish_button.click()
    except Exception as error:
        raise PublishUnknownError(
            f"Publish click outcome is uncertain; do not resubmit: {error}"
        ) from error

    # ----- Handle a Call Now Popup Appearing After Publish Click -----
    # The old project handled this popup after the Post click. Never click
    # Publish again, even if dismissing the optional popup fails.
    try:
        dismiss_call_now_popup(driver, timeout=7, appearance_timeout=5)
    except Exception as error:
        raise PublishUnknownError(
            "Publish was clicked, but the Call Now popup could not be "
            f"dismissed safely. Verify the post; do not resubmit: {error}"
        ) from error

    return "Running"


def run_facebook_post(
    driver,
    row: dict,
    on_before_submit=None,
) -> str:
    """Prepare a Facebook Post and submit it once."""

    if driver is None:
        raise FacebookPostError(
            "AdsPower WebDriver is not available.",
            retryable=True,
        )

    if not callable(on_before_submit):
        raise FacebookPostError(
            "Missing the durable Publish callback.",
            retryable=False,
        )

    page_link = str(row.get("page_link") or "").strip()

    if not page_link:
        raise FacebookPostError(
            "Facebook Page URL is missing.",
            retryable=False,
        )

    # ----- Reset Composer Before Each Safe Retry -----
    try:
        open_page_link(driver, page_link)

    except ValueError as error:
        raise FacebookPostError(
            str(error),
            retryable=False,
        ) from error

    except (RuntimeError, WebDriverException) as error:
        raise FacebookPostError(
            str(error),
            retryable=True,
        ) from error

    try:
        # ----- Step 1: Open Create Post -----
        if not open_create_post_dialog(driver):
            raise FacebookPostError(
                "Create Post did not open.",
                retryable=True,
            )

        # ----- Step 2: Upload Media -----
        if not upload_post_media(driver, row):
            raise FacebookPostError(
                "Media was not selected.",
                retryable=True,
            )

        # ----- Step 3: Fill Caption -----
        if not fill_post_caption(
            driver,
            row.get("caption", ""),
        ):
            raise FacebookPostError(
                "Caption was not verified.",
                retryable=True,
            )

        # ----- Step 4: Advance Through Next -----
        if not advance_post_composer(driver):
            raise FacebookPostError(
                "Publish screen is not ready.",
                retryable=True,
            )

    except FacebookSwitchError as error:
        raise FacebookPostError(
            str(error),
            retryable=error.retryable,
        ) from error

    except WebDriverException as error:
        raise FacebookPostError(
            f"Facebook preparation failed: {error}",
            retryable=True,
        ) from error

    # ----- Step 5: Publish Once -----
    return submit_facebook_post(
        driver,
        on_before_submit=on_before_submit,
    )


# ----- Normalize Facebook Post URL -----
def _normalize_facebook_post_url(value: str) -> str:
    from urllib.parse import parse_qs
    import re

    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
        host = (parsed.hostname or "").lower()
    except ValueError:
        return ""
    if host != "facebook.com" and not host.endswith(".facebook.com"):
        return ""
    path = parsed.path.rstrip("/")
    if re.fullmatch(
        r"/(?:[^/]+/)?(?:posts|videos|reel|permalink)/[A-Za-z0-9_-]+", path, re.I
    ):
        return "https://www.facebook.com" + path
    if path.lower() in {"/story.php", "/permalink.php"}:
        params = parse_qs(parsed.query)
        story_id = (params.get("story_fbid") or [""])[0]
        page_id = (params.get("id") or [""])[0]
        if re.fullmatch(r"[A-Za-z0-9_-]+", story_id):
            return (
                "https://www.facebook.com/story.php?story_fbid="
                + story_id
                + ("&id=" + page_id if page_id.isdigit() else "")
            )
    return ""


# ----- Capture Published Facebook Post URL -----
def capture_published_post_url(
    driver,
    row: dict,
    timeout: int = 180,
    published_after: float | None = None,
    should_stop=None,
) -> str:
    """Wait 30s, reopen the Page, find the new post and click its time link."""
    if driver is None:
        raise PublishUnknownError("Cannot capture a post URL without a browser.")

    page_link = str(row.get("page_link") or "").strip()
    caption = str(row.get("caption") or "").strip()
    if not page_link or not caption:
        raise PublishUnknownError("Page link and caption are required for URL capture.")

    def check_stop():
        if callable(should_stop) and should_stop():
            raise PublishUnknownError(
                "URL verification was stopped after Publish; do not repost."
            )

    # ----- Allow Facebook to Finish Publishing Before Reload -----
    if published_after is not None:
        wait_until = float(published_after) + 30
        while time.time() < wait_until:
            check_stop()
            time.sleep(min(0.25, max(0, wait_until - time.time())))

    # ----- Do Not Reload While Composer Is Still Open -----
    composer_script = r"""
        const visible = el => {
            if (!el) return false;
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return r.width > 0 && r.height > 0 &&
                s.display !== 'none' && s.visibility !== 'hidden';
        };
        const norm = s => String(s || '').toLowerCase().normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd');
        return [...document.querySelectorAll('[role="dialog"], [aria-modal="true"]')]
            .filter(visible).some(dialog => {
                const title = norm((dialog.getAttribute('aria-label') || '') + ' ' +
                    [...dialog.querySelectorAll('h1,h2,h3,[role="heading"]')]
                        .map(el => el.innerText).join(' '));
                return /create post|tao bai viet|edit video|chinh sua video|post settings|reel settings/.test(title) ||
                    Boolean(dialog.querySelector('[contenteditable="true"]'));
            });
    """
    settle_deadline = time.monotonic() + 60
    clear_since = None
    try:
        while time.monotonic() < settle_deadline:
            check_stop()
            if driver.execute_script(composer_script):
                clear_since = None
            elif clear_since is None:
                clear_since = time.monotonic()
            elif time.monotonic() - clear_since >= 2:
                break
            time.sleep(0.5)
        else:
            raise PublishUnknownError(
                "Facebook composer is still open; do not reload or republish."
            )
    except PublishUnknownError:
        raise
    except WebDriverException as error:
        raise PublishUnknownError(
            f"Cannot inspect the Facebook composer: {error}"
        ) from error

    # ----- Find Caption, Bounded Feed Card and Timestamp -----
    inspect_script = r"""
        const caption = String(arguments[0] || '');
        const postedAfter = Number(arguments[1] || 0) * 1000;
        const norm = value => String(value || '').normalize('NFKC')
            .toLowerCase().replace(/[\u200b-\u200f\ufeff]/g, '')
            .replace(/[^\p{L}\p{N}\s]/gu, ' ').replace(/\s+/g, ' ').trim();
        const unaccent = value => norm(value).normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd');
        const words = norm(caption).split(' ').filter(Boolean);
        const prefix5 = words.slice(0, 5).join(' ');
        const prefix3 = words.slice(0, 3).join(' ');
        const prefix2 = words.slice(0, 2).join(' ');
        if (!prefix2) return {state:'missing', reason:'empty caption'};

        const visible = el => {
            if (!el || !el.isConnected) return false;
            const rect = el.getBoundingClientRect();
            if (rect.width <= 0 || rect.height <= 0) return false;
            for (let p = el; p; p = p.parentElement) {
                const style = getComputedStyle(p);
                if (style.display === 'none' || style.visibility === 'hidden' ||
                    p.getAttribute('aria-hidden') === 'true') return false;
            }
            return true;
        };
        const isPostUrl = value => {
            try {
                const url = new URL(value, location.href);
                return /(^|\.)facebook\.com$/i.test(url.hostname) &&
                    (/\/(posts|reel|videos|permalink)\/[\w-]+\/?$/i.test(url.pathname) ||
                     (/\/(story|permalink)\.php$/i.test(url.pathname) &&
                      url.searchParams.has('story_fbid')));
            } catch { return false; }
        };
        const main = document.querySelector('[role="main"], main') || document.body;
        const isCaption = el => {
            if (!visible(el) || el.closest('[contenteditable="true"]')) return false;
            if (el.closest('[role="dialog"], [aria-modal="true"]')) return false;
            const raw = String(el.innerText || '').trim();
            if (raw.length < prefix2.length || raw.length > 2500) return false;
            const text = norm(raw);
            // Facebook can truncate a caption or wrap the first words in spans.
            if (prefix5 && text.includes(prefix5)) return true;
            if (prefix3 && text.startsWith(prefix3)) return true;
            return prefix2.length >= 10 && text.startsWith(prefix2);
        };
        const leaves = selector => {
            const nodes = [...main.querySelectorAll(selector)].filter(isCaption);
            return nodes.filter(el => !nodes.some(other =>
                other !== el && el.contains(other)));
        };
        let captionNodes = leaves(
            '[data-ad-preview="message"], [data-ad-comet-preview="message"], ' +
            '[dir="auto"], p, span'
        );
        if (!captionNodes.length) captionNodes = leaves('div');
        if (!captionNodes.length) return {
            state:'missing', reason:'caption not visible in feed', captions:0, cards:0
        };

        const cardSelector = '[role="article"], [data-pagelet*="FeedUnit"], ' +
            '[data-testid*="feed_story" i]';
        const linkSelector = 'a[href], [role="link"], [role="button"]';
        const actionSelector = 'button, [role="button"]';
        const hasActions = node => [...node.querySelectorAll(actionSelector)]
            .some(el => /^(like|comment|share|thich|binh luan|chia se)$/i.test(
                unaccent(el.getAttribute('aria-label') || el.innerText || '')));
        const timePattern = /(?:^|\s)(?:vua xong|vua moi|just now|now|hom nay|today|hom qua|yesterday|\d+\s*(?:giay|phut|gio|ngay|tuan|thang|nam|s|m|min|h|hr|hours?|minutes?|days?|weeks?|months?|years?))(?:\s|$)/i;
        const isTime = el => {
            const label = unaccent([
                el.getAttribute('aria-label'), el.getAttribute('title'),
                el.innerText
            ].filter(Boolean).join(' '));
            return timePattern.test(label) ||
                Boolean(el.querySelector('time, abbr[data-utime], [data-utime]'));
        };
        const findCard = leaf => {
            let best = null;
            for (let p = leaf.parentElement, depth = 0;
                 p && p !== main && depth < 22; p = p.parentElement, depth++) {
                if (!visible(p)) continue;
                const rect = p.getBoundingClientRect();
                const text = String(p.innerText || '');
                if (rect.height > 5000 || text.length > 18000) break;
                const links = [...p.querySelectorAll(linkSelector)].filter(visible);
                const timestamp = links.some(isTime) ||
                    Boolean(p.querySelector('time, abbr[data-utime]'));
                const directLink = links.some(a => isPostUrl(
                    a.getAttribute('href') || a.href || ''));
                const article = p.matches(cardSelector);
                if ((timestamp || directLink) && (hasActions(p) || article || links.length >= 2)) {
                    best = p;
                    break;
                }
                if (article && links.length) { best = p; break; }
            }
            return best;
        };
        const cards = [...new Set(captionNodes.map(findCard).filter(Boolean))];
        const unique = cards.filter(card => !cards.some(other =>
            other !== card && card.contains(other)));
        if (!unique.length) return {
            state:'missing', reason:'caption matched but no bounded post card',
            captions:captionNodes.length, cards:0
        };

        // Timestamp filtering is limited to the post header. Other times in a
        // card (e.g. comments) must not eliminate a new post incorrectly.
        const headerTimes = card => {
            const top = card.getBoundingClientRect().top;
            return [...card.querySelectorAll('time[datetime], abbr[data-utime], [data-utime]')]
                .filter(el => visible(el) &&
                    el.getBoundingClientRect().top - top >= -5 &&
                    el.getBoundingClientRect().top - top <= 240)
                .map(el => el.hasAttribute('data-utime')
                    ? Number(el.getAttribute('data-utime')) * 1000
                    : Date.parse(el.getAttribute('datetime') || ''))
                .filter(t => Number.isFinite(t) && t > 946684800000);
        };
        const recent = unique.filter(card => {
            if (!postedAfter) return true;
            const times = headerTimes(card);
            // Use a generous window for server delays and local clock drift.
            return !times.length || Math.max(...times) >= postedAfter - 900000;
        });
        if (!recent.length) return {
            state:'stale', reason:'matching cards have older post-header timestamps',
            captions:captionNodes.length, cards:unique.length
        };
        if (recent.length !== 1) return {
            state:'ambiguous', reason:'multiple posts match caption (' + recent.length + ')',
            captions:captionNodes.length, cards:recent.length
        };
        const card = recent[0];
        const top = card.getBoundingClientRect().top;
        const links = [...card.querySelectorAll(linkSelector)]
            .filter(visible).filter(el => {
                const dy = el.getBoundingClientRect().top - top;
                return dy >= -10 && dy < 420 &&
                    !el.querySelector('img, svg image');
            });
        const score = el => {
            const href = el.getAttribute('href') || el.href || '';
            const stamp = Boolean(el.querySelector('time, abbr[data-utime], [data-utime]'));
            const timeLabel = isTime(el);
            const permalink = isPostUrl(href);
            const dy = el.getBoundingClientRect().top - top;
            // Prefer the author/date timestamp; permalink anchors are fallback.
            return (stamp ? 150 : 0) + (timeLabel ? 100 : 0) +
                (permalink ? 70 : 0) + (dy < 230 ? 15 : 0);
        };
        const candidates = links.map(el => ({
            el, score:score(el),
            href:el.getAttribute('href') || el.href || '',
            time:isTime(el)
        })).filter(a => a.time || isPostUrl(a.href));
        candidates.sort((a,b) => b.score - a.score);
        if (!candidates.length) return {
            state:'matched_no_time', reason:'post visible, but no time/permalink control',
            captions:captionNodes.length, cards:recent.length
        };
        if (candidates.length > 1 &&
            candidates[0].score === candidates[1].score &&
            candidates[0].href && candidates[1].href &&
            candidates[0].href !== candidates[1].href) return {
            state:'ambiguous', reason:'two different time links in matching post'
        };
        return {
            state:'timestamp', button:candidates[0].el,
            href:candidates[0].href,
            reason:'timestamp found', captions:captionNodes.length, cards:1
        };
    """

    scroll_script = r"""
        const roots = [...document.querySelectorAll('[role="feed"], [role="main"], main, div')];
        const scrolling = roots.filter(el => {
            const s = getComputedStyle(el);
            return el.scrollHeight > el.clientHeight + 100 &&
                ['auto', 'scroll'].includes(s.overflowY);
        }).sort((a,b) => b.clientHeight - a.clientHeight);
        if (scrolling.length) scrolling[0].scrollTop += 600;
        else window.scrollBy(0, 600);
    """

    deadline = time.monotonic() + max(1, timeout)
    last_reason = "no matching post yet"
    last_details = ""
    try:
        for cycle in range(3):
            check_stop()
            open_page_link(driver, page_link)
            time.sleep(1)
            for index in range(8):
                check_stop()
                if time.monotonic() >= deadline:
                    break
                result = driver.execute_script(
                    inspect_script, caption, published_after or 0
                )
                if not isinstance(result, dict):
                    result = {"state": "missing", "reason": "DOM returned no result"}
                state = str(result.get("state") or "missing")
                last_reason = str(result.get("reason") or state)
                last_details = (
                    f"captions={result.get('captions', '?')}, "
                    f"cards={result.get('cards', '?')}, "
                    f"reload={cycle + 1}/3, scan={index + 1}/8"
                )
                if state == "timestamp" and result.get("button") is not None:
                    button = result["button"]
                    href = _normalize_facebook_post_url(result.get("href") or "")
                    before_url = driver.current_url
                    previous_handles = set(driver.window_handles)
                    try:

                        driver.execute_script(
                            "arguments[0].scrollIntoView({block:'center'});", button
                        )
                        ActionChains(driver).move_to_element(button).perform()
                        href = (
                            _normalize_facebook_post_url(
                                button.get_attribute("href") or ""
                            )
                            or href
                        )
                        button.click()
                    except WebDriverException as error:
                        last_reason = f"could not click timestamp: {error}"
                        break
                    # ----- Verify Navigation or Canonical Timestamp Href -----
                    click_deadline = min(deadline, time.monotonic() + 12)
                    while time.monotonic() < click_deadline:
                        check_stop()
                        new_handles = set(driver.window_handles) - previous_handles
                        if new_handles:
                            driver.switch_to.window(next(iter(new_handles)))
                        opened_url = _normalize_facebook_post_url(driver.current_url)
                        if opened_url:
                            return opened_url
                        if driver.current_url != before_url:
                            break
                        time.sleep(0.4)
                    if href:
                        return href
                    last_reason = "timestamp was clicked but no permalink was returned"
                    break
                if state == "ambiguous":
                    raise PublishUnknownError(
                        f"Cannot choose a post time link safely: {last_reason}. "
                        "Do not publish again."
                    )
                if index < 7:
                    driver.execute_script(scroll_script)
                    time.sleep(1)
            if time.monotonic() >= deadline:
                break
            time.sleep(2)
    except PublishUnknownError:
        raise
    except (WebDriverException, RuntimeError, ValueError) as error:
        raise PublishUnknownError(f"Cannot capture post URL: {error}") from error

    raise PublishUnknownError(
        "Post URL could not be confirmed after reloading the Page feed. "
        f"Last reason: {last_reason}; {last_details}. Do not publish again."
    )


# ----- Open a Verified Published Post URL -----
def open_published_post_url(driver, post_url: str, timeout: int = 30) -> str:
    """Open the captured permalink and verify the browser is on that post."""
    expected = _normalize_facebook_post_url(post_url)
    if driver is None or not expected:
        raise FacebookPostError(
            "A valid published post URL and browser are required.",
            retryable=False,
        )

    try:
        # ----- Avoid Reloading When the Timestamp Already Opened the Post -----
        current = _normalize_facebook_post_url(driver.current_url)
        if current != expected:
            try:
                driver.get(expected)
            except TimeoutException:
                # Navigation may have succeeded even if full page loading timed out.
                pass

        def post_page_ready(browser):
            if _normalize_facebook_post_url(browser.current_url) != expected:
                return False
            return browser.execute_script("return document.readyState") in {
                "interactive",
                "complete",
            }

        WebDriverWait(driver, timeout, poll_frequency=0.5).until(post_page_ready)

    except TimeoutException as error:
        raise FacebookPostError(
            "The published post URL was captured, but the browser did not "
            "reach that post page.",
            retryable=False,
        ) from error
    except WebDriverException as error:
        raise FacebookPostError(
            f"Cannot open the published Facebook post: {error}",
            retryable=False,
        ) from error

    return expected


# ----- Inspect a Rendered Published Comment Using DOM -----
def _published_comment_snapshot(driver, comment: str) -> dict:
    """Count matching displayed comment bodies, not editor drafts.

    Facebook may split a comment across spans, links and emoji elements.
    The fallback searches bounded comment containers instead of requiring
    one child element's innerText to equal the entire Excel comment.
    """
    result = driver.execute_script(
        r"""
        const wanted = String(arguments[0] || '');
        const basic = value => String(value || '').normalize('NFKC')
            .replace(/[\u200B-\u200F\u2060\uFE0E\uFE0F\uFEFF]/g, '')
            .replace(/\s+/g, ' ').trim();
        const key = value => basic(value).toLocaleLowerCase()
            .replace(/\p{Extended_Pictographic}/gu, '')
            .replace(/[^\p{L}\p{N}\s]/gu, ' ')
            .replace(/\s+/g, ' ').trim();
        const urlPattern = /https?:\/\/[^\s<>]+/gi;
        const urlKey = value => String(value || '').trim()
            .replace(/^https?:\/\//i, '')
            .replace(/^www\./i, '')
            .replace(/[\/.,;:!?]+$/, '').toLocaleLowerCase();
        const wantedUrls = (wanted.match(urlPattern) || []).map(urlKey);
        const wantedBody = key(wanted.replace(urlPattern, ' '));
        const wantedKey = key(wanted);
        const wantedRaw = basic(wanted).toLocaleLowerCase();
        const visible = element => {
            if (!element || !element.isConnected) return false;
            if (typeof element.checkVisibility === 'function' &&
                !element.checkVisibility({checkOpacity: true, checkVisibilityCSS: true})) {
                return false;
            }
            for (let p = element; p; p = p.parentElement) {
                const css = getComputedStyle(p);
                if (css.display === 'none' || css.visibility === 'hidden' ||
                    Number(css.opacity || 1) <= 0.01 ||
                    p.getAttribute('aria-hidden') === 'true' ||
                    p.hasAttribute('inert')) return false;
            }
            return true;
        };
        const containsPhrase = (hay, needle) => Boolean(needle) &&
            (hay === needle || hay.startsWith(needle + ' ') ||
             hay.endsWith(' ' + needle) || hay.includes(' ' + needle + ' '));
        const candidateSelector = [
            'span', 'p', 'div[dir="auto"]', '[data-lexical-text]',
            'div[data-virtualized="false"]',
            '[data-testid*="comment" i]',
            '[role="article"]', '[role="listitem"]'
        ].join(',');
        const candidates = [...document.querySelectorAll(candidateSelector)]
            .filter(visible)
            // The editor draft is never evidence of a published comment.
            .filter(el => !el.closest('[contenteditable="true"], textarea'))
            .filter(el => !el.querySelector('[contenteditable="true"], textarea'));
        const exact = [];
        const bounded = [];
        for (const element of candidates) {
            const text = String(element.innerText || element.textContent || '');
            if (!text) continue;
            if (text.length > Math.max(1800, wanted.length + 1000)) continue;
            const variants = [text];
            // A posted comment can be split into inline spans and links.
            // Joining direct child text also separates author and body labels.
            if (element.children.length) {
                const spaced = [...element.childNodes].map(node =>
                    node.nodeType === 3 ? node.textContent :
                    (node.innerText || node.textContent || '')
                ).filter(Boolean).join(' ');
                if (spaced) variants.push(spaced);
            }
            const value = key(text);
            const raw = basic(text).toLocaleLowerCase();
            // Exact content may be split into multiple visual spans. Emoji
            // rendering sometimes differs between input and published text.
            if ((wantedKey && value === wantedKey) ||
                (!wantedKey && wantedRaw && raw === wantedRaw)) {
                exact.push(element);
                continue;
            }
            if (!element.matches(
                'div[data-virtualized="false"], [data-testid*="comment" i], ' +
                '[role="article"], [role="listitem"], div[dir="auto"]'
            )) continue;
            const urls = [...element.querySelectorAll('a[href]')]
                .map(link => urlKey(link.href));
            const urlsMatch = wantedUrls.every(link =>
                urls.some(actual => actual === link) ||
                variants.some(item => urlKey(item).includes(link)));
            const textMatch = wantedBody
                ? variants.some(item => containsPhrase(
                    key(item.replace(urlPattern, ' ')), wantedBody
                ))
                : (!wantedUrls.length && wantedRaw &&
                   variants.some(item => basic(item).toLocaleLowerCase().includes(wantedRaw)));
            if (urlsMatch && (textMatch || (!wantedBody && wantedUrls.length))) {
                bounded.push(element);
            }
        }
        const all = [...new Set([...exact, ...bounded])];
        // Count one rendered comment once, not each nested wrapper.
        const leaves = all.filter(el => !all.some(other =>
            other !== el && el.contains(other)));
        return {
            count: leaves.length,
            exact: exact.length,
            bounded: bounded.length
        };
    """,
        str(comment or ""),
    )
    if not isinstance(result, dict):
        return {"count": 0, "exact": 0, "bounded": 0}
    return result


def _reveal_reel_comments_for_verification(driver) -> None:
    """Open a collapsed Reel comment panel without sending anything."""
    if "/reel/" not in (driver.current_url or "").casefold():
        return
    control = driver.execute_script(r"""
        const norm = value => String(value || '').normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .replace(/đ/g, 'd').toLowerCase().replace(/\s+/g, ' ').trim();
        const visible = el => el.isConnected &&
            (!el.checkVisibility || el.checkVisibility());
        const buttons = [...document.querySelectorAll('button, [role="button"]')]
            .filter(visible).filter(el => el.getAttribute('aria-expanded') === 'false')
            .filter(el => /^(?:comment|comments|binh luan|xem binh luan|view comments)$/.test(
                norm(el.getAttribute('aria-label') || el.getAttribute('title') ||
                    el.innerText)));
        return buttons.length === 1 ? buttons[0] : null;
    """)
    if control is not None:
        driver.execute_script("arguments[0].click();", control)


def verify_visible_published_comment(
    driver,
    comment: str,
    *,
    post_url: str,
    timeout: int = 25,
) -> bool:
    """Read-only verification of an already attempted Comment send.

    This function must never type, click Send, or retry publishing.
    """
    expected_url = _normalize_facebook_post_url(post_url)
    if driver is None or not expected_url or not str(comment or "").strip():
        raise FacebookPostError(
            "A valid Post URL and Comment are required.", retryable=False
        )
    if _normalize_facebook_post_url(driver.current_url) != expected_url:
        raise FacebookPostError(
            "Browser is not on the expected Facebook Post.", retryable=False
        )
    if int(_published_comment_snapshot(driver, comment).get("count") or 0) > 0:
        return True
    _reveal_reel_comments_for_verification(driver)
    try:
        WebDriverWait(driver, timeout, poll_frequency=0.5).until(
            lambda browser: int(
                _published_comment_snapshot(browser, comment).get("count") or 0
            )
            > 0
        )
        return True
    except TimeoutException:
        return False


# ----- Comment on the Verified Published Post -----
class CommentSubmissionUnknownError(FacebookPostError):
    """A comment may have been sent. Never send it again automatically."""

    def __init__(self, message: str):
        super().__init__(message, retryable=False)


def post_comment_on_opened_post(
    driver,
    comment: str,
    *,
    post_url: str,
    on_before_send,
    timeout: int = 35,
) -> bool:
    """Use DOM focus to submit one comment to the verified Facebook post."""
    comment = str(comment or "").strip()
    expected_url = _normalize_facebook_post_url(post_url)
    if not comment:
        raise FacebookPostError("Comment text is empty.", retryable=False)
    if driver is None or not expected_url:
        raise FacebookPostError(
            "A verified Post URL is required for commenting.", retryable=False
        )
    if not callable(on_before_send):
        raise FacebookPostError(
            "Missing durable before-comment callback.", retryable=False
        )
    if _normalize_facebook_post_url(driver.current_url) != expected_url:
        raise FacebookPostError(
            "Browser is not on the expected Facebook Post.", retryable=False
        )

    # ----- Locate the Comment Editor and Send Control by DOM ----
    inspect_script = r"""
        const action = arguments[0];
        const wanted = arguments[1];
        const norm = value => String(value || '')
            .normalize('NFKC')
            .replace(/[\u200B-\u200D\u2060\uFE0E\uFE0F\uFEFF]/g, '')
            .replace(/\s+/g, ' ').trim();
        const labelNorm = value => norm(value).toLowerCase().normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd');
        const visible = element => {
            if (!element || !element.isConnected) return false;
            if (typeof element.checkVisibility === 'function' &&
                !element.checkVisibility({checkOpacity: true, checkVisibilityCSS: true})) {
                return false;
            }
            for (let node = element; node; node = node.parentElement) {
                const css = getComputedStyle(node);
                if (css.display === 'none' || css.visibility === 'hidden' ||
                    Number(css.opacity || 1) <= .01 ||
                    node.getAttribute('aria-hidden') === 'true' ||
                    node.hasAttribute('inert')) return false;
            }
            return true;
        };
        const label = element => [
            element.getAttribute('aria-label'),
            element.getAttribute('aria-placeholder'),
            element.getAttribute('data-placeholder'),
            element.getAttribute('placeholder'),
            element.getAttribute('title'),
            element.getAttribute('data-testid')
        ].map(labelNorm).filter(Boolean).join(' ');
        const isComment = value => /(?:comment|binh luan)/.test(value);
        const selector = '[contenteditable="true"], textarea, [role="textbox"]';
        const activeModals = [...document.querySelectorAll('[aria-modal="true"]')]
            .filter(visible);
        const activeModal = activeModals[activeModals.length - 1] || null;
        const editors = [...new Set([...document.querySelectorAll(selector)])]
            .filter(el => visible(el) && !el.disabled &&
                el.getAttribute('aria-disabled') !== 'true' &&
                (!activeModal || activeModal.contains(el)) &&
                (el.matches('[contenteditable="true"], textarea')))
            .filter(el => isComment(label(el)) ||
                (el.parentElement && isComment(label(el.parentElement))));
        const rank = element => {
            const own = label(element);
            return (/(?:write|viet|enter|nhap|leave|de lai).*(?:comment|binh luan)/.test(own) ? 40 : 0) +
                (isComment(own) ? 30 : 0) +
                (element.matches('[contenteditable="true"]') ? 10 : 0) +
                (element.getAttribute('role') === 'textbox' ? 5 : 0);
        };
        editors.sort((a, b) => rank(b) - rank(a));
        // React can replace the Lexical editor after text insertion. Prefer
        // the one containing this exact draft over an empty old editor.
        const draftEditors = editors.filter(el => norm(
            el.tagName === 'TEXTAREA' ? el.value : el.innerText
        ) === norm(wanted));
        const editor = draftEditors.length === 1
            ? draftEditors[0] : (editors[0] || null);
        const ambiguousEditor = draftEditors.length > 1 ||
            (draftEditors.length === 0 && editors.length > 1 &&
             rank(editors[0]) === rank(editors[1]));

        if (action === 'inspect') {
            let sendButton = null;
            let sendDisabled = false;
            let ambiguousSend = false;
            if (editor && !ambiguousEditor) {
                const sendLabels = new Set([
                    'send', 'post', 'send comment', 'post comment',
                    'submit comment', 'publish comment', 'gui', 'dang',
                    'gui binh luan', 'dang binh luan'
                ]);
                // Search the editor's DOM ancestors; never compare screen coordinates.
                for (let root = editor.parentElement, depth = 0;
                     root && depth < 8; root = root.parentElement, depth++) {
                    if (activeModal && !activeModal.contains(root)) break;
                    const controls = [...root.querySelectorAll(
                        'button, [role="button"], input[type="submit"]'
                    )].filter(button => visible(button) &&
                        !button.closest('[contenteditable="true"]') &&
                        (sendLabels.has(labelNorm(
                            button.getAttribute('aria-label') ||
                            button.getAttribute('title') ||
                            button.value || button.innerText
                        )) || /(?:send|submit|post).*(?:comment|button)|(?:comment).*(?:send|submit|post)/
                            .test(labelNorm(button.getAttribute('data-testid')))));
                    if (controls.length) {
                        const enabled = controls.filter(button => !button.disabled &&
                            button.getAttribute('aria-disabled') !== 'true' &&
                            getComputedStyle(button).pointerEvents !== 'none');
                        if (enabled.length === 1) sendButton = enabled[0];
                        else if (enabled.length > 1) ambiguousSend = true;
                        else sendDisabled = true;
                        break;
                    }
                }
            }
            return {
                editor: ambiguousEditor ? null : editor,
                ambiguous_editor: ambiguousEditor,
                send_button: sendButton,
                send_disabled: sendDisabled,
                ambiguous_send: ambiguousSend
            };
        }
        if (action === 'toggle') {
            if (editor && !ambiguousEditor) return null;
            // Open a collapsed Reel comment panel using its DOM element.
            const candidates = [...document.querySelectorAll('button, [role="button"]')]
                .filter(visible).filter(el => !activeModal || activeModal.contains(el))
                .filter(el => {
                    const text = labelNorm(el.getAttribute('aria-label') ||
                        el.innerText || el.getAttribute('title'));
                    return /^(?:comment|comments|binh luan|view comments|xem binh luan)$/.test(text) &&
                        el.getAttribute('aria-expanded') === 'false';
                });
            return candidates.length === 1 ? candidates[0] : null;
        }
        return null;
    """

    def inspect(action):
        return driver.execute_script(inspect_script, action, comment)

    def find_editor(browser):
        state = inspect("inspect")
        if state.get("ambiguous_editor"):
            raise FacebookPostError(
                "Multiple comment editors are visible; cannot choose safely.",
                retryable=False,
            )
        return state.get("editor") or False

    try:
        try:
            editor = WebDriverWait(driver, 5, poll_frequency=0.3).until(find_editor)
        except TimeoutException:
            toggle = inspect("toggle")
            if toggle is not None:
                driver.execute_script("arguments[0].click();", toggle)
            editor = WebDriverWait(driver, 15, poll_frequency=0.3).until(find_editor)
    except TimeoutException as error:
        raise FacebookPostError(
            "Comment editor was not found on the published post.",
            retryable=True,
        ) from error
    except WebDriverException as error:
        raise FacebookPostError(
            "Cannot open Facebook comment editor using DOM.",
            retryable=True,
        ) from error

    def read_editor():
        return (
            driver.execute_script(
                "return arguments[0].tagName === 'TEXTAREA' ? "
                "arguments[0].value : arguments[0].innerText;",
                editor,
            )
            or ""
        )

    def normalized(value):
        import unicodedata

        cleaned = unicodedata.normalize("NFKC", str(value or ""))
        cleaned = "".join(
            char
            for char in cleaned
            if char not in "\u200b\u200c\u200d\u2060\ufe0e\ufe0f\ufeff"
        )
        return " ".join(cleaned.split())

    # ----- Focus DOM Editor Without a Pointer Click -----
    try:
        focused = driver.execute_script(
            r"""
            const editor = arguments[0];
            if (!editor || !editor.isConnected) return false;
            const modals = [...document.querySelectorAll('[aria-modal="true"]')]
                .filter(el => !el.hasAttribute('inert') &&
                    el.getAttribute('aria-hidden') !== 'true' &&
                    (!el.checkVisibility || el.checkVisibility()));
            if (modals.length && !modals[modals.length - 1].contains(editor)) {
                return false;
            }
            editor.focus({preventScroll: true});
            return document.activeElement === editor ||
                editor.contains(document.activeElement);
        """,
            editor,
        )
        if not focused:
            raise FacebookPostError(
                "Facebook comment editor could not receive DOM focus.",
                retryable=True,
            )

        existing = normalized(read_editor())
        if existing and existing != normalized(comment):
            raise FacebookPostError(
                "Comment editor already contains different text; refusing to overwrite it.",
                retryable=False,
            )
        if existing != normalized(comment):
            try:
                # CDP inserts text into the DOM-focused Lexical editor.
                # It does not click the element or send an Enter key.
                driver.execute_cdp_cmd("Input.insertText", {"text": comment})
            except (AttributeError, WebDriverException) as cdp_error:
                if "\n" in comment or "\r" in comment:
                    raise FacebookPostError(
                        "Cannot safely type a multiline comment without CDP.",
                        retryable=False,
                    ) from cdp_error

                ActionChains(driver).send_keys(comment).perform()

        WebDriverWait(driver, 15, poll_frequency=0.25).until(
            lambda browser: normalized(read_editor()) == normalized(comment)
        )
        baseline = int(_published_comment_snapshot(driver, comment).get("count") or 0)
        state = inspect("inspect")
        if state.get("ambiguous_send"):
            raise FacebookPostError(
                "Multiple comment Send buttons are visible.",
                retryable=False,
            )
        if state.get("send_disabled"):

            def send_ready(browser):
                current = inspect("inspect")
                if current.get("ambiguous_send"):
                    raise FacebookPostError(
                        "Ambiguous Comment Send buttons.",
                        retryable=False,
                    )
                return current.get("send_button") or False

            send_button = WebDriverWait(driver, 10, poll_frequency=0.25).until(
                send_ready
            )
        else:
            send_button = state.get("send_button")
    except FacebookPostError:
        raise
    except (TimeoutException, WebDriverException) as error:
        reason = str(error).splitlines()[0]
        raise FacebookPostError(
            f"Cannot prepare or verify comment using DOM: {reason}",
            retryable=True,
        ) from error

    # ----- Recover DOM Focus After React Re-renders the Editor -----
    # The Lexical editor can lose focus after Input.insertText or DOM inspection.
    # Re-acquire the live editor and verify that the draft is still intact.
    def focus_live_editor(browser):
        state = inspect("inspect")
        if state.get("ambiguous_editor"):
            raise FacebookPostError(
                "Multiple Comment editors appeared before sending.",
                retryable=False,
            )

        live_editor = state.get("editor")
        if live_editor is None:
            return False

        result = driver.execute_script(
            r"""
            const editor = arguments[0];
            const expected = arguments[1];
            const normalise = value => String(value || '')
                .normalize('NFKC')
                .replace(/[\u200B-\u200D\u2060\uFE0E\uFE0F\uFEFF]/g, '')
                .replace(/\s+/g, ' ').trim();

            if (!editor || !editor.isConnected) {
                return {status: 'detached'};
            }
            const current = editor.tagName === 'TEXTAREA'
                ? editor.value : editor.innerText;
            if (normalise(current) !== normalise(expected)) {
                return {status: 'draft_changed'};
            }
            editor.focus({preventScroll: true});
            const active = document.activeElement;
            return {
                status: active === editor || editor.contains(active)
                    ? 'ready' : 'focus_lost'
            };
        """,
            live_editor,
            comment,
        )

        if result.get("status") == "draft_changed":
            raise FacebookPostError(
                "Comment draft changed before sending; nothing was sent.",
                retryable=True,
            )
        return live_editor if result.get("status") == "ready" else False

    try:
        # Validate the current live Lexical editor for both Send-button and
        # Enter paths. No outgoing comment action has happened yet.
        WebDriverWait(driver, 5, poll_frequency=0.25).until(focus_live_editor)
        if send_button is not None:
            # React may have replaced the Send button during focus recovery.
            current = inspect("inspect")
            if current.get("ambiguous_send"):
                raise FacebookPostError(
                    "Multiple Comment Send buttons are visible.",
                    retryable=False,
                )
            send_button = current.get("send_button")
            if send_button is None:
                raise FacebookPostError(
                    "Comment Send button changed before sending; nothing was sent.",
                    retryable=True,
                )
    except TimeoutException as error:
        raise FacebookPostError(
            "Comment editor could not retain DOM focus; nothing was sent.",
            retryable=True,
        ) from error
    except WebDriverException as error:
        raise FacebookPostError(
            "Cannot focus the live Comment editor; nothing was sent.",
            retryable=True,
        ) from error

    # ----- Durable Boundary: Send Exactly Once -----
    # The callback records Sending before any potentially irreversible action.
    # All focus recovery and draft checks above are safe to retry.
    on_before_send()
    try:
        if send_button is not None:
            clicked = driver.execute_script(
                r"""
                const button = arguments[0];
                if (!button || !button.isConnected || button.disabled ||
                    button.getAttribute('aria-disabled') === 'true') return false;
                button.click();
                return true;
            """,
                send_button,
            )
            if not clicked:
                raise RuntimeError("Comment Send control is no longer available.")
        else:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ENTER)
    except Exception as error:
        reason = str(error).splitlines()[0]
        raise CommentSubmissionUnknownError(
            f"Comment send outcome is uncertain; do not resend: {reason}"
        ) from error

    # ----- Confirm the New Comment, Not Just an Empty Editor -----
    try:
        WebDriverWait(driver, timeout, poll_frequency=0.5).until(
            lambda browser: int(
                _published_comment_snapshot(browser, comment).get("count") or 0
            )
            > baseline
        )
    except Exception as error:
        raise CommentSubmissionUnknownError(
            "Comment send was attempted, but its rendered text could not be "
            "verified in the Reel/Post comment DOM. Do not resend automatically."
        ) from error
    return True
