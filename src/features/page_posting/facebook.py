import re
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains

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


# ----- Normalize Caption for Matching -----
def _caption_key(value: str) -> str:
    value = (value or "").casefold()
    value = re.sub(r"[^\w\s]", " ", value)
    return " ".join(value.split())


# ----- Canonicalize Facebook Post URL -----
def _canonical_post_url(href: str) -> str:
    href = str(href or "").strip()

    if not href:
        return ""

    if href.startswith("//"):
        href = "https:" + href
    elif href.startswith("/"):
        href = "https://www.facebook.com" + href

    try:
        parts = urlsplit(href)
    except ValueError:
        return ""

    host = (parts.hostname or "").casefold()

    if host != "facebook.com" and not host.endswith(".facebook.com"):
        return ""

    path = re.sub(r"/{2,}", "/", parts.path or "/").rstrip("/") or "/"
    lower_path = path.casefold()

    # Không dùng link ảnh làm permalink của bài viết.
    if lower_path in {"/photo.php", "/photo", "/photos.php"} or lower_path.startswith(
        ("/photo/", "/photos/")
    ):
        return ""

    # Bài viết, Reel và video.
    if re.fullmatch(
        r"/(?:[^/?#]+/)*(?:reel|reels|video|videos|posts)/[^/?#]+",
        path,
        re.IGNORECASE,
    ):
        return f"https://www.facebook.com{path}"

    # Link chia sẻ bài viết/video.
    if re.fullmatch(r"/share/[prv]/[^/?#]+", path, re.IGNORECASE):
        return f"https://www.facebook.com{path}"

    # Link permalink kiểu cũ.
    if lower_path in {"/permalink.php", "/story.php"}:
        query = parse_qs(parts.query)
        story_fbid = next(iter(query.get("story_fbid", [])), "")
        page_id = next(iter(query.get("id", [])), "")

        if story_fbid and page_id:
            params = urlencode(
                [
                    ("story_fbid", story_fbid),
                    ("id", page_id),
                ]
            )
            return f"https://www.facebook.com/permalink.php?{params}"

    # Video Watch.
    if lower_path == "/watch":
        video_id = next(iter(parse_qs(parts.query).get("v", [])), "")

        if video_id:
            return f"https://www.facebook.com/watch/?{urlencode([('v', video_id)])}"

    return ""


