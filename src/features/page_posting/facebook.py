from pathlib import Path
import re
import time
from urllib.parse import (
    parse_qs,
)

from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains

# ----- Constants and Timeouts -----
POST_BUTTON_TIMEOUT = 60  # seconds
POST_PUBLISH_WAIT_SECONDS = 10  # seconds
POST_TIMESTAMP_CYCLES = 3  # attempts

# ----- Facebook Action Labels -----
POST_ACTIONS = {"post", "publish", "share", "đăng", "chia sẻ"}

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
    "xem tất cả trang cá nhân",
    "xem tất cả hồ sơ",
}

SWITCH_PROFILE_ACTIONS = {
    "switch profile",
    "switch account",
    "chuyển trang cá nhân",
    "chuyển tài khoản",
}

CONFIRM_SWITCH_ACTIONS = {
    "switch now",
    "switch profile now",
    "chuyển ngay",
    "chuyển trang cá nhân ngay",
}

_ACTION_SELECTOR = (
    "button, [role='button'], [role='menuitem'], [role='option'], "
    "a[role='button'], [tabindex='0']"
)

_POPUP_SELECTOR = "[role='menu'], [role='dialog'], [role='listbox']"


# ----- Custom Exceptions -----
class FacebookPostError(RuntimeError):
    pass


class PublishUnknownError(FacebookPostError):
    pass


class CommentPostError(RuntimeError):
    pass


# ----- Text Normalization -----
def _normalise(value: str) -> str:
    return " ".join((value or "").casefold().split())


def _caption_key(value: str) -> str:
    value = (value or "").casefold()
    value = re.sub(r"[^\w\s]", " ", value)
    return " ".join(value.split())


# ----- Element Visibility and Click Helpers -----
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


def _click_once(element, driver) -> None:
    try:
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});",
            element,
        )
    except Exception:
        pass

    element.click()


# ----- DOM Action Finder -----
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


# ----- Facebook Account Menu -----
def _find_account_menu(driver):
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
        const selectors = [
            '[data-testid="blue_bar_profile_link"]',
            'button[aria-label*="your profile" i]',
            '[role="button"][aria-label*="your profile" i]',
            'button[aria-label*="account" i]',
            '[role="button"][aria-label*="account" i]',
            'button[aria-label*="profile" i]',
            '[role="button"][aria-label*="profile" i]',
            'button[aria-label*="tài khoản" i]',
            '[role="button"][aria-label*="tài khoản" i]',
            '[role="button"][aria-label*="trang cá nhân" i]'
        ];
        for (const selector of selectors) {
            const element = Array.from(
                document.querySelectorAll(selector)
            ).find(visible);
            if (element) {
                return element;
            }
        }
        return null;
        """)


def _visible_popup(driver):
    return driver.execute_script(
        r"""
        const visible = element => {
            const style = window.getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            return rect.width > 0 &&
                rect.height > 0 &&
                style.display !== 'none' &&
                style.visibility !== 'hidden' &&
                Number(style.opacity || 1) > 0;
        };
        const popups = Array.from(
            document.querySelectorAll(arguments[0])
        ).filter(visible);
        return popups.length ? popups[popups.length - 1] : null;
        """,
        _POPUP_SELECTOR,
    )


def _wait_for_popup(driver, timeout: int = 12):
    return WebDriverWait(driver, timeout).until(
        lambda current: _visible_popup(current) or False
    )


def _find_page_option(driver, page_name: str, popup):
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
        const selector = arguments[2];
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
                ...Array.from(
                    element.querySelectorAll('img[alt]')
                ).map(image => image.alt)
            ].map(norm).filter(Boolean);
            const matched = values.some(value =>
                value === target ||
                value.startsWith(target + ' ') ||
                value === 'switch to ' + target ||
                value === 'chuyển sang ' + target
            );
            if (matched) {
                return element;
            }
        }
        return null;
        """,
        popup,
        page_name,
        _ACTION_SELECTOR,
    )


# ----- Facebook Session and Page Switching -----
def _wait_for_page_ready(driver, timeout: int = 30) -> None:
    WebDriverWait(driver, timeout).until(
        lambda current: current.execute_script("return document.readyState")
        in {"interactive", "complete"}
    )


