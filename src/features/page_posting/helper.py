import re


def clean_value(value: object) -> str:
    if value is None:
        return ""

    return str(value).strip()


def get_number(value: object) -> int | None:
    text = clean_value(value)

    if not text:
        return None

    try:
        number = float(text)
    except (TypeError, ValueError):
        return None

    if not number.is_integer():
        return None

    return int(number)


def get_id_number(value: object) -> int | float:
    text = clean_value(value)
    match = re.fullmatch(r"[A-Za-z]+-(\d+)", text)

    if not match:
        return float("inf")

    return int(match.group(1))