# ----- Find Post Timestamp Link -----
def _find_post_timestamp_link(article):
    if article is None:
        return None

    relative_time = re.compile(
        r"\b\d+\s*(?:s|sec|secs|second|seconds|m|min|mins|minute|minutes|"
        r"h|hr|hrs|hour|hours|d|day|days|w|wk|wks|week|weeks|"
        r"mo|mos|month|months|y|yr|yrs|year|years|"
        r"giây|phút|giờ|ngày|tuần|tháng|năm)\b",
        re.IGNORECASE,
    )

    date_label = re.compile(
        r"\b(?:just now|yesterday|today|hôm nay|hôm qua|vừa xong|"
        r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
        r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|"
        r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b",
        re.IGNORECASE,
    )

    try:
        links = article.find_elements(By.CSS_SELECTOR, "a[href]")
    except StaleElementReferenceException:
        return None

    timestamp_candidates = []
    permalink_candidates = []
    unverified_timestamp_candidates = []

    for index, link in enumerate(links):
        try:
            if not _visible(link):
                continue

            href = (link.get_attribute("href") or "").strip()

            if not href:
                continue

            text = _normalise(link.text)
            aria = _normalise(link.get_attribute("aria-label") or "")
            title = _normalise(link.get_attribute("title") or "")

            try:
                time_nodes = link.find_elements(
                    By.CSS_SELECTOR,
                    "time, abbr, [data-utime]",
                )
                label_nodes = link.find_elements(
                    By.CSS_SELECTOR,
                    "[title], [aria-label]",
                )
            except StaleElementReferenceException:
                continue

            nested_labels = []

            for node in label_nodes:
                try:
                    nested_labels.extend(
                        [
                            _normalise(node.get_attribute("aria-label") or ""),
                            _normalise(node.get_attribute("title") or ""),
                            _normalise(node.text or ""),
                        ]
                    )
                except StaleElementReferenceException:
                    continue

            label = " ".join(
                value for value in [text, aria, title, *nested_labels] if value
            )

            if text in {
                "like",
                "comment",
                "share",
                "thích",
                "bình luận",
                "chia sẻ",
            }:
                continue

            has_timestamp = (
                bool(time_nodes)
                or bool(relative_time.search(label))
                or bool(date_label.search(label))
                or "nội dung thời gian" in label
                or "timestamp" in label
            )

            canonical_url = _canonical_post_url(href)

            if canonical_url:
                permalink_candidates.append((index, link))

                if has_timestamp:
                    score = 0

                    if "nội dung thời gian" in label or "timestamp" in label:
                        score += 100

                    if time_nodes:
                        score += 80

                    if relative_time.search(label):
                        score += 60

                    if date_label.search(label):
                        score += 40

                    timestamp_candidates.append((score, index, link))

            elif has_timestamp:
                # Chỉ dùng khi Facebook không cung cấp permalink hợp lệ
                # trong các link của bài viết. URL sau khi click vẫn phải
                # được kiểm tra, không tự động lưu photo.php.
                score = 0

                if "nội dung thời gian" in label or "timestamp" in label:
                    score += 100

                if time_nodes:
                    score += 80

                if relative_time.search(label):
                    score += 60

                if date_label.search(label):
                    score += 40

                unverified_timestamp_candidates.append((score, index, link))

        except StaleElementReferenceException:
            continue

    # Ưu tiên link vừa có dấu hiệu thời gian vừa là permalink hợp lệ.
    if timestamp_candidates:
        timestamp_candidates.sort(key=lambda item: (-item[0], item[1]))
        print("[DEBUG post] Found timestamp permalink.")
        return timestamp_candidates[0][2]

    # Nếu Facebook không cung cấp nhãn thời gian rõ ràng,
    # lấy permalink hợp lệ đầu tiên trong bài viết.
    if permalink_candidates:
        permalink_candidates.sort(key=lambda item: item[0])
        print("[DEBUG post] Timestamp label unavailable; using post permalink link.")
        return permalink_candidates[0][1]

    # Trường hợp nhãn thời gian có tồn tại nhưng href chưa nhận diện được.
    # Hàm lấy URL thực tế sau khi click và sẽ từ chối URL ảnh nếu vẫn sai.
    if unverified_timestamp_candidates:
        unverified_timestamp_candidates.sort(key=lambda item: (-item[0], item[1]))
        print(
            "[DEBUG post] Found timestamp element without a recognized "
            "permalink. Will inspect the URL after clicking."
        )
        return unverified_timestamp_candidates[0][2]

    debug_links = []

    for link in links[:12]:
        try:
            debug_links.append(
                {
                    "text": (link.text or "")[:50],
                    "aria": link.get_attribute("aria-label"),
                    "href": link.get_attribute("href"),
                }
            )
        except StaleElementReferenceException:
            continue

    print(
        "[DEBUG post] No valid post timestamp link found. "
        f"Available links: {debug_links}"
    )
    return None


# ----- Clean Post Permalink -----
def _clean_post_permalink(url: str) -> str:
    url = str(url or "").strip()

    if not url:
        return ""

    try:
        parts = urlsplit(url)
    except ValueError:
        return ""

    host = (parts.hostname or "").casefold()

    if host != "facebook.com" and not host.endswith(".facebook.com"):
        return ""

    path = re.sub(r"/{2,}", "/", parts.path or "/").rstrip("/") or "/"
    path_lower = path.casefold()
    query_items = parse_qsl(parts.query, keep_blank_values=False)

    if path_lower.endswith("/permalink.php"):
        allowed = {"story_fbid", "id"}
    elif path_lower.endswith("/photo.php") or path_lower == "/photo":
        allowed = {"fbid", "id", "set"}
    elif path_lower == "/watch":
        allowed = {"v"}
    else:
        allowed = set()

    clean_query = urlencode(
        [(key, value) for key, value in query_items if key in allowed]
    )

    return urlunsplit(("https", "www.facebook.com", path, clean_query, ""))