def _check_facebook_session(driver) -> None:
    current_url = str(getattr(driver, "current_url", "") or "").casefold()

    if any(
        part in current_url
        for part in (
            "facebook.com/login",
            "facebook.com/checkpoint",
            "facebook.com/challenge",
            "two_step_verification",
        )
    ):
        raise FacebookPostError(
            "The AdsPower profile is not logged in to Facebook "
            "or requires a checkpoint/security verification."
        )


def _wait_for_switch_complete(driver, timeout: int = 15) -> None:
    try:
        WebDriverWait(driver, timeout).until(
            lambda current: _visible_popup(current) is None
        )
    except TimeoutException as error:
        raise FacebookPostError(
            "Facebook did not close the profile selector after the Page was chosen. "
            "The target Page switch could not be confirmed."
        ) from error


def switch_to_page(driver, page_name: str) -> None:
    page_name = str(page_name or "").strip()

    if not page_name:
        raise FacebookPostError("Facebook Page name is missing from Excel.")

    driver.get("https://www.facebook.com/")
    _wait_for_page_ready(driver)
    _check_facebook_session(driver)

    account_menu = _find_account_menu(driver)

    if account_menu is None:
        raise FacebookPostError(
            "Could not find Facebook's account menu in the DOM. "
            "Check whether the AdsPower profile is logged in."
        )

    _click(account_menu, driver)

    try:
        popup = _wait_for_popup(driver)
    except TimeoutException as error:
        raise FacebookPostError("Facebook's account menu did not open.") from error

    attempted_actions = set()

    for _ in range(3):
        page_option = _find_page_option(driver, page_name, popup)

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

            action = _dom_find_action(
                driver,
                labels,
                popup,
                exact=False,
            )

            if action is not None:
                attempted_actions.add(action_name)
                break

        if action is None:
            raise FacebookPostError(
                f"Could not find the Page '{page_name}' in Facebook's profile menu. "
                "Check the Page name in the PAGE sheet and confirm that this profile has access."
            )

        _click(action, driver)

        try:
            popup = _wait_for_popup(driver)
        except TimeoutException as error:
            raise FacebookPostError(
                "Facebook did not open the profile list after the menu action."
            ) from error
    else:
        raise FacebookPostError(f"Could not select the Facebook Page '{page_name}'.")

    popup = _visible_popup(driver)

    confirm_button = _dom_find_action(
        driver,
        CONFIRM_SWITCH_ACTIONS,
        popup,
        exact=False,
    )

    if confirm_button is not None:
        _click(confirm_button, driver)

    _wait_for_switch_complete(driver)
    _check_facebook_session(driver)


# ----- Post Composer Detection -----
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

        except Exception as error:
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

    except Exception as error:
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


# ----- Publish Photo or Video -----
def publish_photo(driver, row: dict) -> None:
    page_name = str(row.get("page") or row.get("page_name") or "").strip()
    page_link = str(row.get("page_link") or "").strip()
    caption = str(row.get("caption") or "").strip()
    media_path = str(row.get("_validated_image") or row.get("image") or "").strip()

    if not page_link:
        raise FacebookPostError("Facebook Page URL is missing from Excel.")

    if not caption:
        raise FacebookPostError("Post caption is missing from Excel.")

    if not media_path:
        raise FacebookPostError("Media path is missing from Excel.")

    switch_to_page(driver, page_name)

    driver.get(page_link)
    _wait_for_page_ready(driver)
    _check_facebook_session(driver)
    _dismiss_call_now_popup(driver, appearance_timeout=1)

    composer = _find_composer_trigger(driver)

    if composer is None:
        raise FacebookPostError(
            "Could not locate the Page composer in Facebook's DOM structure."
        )

    _click(composer, driver)
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

    caption_box = WebDriverWait(driver, 20).until(locate_caption)

    _click(caption_box, driver)
    caption_box.send_keys(caption)

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
    driver, caption: str, attempts: int = 2, page_link: str = ""
) -> None:
    attempts = max(1, int(attempts))
    for cycle in range(1, attempts + 1):
        driver.refresh()
        try:
            _wait_for_page_ready(driver, timeout=30)
        except TimeoutException:
            pass
        _check_facebook_session(driver)
        try:
            _dismiss_call_now_popup(driver, timeout=3)
        except Exception:
            pass
        if page_link:
            expected = page_link.split("?", 1)[0].rstrip("/").casefold()
            actual = driver.current_url.split("?", 1)[0].rstrip("/").casefold()
            if expected != actual:
                driver.get(page_link)
                _wait_for_page_ready(driver, timeout=30)
                _check_facebook_session(driver)
        time.sleep(3)
        _scroll_to_render_posts(driver, pixels=600, wait=1.5)
        article = _find_post_article(driver, caption, timeout=12)
        if article is None:
            continue
        anchors = article.find_elements(By.CSS_SELECTOR, "a[href]")
        if len(anchors) < 3:
            continue
        candidate = anchors[2]
        if not candidate.is_displayed() or not candidate.is_enabled():
            continue
        original_handles = set(driver.window_handles)
        _click(candidate, driver)
        for _ in range(20):
            new_handles = set(driver.window_handles) - original_handles
            if new_handles:
                driver.switch_to.window(next(iter(new_handles)))
                break
            time.sleep(0.25)
        return
    raise PublishUnknownError(
        f"Post submitted, but its caption/anchor was not found after {attempts} cycles. "
        "Do not republish automatically."
    )


