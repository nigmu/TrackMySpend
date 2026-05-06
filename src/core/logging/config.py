# src/core/logging/config.py
import logging
import os


def _log_level() -> int:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    return getattr(logging, level_name, logging.INFO)


def configure_logging() -> None:
    """
    Central logging bootstrap.
    Call once during app startup.
    """
    root = logging.getLogger()
    if root.handlers:
        # Avoid duplicate handlers on reload/dev restarts.
        return

    root.setLevel(_log_level())

    fmt = os.getenv(
        "LOG_FORMAT",
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    formatter = logging.Formatter(fmt=fmt)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    if os.getenv("LOG_TO_FILE", "0") == "1":
        log_path = os.getenv("LOG_FILE_PATH", "logs/app.log")
        log_dir = os.path.dirname(log_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    # Suppress verbose third-party logs that can include sensitive OAuth details.
    logging.getLogger("requests_oauthlib").setLevel(logging.WARNING)
    logging.getLogger("oauthlib").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)