# ----- Open Post Detail and Retrieve URL -----
def _reload_and_find_post_url(
    driver,
    caption: str,
    attempts: int = 2,
) -> str:
    before_post_url = _clean_post_permalink(driver.current_url)

    for attempt in range(1, attempts + 1):
        article = _find_post_article(driver, caption, timeout=15)

        if article is None:
            if attempt >= attempts:
                break

            print(
                f"[DEBUG post] Post not found, attempt {attempt}/{attempts}. "
                "Refreshing the Page."
            )

            time.sleep(3)

            try:
                driver.refresh()
                _wait_for_page_ready(driver, timeout=30)
            except TimeoutException:
                print("[DEBUG post] Page refresh timed out.")
                continue

            _check_facebook_session(driver)

            try:
                _dismiss_call_now_popup(driver, timeout=3)
            except Exception:
                pass

            continue

        print("[DEBUG post] Article found. Looking for timestamp link.")

        timestamp_link = _find_post_timestamp_link(article)

        if timestamp_link is None:
            print("[DEBUG post] Timestamp link not found. Waiting and retrying.")
            time.sleep(2)

            article = _find_post_article(driver, caption, timeout=5)

            if article is not None:
                timestamp_link = _find_post_timestamp_link(article)

        if timestamp_link is None:
            if attempt < attempts:
                continue

            raise PublishUnknownError(
                "The post was found, but its timestamp link could not be located."
            )

        try:
            previous_url = driver.current_url
            previous_handles = set(driver.window_handles)

            # Bắt buộc click timestamp trước khi đọc URL.
            _click(timestamp_link, driver)

            try:
                WebDriverWait(
                    driver,
                    12,
                    poll_frequency=0.3,
                ).until(
                    lambda current: (
                        current.current_url != previous_url
                        or len(current.window_handles) > len(previous_handles)
                    )
                )
            except TimeoutException as error:
                raise PublishUnknownError(
                    "The timestamp was clicked, but Facebook did not navigate "
                    "to the post permalink."
                ) from error

            new_handles = set(driver.window_handles) - previous_handles

            if new_handles:
                driver.switch_to.window(next(iter(new_handles)))

            try:
                _wait_for_page_ready(driver, timeout=30)
            except TimeoutException:
                print("[DEBUG post] Post detail page readiness timed out.")

            # Chỉ lấy URL sau khi click timestamp và điều hướng.
            post_url = _clean_post_permalink(driver.current_url)

            if not post_url:
                raise PublishUnknownError(
                    "Facebook navigated to a URL that could not be recognized "
                    "as a Facebook permalink."
                )

            if post_url == before_post_url:
                raise PublishUnknownError(
                    "The browser URL did not change to the post permalink."
                )

            print(f"[DEBUG post] Retrieved permalink after timestamp click: {post_url}")
            return post_url

        except StaleElementReferenceException as error:
            raise PublishUnknownError(
                "The post changed while clicking its timestamp. "
                "The permalink could not be retrieved."
            ) from error

    raise PublishUnknownError(
        "The published post could not be found after waiting and refreshing. "
        "Check the Page before retrying to avoid publishing a duplicate."
    )


# ----- Public Function to Retrieve Post URL -----
def get_published_post_url(
    driver,
    caption: str,
    attempts: int = 2,
) -> str:
    return _reload_and_find_post_url(driver, caption, attempts)