# ----- Post Permalink Normalization -----
def _post_permalink(url: str) -> str:
    from urllib.parse import urlparse

    parts = urlparse(url or "")
    if parts.hostname not in ("www.facebook.com", "facebook.com", "m.facebook.com"):
        return ""
    path = parts.path.rstrip("/")
    if re.search(r"/(?:reel|videos|posts|permalink)/[0-9]+$", path):
        return "https://www.facebook.com" + path + "/"
    if path == "/story.php":
        query = parse_qs(parts.query)
        if query.get("story_fbid"):
            return (
                "https://www.facebook.com/story.php?story_fbid="
                + query["story_fbid"][0]
                + ("&id=" + query["id"][0] if query.get("id") else "")
            )
    return ""


# ----- Publish Comment -----
def post_comment_on_opened_post(driver, comment: str) -> bool:
    comment = str(comment or "").strip()
    if not comment:
        return False
    if not _post_permalink(driver.current_url):
        raise CommentPostError(
            "Opened view is not a verified post permalink. Comment not submitted."
        )
    editors = driver.find_elements(
        By.CSS_SELECTOR,
        "[contenteditable='true'][role='textbox'], [contenteditable='true'][data-lexical-editor='true']",
    )

    def is_comment_editor(el):
        if not _visible(el):
            return False
        label = _normalise(
            " ".join(
                filter(
                    None,
                    [
                        el.get_attribute("aria-label"),
                        el.get_attribute("data-placeholder"),
                        el.get_attribute("aria-placeholder"),
                    ],
                )
            )
        )
        return any(
            token in label
            for token in ("comment", "bình luận", "write a comment", "viết bình luận")
        )

    candidates = [el for el in editors if is_comment_editor(el)]
    if len(candidates) != 1:
        raise CommentPostError(
            f"Expected one comment editor, found {len(candidates)}. Nothing submitted."
        )
    box = candidates[0]
    _click(box, driver)
    lines = comment.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for i, line in enumerate(lines):
        if line:
            box.send_keys(line)
        if i != len(lines) - 1:
            box.send_keys(Keys.SHIFT, Keys.ENTER)
    box.send_keys(Keys.ENTER)
    key = _normalise(comment)

    def confirmed(_):
        try:
            visible = driver.find_elements(
                By.CSS_SELECTOR, "div[role='article'], ul li, div[dir='auto']"
            )
            for node in visible:
                if not _visible(node):
                    continue
                if node.get_attribute("contenteditable") == "true":
                    continue
                if _normalise(node.text) == key:
                    return True
            return False
        except StaleElementReferenceException:
            return False

    try:
        WebDriverWait(driver, 20, poll_frequency=0.5).until(confirmed)
    except TimeoutException:
        return False
    return True


# ----- Get Opened Post URL -----
def get_opened_post_url(driver) -> str:
    url = _post_permalink(driver.current_url)
    if not url:
        raise PublishUnknownError(
            "Current browser address is not a verified post permalink; URL not saved."
        )
    return url
