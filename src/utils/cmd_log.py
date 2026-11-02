import sys
import traceback
from datetime import datetime


def cmd_log(
    level: str,
    message: str,
    error: BaseException | None = None,
) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")

    if error is not None:
        message = f"{message}: {type(error).__name__}"

    print(
        f"[{timestamp}] [{level.upper()}] {message}",
        file=sys.stdout,
        flush=True,
    )

    if error is not None:
        traceback.print_exception(
            type(error),
            error,
            error.__traceback__,
            file=sys.stdout,
        )