# ----- Open Post Detail and Retrieve URL -----
def _reload_and_find_post_url(
    driver,
    caption: str,
    attempts: int = 2,
) -> str:
    before_post_url = _clean_post_permalink(driver.current_url)

    for attempt in range(1, attempts + 1):
        article = _find_post_article(driver, caption, timeout=15)

        if article is None:
            if attempt >= attempts:
                break

            print(
                f"[DEBUG post] Post not found, attempt {attempt}/{attempts}. "
                "Refreshing the Page."
            )

            time.sleep(3)

            try:
                driver.refresh()
                _wait_for_page_ready(driver, timeout=30)
            except TimeoutException:
                print("[DEBUG post] Page refresh timed out.")
                continue

            _check_facebook_session(driver)

            try:
                _dismiss_call_now_popup(driver, timeout=3)
            except Exception:
                pass

            continue

        print("[DEBUG post] Article found. Looking for timestamp link.")

        timestamp_link = _find_post_timestamp_link(article)

        if timestamp_link is None:
            print("[DEBUG post] Timestamp link not found. Waiting and retrying.")
            time.sleep(2)

            article = _find_post_article(driver, caption, timeout=5)

            if article is not None:
                timestamp_link = _find_post_timestamp_link(article)

        if timestamp_link is None:
            if attempt < attempts:
                continue

            raise PublishUnknownError(
                "The post was found, but its timestamp link could not be located."
            )

        try:
            previous_url = driver.current_url
            previous_handles = set(driver.window_handles)

            # Bắt buộc click timestamp trước khi đọc URL.
            _click(timestamp_link, driver)

            try:
                WebDriverWait(
                    driver,
                    12,
                    poll_frequency=0.3,
                ).until(
                    lambda current: (
                        current.current_url != previous_url
                        or len(current.window_handles) > len(previous_handles)
                    )
                )
            except TimeoutException as error:
                raise PublishUnknownError(
                    "The timestamp was clicked, but Facebook did not navigate "
                    "to the post permalink."
                ) from error

            new_handles = set(driver.window_handles) - previous_handles

            if new_handles:
                driver.switch_to.window(next(iter(new_handles)))

            try:
                _wait_for_page_ready(driver, timeout=30)
            except TimeoutException:
                print("[DEBUG post] Post detail page readiness timed out.")

            # Chỉ lấy URL sau khi click timestamp và điều hướng.
            post_url = _clean_post_permalink(driver.current_url)

            if not post_url:
                raise PublishUnknownError(
                    "Facebook navigated to a URL that could not be recognized "
                    "as a Facebook permalink."
                )

            if post_url == before_post_url:
                raise PublishUnknownError(
                    "The browser URL did not change to the post permalink."
                )

            print(f"[DEBUG post] Retrieved permalink after timestamp click: {post_url}")
            return post_url

        except StaleElementReferenceException as error:
            raise PublishUnknownError(
                "The post changed while clicking its timestamp. "
                "The permalink could not be retrieved."
            ) from error

    raise PublishUnknownError(
        "The published post could not be found after waiting and refreshing. "
        "Check the Page before retrying to avoid publishing a duplicate."
    )


# ----- Public Function to Retrieve Post URL -----
def get_published_post_url(
    driver,
    caption: str,
    attempts: int = 2,
) -> str:
    return _reload_and_find_post_url(driver, caption, attempts)


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
def _find_post_article(driver, caption: str, timeout: int = 15):
    words = _caption_key(caption).split()
    snippet = " ".join(words[:8])

    if not snippet:
        return None

    def locate(current):
        try:
            # First try Facebook's native article container.
            articles = current.find_elements(
                By.CSS_SELECTOR,
                "[role='article'], article",
            )

            for article in articles:
                try:
                    if not _visible(article):
                        continue

                    if snippet in _caption_key(article.text):
                        print("[DEBUG post] Caption matched a post article.")
                        return article

                except StaleElementReferenceException:
                    continue

            # Fallback: climb from the caption to the container
            # that also contains the timestamp or post actions.
            candidate = current.execute_script(
                r"""
                const needle = arguments[0];

                const norm = value => String(value || '')
                    .normalize('NFKC')
                    .toLocaleLowerCase()
                    .replace(/[^\p{L}\p{N}\s]/gu, ' ')
                    .replace(/\s+/g, ' ')
                    .trim();

                const visible = el => {
                    const rect = el.getBoundingClientRect();
                    const style = getComputedStyle(el);

                    return rect.width > 0 &&
                        rect.height > 0 &&
                        style.display !== 'none' &&
                        style.visibility !== 'hidden';
                };

                const timestampPattern =
                    /\b\d+\s*(?:s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days|w|wk|wks|week|weeks|mo|mos|month|months|y|yr|yrs|year|years|giây|phút|giờ|ngày|tuần|tháng|năm)\b|\b(?:just now|yesterday|today|hôm nay|hôm qua|vừa xong)\b|\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?\s+\d{1,2}\b|\b\d{1,2}:\d{2}(?:\s*[ap]m)?\b/i;

                const hasTimestamp = node => {
                    const elements = [
                        ...node.querySelectorAll('a[href], time, abbr')
                    ];

                    return elements.some(el => {
                        const label = [
                            el.innerText,
                            el.getAttribute('aria-label'),
                            el.getAttribute('title'),
                            el.getAttribute('datetime'),
                            el.getAttribute('data-tooltip-content')
                        ].filter(Boolean).join(' ');

                        return timestampPattern.test(label) ||
                            el.matches('time[datetime], abbr[data-utime]');
                    });
                };

                const hasPostActions = node => {
                    const actions = [
                        ...node.querySelectorAll('button, [role="button"]')
                    ];

                    return actions.some(el => {
                        const label = norm([
                            el.innerText,
                            el.getAttribute('aria-label')
                        ].filter(Boolean).join(' '));

                        return /^(like|comment|share|thích|bình luận|chia sẻ)(\s+\d+)?$/
                            .test(label);
                    });
                };

                const matches = [
                    ...document.querySelectorAll(
                        '[role="article"], article, div'
                    )
                ].filter(el => {
                    if (!visible(el)) return false;

                    const text = norm(el.innerText);
                    return text.includes(needle) && text.length < 12000;
                });

                matches.sort(
                    (a, b) =>
                        norm(a.innerText).length -
                        norm(b.innerText).length
                );

                let actionFallback = null;

                for (const match of matches) {
                    let node = match;
                    let depth = 0;

                    while (
                        node &&
                        node !== document.body &&
                        depth < 18
                    ) {
                        const text = norm(node.innerText);

                        if (
                            !text.includes(needle) ||
                            text.length >= 12000
                        ) {
                            break;
                        }

                        if (node.matches('[role="article"], article')) {
                            return node;
                        }

                        // Prefer the smallest ancestor containing both
                        // the caption and the post timestamp.
                        if (hasTimestamp(node)) {
                            return node;
                        }

                        if (
                            !actionFallback &&
                            hasPostActions(node)
                        ) {
                            actionFallback = node;
                        }

                        node = node.parentElement;
                        depth += 1;
                    }
                }

                return actionFallback;
                """,
                snippet,
            )

            if candidate:
                print(
                    "[DEBUG post] Found the full post container "
                    "using the caption fallback."
                )
                return candidate

            return False

        except StaleElementReferenceException:
            return False

    try:
        return WebDriverWait(
            driver,
            timeout,
            poll_frequency=0.5,
        ).until(locate)

    except TimeoutException:
        print("[DEBUG post] Post container not found. " f"Search key: {snippet!r}")
        return None


