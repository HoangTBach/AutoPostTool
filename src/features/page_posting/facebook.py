import time

try:
    from selenium.common.exceptions import (
        StaleElementReferenceException,
        TimeoutException,
    )
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
except ImportError:
    StaleElementReferenceException = TimeoutException = Exception
    By = Keys = WebDriverWait = None


class FacebookPostError(RuntimeError):
    pass


class PublishUnknownError(FacebookPostError):
    pass


class CommentPostError(RuntimeError):
    pass


CREATE_POST_LABELS = {
    "create post",
    "create a post",
    "tạo bài viết",
    "write something",
    "bạn viết gì đi",
    "bạn đang nghĩ gì",
}

PHOTO_LABELS = {
    "photo/video",
    "photo / video",
    "ảnh/video",
    "ảnh và video",
}

POST_LABELS = {"post", "đăng", "publish", "chia sẻ"}
COMMENT_LABELS = {"comment", "bình luận", "send", "gửi"}


def _require_selenium() -> None:
    if By is None:
        raise RuntimeError("Selenium is missing. Run: python -m pip install selenium")


def _normalise(value: str) -> str:
    return " ".join((value or "").casefold().split())


def _visible(element) -> bool:
    try:
        return element.is_displayed()
    except Exception:
        return False


def _click(element, driver) -> None:
    try:
        element.click()
    except Exception:
        driver.execute_script("arguments[0].click();", element)


def _find_clickable(driver, labels: set[str], root=None):
    search_root = root or driver
    elements = search_root.find_elements(
        By.XPATH,
        ".//*[@role='button' or self::button or @role='menuitem']",
    )
    wanted = {_normalise(label) for label in labels}

    for element in reversed(elements):
        if not _visible(element):
            continue

        text = _normalise(element.text)
        aria = _normalise(element.get_attribute("aria-label"))
        title = _normalise(element.get_attribute("title"))

        if any(
            label == value or label.startswith(value)
            for value in wanted
            for label in (text, aria, title)
            if label
        ):
            try:
                if element.is_enabled():
                    return element
            except Exception:
                return element

    return None


def _visible_dialog(driver):
    dialogs = [
        item
        for item in driver.find_elements(By.XPATH, "//*[@role='dialog']")
        if _visible(item)
    ]
    return dialogs[-1] if dialogs else None


def _wait_for_dialog(driver, timeout=15):
    return WebDriverWait(driver, timeout).until(
        lambda current: _visible_dialog(current)
    )


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


def _find_file_input(driver, dialog, timeout=15):
    def locate(_):
        roots = [dialog, driver] if dialog is not None else [driver]

        for root in roots:
            inputs = root.find_elements(By.CSS_SELECTOR, "input[type='file']")
            if inputs:
                return inputs[-1]

        return False

    return WebDriverWait(driver, timeout).until(locate)


def _find_post_article(driver, caption: str, timeout=12):
    snippet = " ".join(caption.split())[:60]
    if not snippet:
        return None

    def locate(current):
        articles = current.find_elements(By.XPATH, "//*[@role='article']")

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
                for part in ("/posts/", "/permalink/", "story_fbid=", "/photo/")
            ):
                return href
    except Exception:
        pass

    return ""


def publish_photo(driver, row: dict) -> str:
    _require_selenium()

    page_link = str(row.get("page_link") or "").strip()
    caption = str(row.get("caption") or "").strip()
    image_path = str(row.get("_validated_image") or row.get("image") or "").strip()

    driver.get(page_link)

    WebDriverWait(driver, 30).until(
        lambda current: current.execute_script("return document.readyState")
        == "complete"
    )

    current_url = driver.current_url.casefold()
    if "facebook.com/login" in current_url or "checkpoint" in current_url:
        raise FacebookPostError(
            "The AdsPower profile is not logged in to Facebook "
            "or requires a checkpoint."
        )

    composer = _find_clickable(driver, CREATE_POST_LABELS)

    if composer is None:
        textboxes = [
            item
            for item in driver.find_elements(
                By.CSS_SELECTOR,
                "[contenteditable='true'][role='textbox']",
            )
            if _visible(item)
        ]
        if textboxes:
            composer = textboxes[-1]

    if composer is None:
        raise FacebookPostError("Could not find the Facebook Page post composer.")

    _click(composer, driver)
    dialog = _wait_for_dialog(driver)

    photo_button = _find_clickable(driver, PHOTO_LABELS, dialog)
    if photo_button is None:
        raise FacebookPostError(
            "Could not find the Photo/Video button in the composer."
        )

    _click(photo_button, driver)
    dialog = _visible_dialog(driver) or dialog

    file_input = _find_file_input(driver, dialog)
    file_input.send_keys(image_path)

    def locate_caption(_):
        try:
            current_dialog = _visible_dialog(driver) or dialog
            return _find_caption_box(current_dialog) or False
        except StaleElementReferenceException:
            return False

    caption_box = WebDriverWait(driver, 20).until(locate_caption)
    _click(caption_box, driver)
    caption_box.send_keys(caption)

    post_button = _find_clickable(driver, POST_LABELS, dialog)
    if post_button is None:
        raise FacebookPostError("Could not find the Post button.")

    try:
        _click(post_button, driver)
    except Exception as error:
        raise PublishUnknownError(
            "Facebook did not confirm whether the Post click was accepted."
        ) from error

    try:
        WebDriverWait(driver, 30).until(
            lambda current: _visible_dialog(current) is None
        )
    except TimeoutException as error:
        raise PublishUnknownError(
            "Facebook did not close the post composer after submission. "
            "Check the Page before retrying."
        ) from error

    article = _find_post_article(driver, caption)
    if article is None:
        raise PublishUnknownError(
            "The post may have been submitted, but could not be verified."
        )

    return _find_post_url(article)


def post_comment(driver, caption: str, comment: str) -> None:
    _require_selenium()

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

    if box is None:
        open_comment = _find_clickable(
            driver,
            {"comment", "bình luận", "write a comment", "viết bình luận"},
            article,
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

    _click(box, driver)
    box.send_keys(comment)

    submit = _find_clickable(driver, COMMENT_LABELS, article)
    if submit is not None:
        _click(submit, driver)
    else:
        box.send_keys(Keys.ENTER)

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
