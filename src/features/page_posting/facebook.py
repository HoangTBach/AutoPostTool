import time

from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

# ----- Exceptions -----


class FacebookPostError(RuntimeError):
    pass


class PublishUnknownError(FacebookPostError):
    pass


class CommentPostError(RuntimeError):
    pass


# ----- Labels and selectors -----


PHOTO_ACTIONS = {
    "photo/video",
    "photo / video",
    "photos/videos",
    "add photos/videos",
    "add photo/video",
    "photos and videos",
    "photo and video",
    "ảnh/video",
    "ảnh và video",
}

POST_ACTIONS = {"post", "publish", "share", "đăng", "chia sẻ"}

NEXT_ACTIONS = {
    "next",
    "continue",
    "proceed",
    "tiếp",
    "tiếp theo",
    "tiếp tục",
}

COMMENT_ACTIONS = {
    "comment",
    "send",
    "bình luận",
    "gửi",
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

_PHOTO_ACTION_SELECTOR = _ACTION_SELECTOR + ", [aria-label]"

_POPUP_SELECTOR = "[role='menu'], [role='dialog'], [role='listbox']"

POST_BUTTON_TIMEOUT = 60


# ----- General DOM helpers -----
def _normalise(value: str) -> str:
    return " ".join((value or "").casefold().split())


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


# ----- Switch Facebook Page -----
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


# ----- Open post composer -----
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


# ----- Import media -----
def _find_photo_action(driver, dialog):
    try:
        action = _dom_find_action(
            driver,
            PHOTO_ACTIONS,
            dialog,
            exact=False,
        )
    except StaleElementReferenceException:
        action = None

    if action is not None:
        return action

    script = r"""
        const dialog = arguments[0];

        const labels = arguments[1].map(value =>
            String(value || '')
                .normalize('NFC')
                .toLocaleLowerCase()
                .replace(/\s*\/\s*/g, '/')
                .replace(/[_-]+/g, ' ')
                .replace(/\s+/g, ' ')
                .trim()
                .replace(/\bphoto video\b/g, 'photo/video')
                .replace(/\bphotos videos\b/g, 'photos/videos')
        );

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
            .replace(/\s*\/\s*/g, '/')
            .replace(/[_-]+/g, ' ')
            .replace(/\s+/g, ' ')
            .trim()
            .replace(/\bphoto video\b/g, 'photo/video')
            .replace(/\bphotos videos\b/g, 'photos/videos');

        const matchesPhoto = element => {
            if (
                !visible(element) ||
                element.disabled ||
                element.getAttribute('aria-disabled') === 'true'
            ) {
                return false;
            }

            const values = [
                element.getAttribute('aria-label'),
                element.getAttribute('title'),
                element.innerText,
                element.textContent,
                element.getAttribute('data-testid'),
                ...Array.from(
                    element.querySelectorAll('img[alt]')
                ).map(image => image.alt)
            ].map(norm).filter(Boolean);

            return values.some(value =>
                labels.some(label =>
                    value === label ||
                    value.startsWith(label) ||
                    value.includes(label)
                )
            );
        };

        const roots = [];

        const addRoot = element => {
            if (element && !roots.includes(element) && visible(element)) {
                roots.push(element);
            }
        };

        addRoot(dialog);

        const regionSelector = [
            '[role="dialog"]',
            '[aria-modal="true"]',
            '[data-pagelet*="Composer"]',
            '[data-testid*="composer" i]',
            '[aria-label*="create post" i]',
            '[aria-label*="tạo bài viết" i]'
        ].join(',');

        const regions = Array.from(
            document.querySelectorAll(regionSelector)
        ).filter(visible);

        const score = element => {
            let value = 0;

            if (element.querySelector("[contenteditable='true'], textarea")) {
                value += 2;
            }

            const text = String(
                element.innerText || element.textContent || ''
            ).toLocaleLowerCase();

            if (
                /create post|what's on your mind|add to your post|tạo bài viết|bạn đang nghĩ gì/.test(text)
            ) {
                value += 2;
            }

            if (
                Array.from(element.querySelectorAll(selector)).some(matchesPhoto)
            ) {
                value += 4;
            }

            if (element.matches('[role="dialog"], [aria-modal="true"]')) {
                value += 1;
            }

            return value;
        };

        regions.sort((left, right) => score(right) - score(left));
        regions.forEach(addRoot);

        addRoot(document.querySelector('[role="main"]'));

        for (const root of roots) {
            if (root.matches && root.matches(selector) && matchesPhoto(root)) {
                return root;
            }

            const actions = Array.from(root.querySelectorAll(selector));

            for (let index = actions.length - 1; index >= 0; index -= 1) {
                if (matchesPhoto(actions[index])) {
                    return actions[index];
                }
            }
        }

        return null;
    """

    try:
        return driver.execute_script(
            script,
            dialog,
            sorted(PHOTO_ACTIONS),
            _PHOTO_ACTION_SELECTOR,
        )
    except StaleElementReferenceException:
        return driver.execute_script(
            script,
            None,
            sorted(PHOTO_ACTIONS),
            _PHOTO_ACTION_SELECTOR,
        )


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


# ----- Enter caption -----
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


# ----- Find published post -----
def _find_post_article(driver, caption: str, timeout: int = 12):
    snippet = " ".join(caption.split())[:60]

    if not snippet:
        return None

    def locate(current):
        articles = current.find_elements(By.CSS_SELECTOR, "[role='article']")

        for article in reversed(articles):
            if not _visible(article):
                continue

            try:
                article_text = " ".join(article.text.split())

                if snippet.casefold() in article_text.casefold():
                    return article
            except StaleElementReferenceException:
                continue

        return False

    try:
        return WebDriverWait(driver, timeout).until(locate)
    except TimeoutException:
        return None


def _find_post_url(article) -> str:
    if article is None:
        return ""

    try:
        links = article.find_elements(By.CSS_SELECTOR, "a[href]")

        for link in links:
            href = link.get_attribute("href") or ""
            lower = href.casefold()

            if "facebook.com" in lower and any(
                part in lower
                for part in (
                    "/posts/",
                    "/permalink/",
                    "story_fbid=",
                    "/photo/",
                )
            ):
                return href
    except Exception:
        pass

    return ""


# ----- Inspect Post button -----
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

            return /(?:post|publish|share).*(?:button|submit)|(?:button|submit).*(?:post|publish|share)/i
                .test(testId);
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


# ----- Inspect Next button -----
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

            return /(?:next|continue).*(?:button|submit)|(?:button|submit).*(?:next|continue)/i
                .test(testId);
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


# ----- Read workflow snapshot -----
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
                ].join('~'));

            return {
                label: root.getAttribute('aria-label') || '',
                testId: root.getAttribute('data-testid') || '',
                text,
                controls
            };
        });

        return JSON.stringify(snapshots).slice(0, 15000);
        """) or ""


# ----- Read composer status -----
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


# ----- Wait for Next or Post -----
def _wait_for_workflow_action(driver, timeout: int = POST_BUTTON_TIMEOUT):
    last_state = {
        "next": "not_found",
        "post": "not_found",
    }

    def locate(current):
        try:
            next_result = _inspect_next_button(current)
            last_state["next"] = next_result.get("status", "not_found")

            if last_state["next"] == "found":
                button = next_result.get("element")

                if button is not None and _visible(button) and button.is_enabled():
                    return "next", button

            # Nếu Tiếp còn hiển thị nhưng bị khóa, không bỏ qua bước đó.
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


# ----- Wait for workflow transition -----
def _wait_for_step_transition(
    driver,
    previous_button,
    previous_snapshot: str,
    timeout: int = 20,
) -> None:
    def transitioned(current):
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

            # So sánh WebElement theo ID DOM, không dùng "is not".
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


# ----- Wait for Post button -----
def _wait_for_post_button(driver, timeout: int = POST_BUTTON_TIMEOUT):
    last_state = {"status": "not_found"}

    def locate(current):
        try:
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


# ----- Publish post -----
def publish_photo(driver, row: dict) -> str:
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

    # ----- Switch to Page -----

    switch_to_page(driver, page_name)

    # ----- Open Page -----

    driver.get(page_link)
    _wait_for_page_ready(driver)
    _check_facebook_session(driver)

    # ----- Open composer -----

    composer = _find_composer_trigger(driver)

    if composer is None:
        raise FacebookPostError(
            "Could not locate the Page composer in Facebook's DOM structure."
        )

    _click(composer, driver)
    dialog = _wait_for_dialog(driver)

    # ----- Import media -----

    photo_button = _find_photo_action(driver, dialog)

    if photo_button is None:
        raise FacebookPostError(
            "Could not find a visible Photo/Video control in the composer DOM. "
            "Facebook may have changed the composer structure or the control label."
        )

    _click(photo_button, driver)
    dialog = _visible_dialog(driver) or dialog

    file_input = _find_file_input(driver, dialog)
    file_input.send_keys(media_path)

    # ----- Enter caption -----

    def locate_caption(_):
        try:
            current_dialog = _visible_dialog(driver) or dialog
            return _find_caption_box(current_dialog) or False
        except StaleElementReferenceException:
            return False

    caption_box = WebDriverWait(driver, 20).until(locate_caption)

    _click(caption_box, driver)
    caption_box.send_keys(caption)

    # ----- Process Next -> Next -> Post -----

    for step in range(1, 3):
        action, action_button = _wait_for_workflow_action(
            driver,
            timeout=POST_BUTTON_TIMEOUT,
        )

        if action != "next":
            raise FacebookPostError(
                f"Expected Facebook's Next button at step {step}/2, "
                f"but found {action!r}. The post was not submitted."
            )

        previous_snapshot = _workflow_snapshot(driver)

        try:
            _click_once(action_button, driver)
        except Exception as error:
            raise FacebookPostError(
                f"Could not safely click Facebook's Next button at step {step}/2. "
                "The workflow was stopped to avoid accidentally skipping a step."
            ) from error

        _wait_for_step_transition(
            driver,
            action_button,
            previous_snapshot,
            timeout=20,
        )

    # ----- Wait for final Post button -----

    post_button = _wait_for_post_button(
        driver,
        timeout=POST_BUTTON_TIMEOUT,
    )

    # ----- Click Post once -----

    try:
        _click_once(post_button, driver)
    except Exception as error:
        raise PublishUnknownError(
            "Facebook did not confirm whether the Post click was accepted. "
            "Check the Page before retrying to avoid publishing a duplicate."
        ) from error

    # ----- Verify published post -----

    try:
        WebDriverWait(driver, 30).until(
            lambda current: _visible_dialog(current) is None
        )
    except TimeoutException as error:
        raise PublishUnknownError(
            "Facebook did not close the post composer after submission. "
            "Check the Page before retrying to avoid publishing a duplicate."
        ) from error

    article = _find_post_article(driver, caption, timeout=30)

    if article is None:
        raise PublishUnknownError(
            "The post may have been submitted, but could not be verified. "
            "Check the Page before retrying to avoid publishing a duplicate."
        )

    return _find_post_url(article)


# ----- Post comment -----
def post_comment(driver, caption: str, comment: str) -> None:
    comment = str(comment or "").strip()

    if not comment:
        raise CommentPostError("Comment text is missing.")

    article = _find_post_article(driver, caption, timeout=20)

    if article is None:
        raise CommentPostError("Published post could not be located in the Page feed.")

    box = None

    for item in article.find_elements(
        By.CSS_SELECTOR,
        "[contenteditable='true'][role='textbox'], textarea",
    ):
        if not _visible(item):
            continue

        label = _normalise(
            item.get_attribute("aria-label") or item.get_attribute("placeholder")
        )

        if any(word in label for word in ("comment", "bình luận", "reply", "trả lời")):
            box = item
            break

    # ----- Open comment input if needed -----

    if box is None:
        open_comment = _dom_find_action(
            driver,
            {
                "comment",
                "bình luận",
                "write a comment",
                "viết bình luận",
            },
            article,
            exact=False,
        )

        if open_comment is not None:
            _click(open_comment, driver)
            time.sleep(0.5)

            for item in article.find_elements(
                By.CSS_SELECTOR,
                "[contenteditable='true'][role='textbox'], textarea",
            ):
                if _visible(item):
                    box = item
                    break

    if box is None:
        raise CommentPostError(
            "Could not find the comment input for the published post."
        )

    # ----- Enter comment -----

    _click(box, driver)
    box.send_keys(comment)

    # ----- Submit comment once -----

    submit = _dom_find_action(
        driver,
        COMMENT_ACTIONS,
        article,
        exact=False,
    )

    if submit is not None:
        try:
            _click_once(submit, driver)
        except Exception as error:
            raise CommentPostError(
                "Facebook did not confirm whether the comment submission was accepted. "
                "Check the post before trying again."
            ) from error
    else:
        box.send_keys(Keys.ENTER)

    # ----- Verify comment -----

    def comment_is_confirmed(_):
        try:
            remaining = []

            for item in article.find_elements(
                By.CSS_SELECTOR,
                "[contenteditable='true'][role='textbox'], textarea",
            ):
                remaining.append(
                    (item.text or item.get_attribute("value") or "").strip()
                )

            if any(comment.casefold() in value.casefold() for value in remaining):
                return False

            return comment.casefold() in " ".join(article.text.split()).casefold()

        except StaleElementReferenceException:
            return False

    try:
        WebDriverWait(driver, 15).until(comment_is_confirmed)
    except TimeoutException as error:
        raise CommentPostError(
            "Facebook did not confirm that the comment was published."
        ) from error