# ----- Find Post Timestamp Link -----
def _find_post_timestamp_link(article):
    if article is None:
        return None

    relative_time = re.compile(
        r"\b\d+\s*(?:s|sec|secs|second|seconds|m|min|mins|minute|minutes|"
        r"h|hr|hrs|hour|hours|d|day|days|w|wk|wks|week|weeks|"
        r"mo|mos|month|months|y|yr|yrs|year|years|"
        r"phút|giờ|ngày|tuần|tháng|năm)\b",
        re.IGNORECASE,
    )

    date_label = re.compile(
        r"\b(?:just now|yesterday|today|hôm nay|hôm qua|vừa xong|"
        r"mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|thu(?:rsday)?|"
        r"fri(?:day)?|sat(?:urday)?|sun(?:day)?|"
        r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
        r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|"
        r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b",
        re.IGNORECASE,
    )

    try:
        links = article.find_elements(By.CSS_SELECTOR, "a[href]")
    except StaleElementReferenceException:
        return None

    candidates = []

    for index, link in enumerate(links):
        try:
            if not _visible(link):
                continue

            href = (link.get_attribute("href") or "").strip()

            if "facebook.com" not in href.casefold():
                continue

            text = _normalise(link.text)
            aria = _normalise(link.get_attribute("aria-label") or "")
            title = _normalise(link.get_attribute("title") or "")

            if text in {
                "like",
                "comment",
                "share",
                "thích",
                "bình luận",
                "chia sẻ",
            }:
                continue

            text_is_time = bool(relative_time.search(text) or date_label.search(text))

            aria_is_time = bool(
                relative_time.search(aria)
                or date_label.search(aria)
                or relative_time.search(title)
                or date_label.search(title)
            )

            # Chỉ nhận chữ thời gian thực sự, không nhận mọi link trong bài.
            if not text_is_time and not (not text and aria_is_time):
                continue

            href_lower = href.casefold()

            try:
                path = urlsplit(href).path.casefold()
            except ValueError:
                continue

            # Ưu tiên đường dẫn permalink của bài đăng.
            if (
                re.search(
                    r"/(?:[^/?#]+/)*(?:posts|reel|reels|videos|"
                    r"permalink\.php|share/[prv])(?:/|$)",
                    path,
                )
                or "story_fbid=" in href_lower
            ):
                score = 100
            elif path.endswith("/photo.php") or path.rstrip("/") == "/photo":
                score = 40
            elif "/comment" in path or "/reply" in path:
                score = 0
            else:
                score = 20

            score += 10 if text_is_time else 5
            candidates.append((score, index, link))

        except StaleElementReferenceException:
            continue

    if not candidates:
        return None

    # Nếu điểm bằng nhau, chọn link xuất hiện sớm hơn trong bài viết.
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][2]


