import json
import logging
import time
import uuid
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from starlette.types import ASGIApp, Receive, Scope, Send

from .config import (
    IST,
    LOG_DIR,
    LOG_FILE_BACKUP_COUNT,
    LOG_FILE_MAX_BYTES,
    LOG_JSON,
    LOG_LEVEL,
)

_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


class IstFormatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt = datetime.fromtimestamp(record.created, IST)
        if datefmt:
            return dt.strftime(datefmt)
        return f"{dt.strftime('%Y-%m-%d %H:%M:%S')},{int(record.msecs):03d} {dt.strftime('%z')}"


class JsonFormatter(IstFormatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(level)
    formatter: logging.Formatter = JsonFormatter() if LOG_JSON else IstFormatter(_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    log_dir = Path(LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=LOG_FILE_MAX_BYTES,
        backupCount=LOG_FILE_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


class RequestLogMiddleware:
    """Logs one line per HTTP request: method, path, status, duration, client, request id.

    Implemented as raw ASGI (not Starlette's BaseHTTPMiddleware) because
    BaseHTTPMiddleware buffers the whole response body in memory to read it,
    which breaks streaming responses. Wrapping `send` directly lets responses
    pass through untouched while we still see the status code and inject the
    request id header.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._logger = get_logger("src.http")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = ""
        for name, value in scope.get("headers") or []:
            if name == b"x-request-id":
                request_id = value.decode("latin-1")
                break
        if not request_id:
            request_id = str(uuid.uuid4())

        client = scope.get("client")
        client_host = client[0] if client else ""
        method = scope.get("method", "")
        path = scope.get("path", "")
        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: dict) -> None:
            # Only the "http.response.start" ASGI event carries status + headers;
            # body chunks ("http.response.body") pass through send() unmodified.
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers = list(message.get("headers") or [])
                headers.append((b"x-request-id", request_id.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            self._logger.exception(
                "request failed method=%s path=%s duration_ms=%.1f client=%s request_id=%s",
                method,
                path,
                duration_ms,
                client_host,
                request_id,
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        self._logger.info(
            "request method=%s path=%s status=%s duration_ms=%.1f client=%s request_id=%s",
            method,
            path,
            status_code,
            duration_ms,
            client_host,
            request_id,
        )