# ----- Open Post Detail and Retrieve URL -----
def _reload_and_find_post_url(
    driver,
    caption: str,
    attempts: int = 2,
) -> str:
    attempts = max(1, int(attempts))

    for attempt in range(1, attempts + 1):
        print(f"[DEBUG post] Finding post, attempt {attempt}/{attempts}.")

        article = _find_post_article(
            driver,
            caption,
            timeout=15,
        )

        if article is None:
            if attempt >= attempts:
                break

            print("[DEBUG post] Post not found. Refreshing the Page.")
            time.sleep(3)

            try:
                driver.refresh()
                _wait_for_page_ready(driver, timeout=30)
                _check_facebook_session(driver)
                _dismiss_call_now_popup(driver, timeout=3)
            except TimeoutException:
                print("[DEBUG post] Page refresh timed out.")

            continue

        timestamp_link = _find_post_timestamp_link(article)

        if timestamp_link is None:
            if attempt >= attempts:
                break

            print(
                "[DEBUG post] Timestamp link unavailable. " "Refreshing and retrying."
            )
            time.sleep(2)

            try:
                driver.refresh()
                _wait_for_page_ready(driver, timeout=30)
                _check_facebook_session(driver)
                _dismiss_call_now_popup(driver, timeout=3)
            except TimeoutException:
                print("[DEBUG post] Page refresh timed out.")

            continue

        before_url = driver.current_url
        before_handles = set(driver.window_handles)
        original_handle = driver.current_window_handle
        href = (timestamp_link.get_attribute("href") or "").strip()

        try:
            # The required action: click the post timestamp first.
            _click(timestamp_link, driver)

        except StaleElementReferenceException:
            print("[DEBUG post] Timestamp became stale. Retrying.")
            continue

        try:
            WebDriverWait(
                driver,
                12,
                poll_frequency=0.3,
            ).until(
                lambda current: (
                    current.current_url != before_url
                    or bool(set(current.window_handles) - before_handles)
                )
            )

        except TimeoutException:
            # Navigate directly only if the timestamp href is already
            # recognized as a safe post permalink, never a photo URL.
            safe_href = _canonical_post_url(href)

            if safe_href and driver.current_url == before_url:
                print(
                    "[DEBUG post] Timestamp click did not navigate. "
                    "Opening its validated post permalink."
                )
                driver.get(safe_href)
            else:
                print("[DEBUG post] Timestamp click did not open a " "different URL.")
                continue

        new_handles = set(driver.window_handles) - before_handles

        if new_handles:
            driver.switch_to.window(next(iter(new_handles)))

        try:
            _wait_for_page_ready(driver, timeout=30)
        except TimeoutException:
            print("[DEBUG post] Post detail page load timed out.")

        # Read the browser URL after clicking the timestamp.
        clicked_url = (driver.current_url or "").strip()
        post_url = _canonical_post_url(clicked_url)

        if post_url:
            print(f"[DEBUG post] Valid post URL: {post_url}")
            return post_url

        print("[DEBUG post] Clicked URL is not a post permalink: " f"{clicked_url!r}")

        # If Facebook redirected to a photo URL but the timestamp's
        # original href is a validated post permalink, use that permalink.
        safe_href = _canonical_post_url(href)

        if safe_href:
            try:
                driver.get(safe_href)
                _wait_for_page_ready(driver, timeout=30)

                post_url = _canonical_post_url(driver.current_url)

                if post_url:
                    print("[DEBUG post] Recovered validated post URL: " f"{post_url}")
                    return post_url

            except TimeoutException:
                print("[DEBUG post] Validated permalink timed out.")

        # Restore the feed before retrying; never save a photo URL.
        try:
            if driver.current_window_handle != original_handle:
                driver.close()

                if original_handle in driver.window_handles:
                    driver.switch_to.window(original_handle)

            elif driver.current_url != before_url:
                driver.back()
                _wait_for_page_ready(driver, timeout=30)

        except Exception as error:
            print(f"[DEBUG post] Could not restore the feed: {error}")

        if attempt < attempts:
            time.sleep(2)

            try:
                driver.refresh()
                _wait_for_page_ready(driver, timeout=30)
                _check_facebook_session(driver)
            except TimeoutException:
                print("[DEBUG post] Page refresh timed out.")

    raise PublishUnknownError(
        "The post may have been published, but Facebook did not provide "
        "a valid post permalink after clicking its timestamp. "
        "No photo URL was saved. Check the Page before retrying."
    )


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


# ----- Close Call Now popup -----
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


# ----- Wait for workflow transition -----
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


# ----- Wait for Post button -----
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


# ----- Wait for publish confirmation -----
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
        # Close the Call Now popup if Facebook displays it.
        try:
            if _call_now_popup_visible(current):
                try:
                    _dismiss_call_now_popup(current, timeout=2)
                except Exception:
                    pass
        except Exception:
            pass

        # Prefer an explicit success notification.
        notice = _find_publish_success_notice(current)

        if notice:
            return f"notification: {notice}"

        # Fallback: wait until the composer remains closed for 3 seconds.
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


# ----- Publish post -----
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

    # ----- Switch to Page -----
    switch_to_page(driver, page_name)

    # ----- Open Page -----
    driver.get(page_link)
    _wait_for_page_ready(driver)
    _check_facebook_session(driver)
    _dismiss_call_now_popup(driver, appearance_timeout=1)

    # ----- Open composer -----
    composer = _find_composer_trigger(driver)

    if composer is None:
        raise FacebookPostError(
            "Could not locate the Page composer in Facebook's DOM structure."
        )

    _click(composer, driver)
    _dismiss_call_now_popup(driver, appearance_timeout=3)
    dialog = _wait_for_dialog(driver)

    # ----- Import media -----
    file_input = _find_file_input(driver, dialog)

    try:
        file_input.send_keys(media_path)
    except Exception as error:
        raise FacebookPostError(
            "Could not upload media through Facebook's file input. "
            "The Windows file dialog should not be opened manually."
        ) from error

    dialog = _visible_dialog(driver) or dialog

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

    # ----- Next -> Post for photos; Next -> Next -> Post for videos -----
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

    # ----- Wait for final Post button -----
    post_button = _wait_for_post_button(
        driver,
        timeout=POST_BUTTON_TIMEOUT,
    )

    # ----- Submit post once -----
    try:
        _click_once(post_button, driver)
    except Exception as error:
        raise PublishUnknownError(
            "Facebook did not confirm whether the Post click was accepted. "
            "Check the Page before retrying to avoid publishing a duplicate."
        ) from error

    # ----- Close Call Now popup if it appears -----
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

    # ----- Wait for Facebook publish confirmation -----
    _wait_for_publish_confirmation(driver, timeout=90)


# ----- Post comment -----
def post_comment(driver, caption: str, comment: str) -> None:
    comment = str(comment or "").strip()

    if not comment:
        raise CommentPostError("Comment text is missing.")

    comment_key = _normalise(comment)
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

    # ----- Enter the entire Excel cell as one comment -----
    _click(box, driver)

    comment_lines = comment.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    for index, line in enumerate(comment_lines):
        if line:
            box.send_keys(line)

        if index < len(comment_lines) - 1:
            # Xuống dòng bên trong cùng một bình luận, không submit.
            box.send_keys(Keys.SHIFT, Keys.ENTER)

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
                "Facebook did not confirm whether the comment submission was "
                "accepted. Check the post before trying again."
            ) from error
    else:
        box.send_keys(Keys.ENTER)

    # ----- Verify the entire comment -----
    def comment_is_confirmed(_):
        try:
            current_article = _find_post_article(
                driver,
                caption,
                timeout=1,
            )

            if current_article is None:
                return False

            # Nếu nội dung vẫn nằm trong ô nhập, chưa xác nhận đã gửi.
            editors = current_article.find_elements(
                By.CSS_SELECTOR,
                "[contenteditable='true'][role='textbox'], textarea",
            )

            for item in editors:
                value = _normalise(item.text or item.get_attribute("value") or "")

                if comment_key in value:
                    return False

            return comment_key in _normalise(current_article.text)

        except StaleElementReferenceException:
            return False

    try:
        WebDriverWait(
            driver,
            20,
            poll_frequency=0.5,
        ).until(comment_is_confirmed)
    except TimeoutException as error:
        raise CommentPostError(
            "Facebook did not confirm that the entire comment was published."
        ) from error
