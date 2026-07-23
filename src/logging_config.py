"""Application logging with credential redaction at the output boundary."""

import logging
import re
import sys
from collections.abc import Iterable
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TextIO

from pythonjsonlogger import jsonlogger


REDACTED = "[REDACTED]"

_SENSITIVE_PARAMETER_PATTERN = re.compile(
    r"(?P<prefix>\b(?:api[_-]?key|access[_-]?token|"
    r"client[_-]?secret|token|password)\b"
    r"(?:%3d|[\"']?\s*[:=]\s*[\"']?))"
    r"(?P<value>[^&\s,;#\"'}]+)",
    re.IGNORECASE,
)
_AUTHORIZATION_PATTERN = re.compile(
    r"(?P<prefix>\b(?:proxy-)?authorization\b[\"']?\s*[:=]\s*[\"']?"
    r"(?:(?:bearer|basic)\s+)?)"
    r"(?P<value>[^&\s,;#\"'}]+)",
    re.IGNORECASE,
)
_URL_PASSWORD_PATTERN = re.compile(
    r"(?P<prefix>\b[a-z][a-z0-9+.-]*://[^:/@\s]+:)"
    r"(?P<value>[^@/\s]+)(?=@)",
    re.IGNORECASE,
)
_TELEGRAM_BOT_TOKEN_PATTERN = re.compile(
    r"(?P<prefix>https://api\.telegram\.org/bot)"
    r"(?P<value>[^/\s\"']+)",
    re.IGNORECASE,
)


def _normalize_sensitive_values(values: Iterable[object]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        values = (values,)
    return tuple(
        sorted(
            {
                str(value)
                for value in values
                if value is not None and str(value)
            },
            key=len,
            reverse=True,
        )
    )


def _mask_pattern(match: re.Match) -> str:
    return f"{match.group('prefix')}{REDACTED}"


def redact_credentials(
    message: object,
    sensitive_values: Iterable[object] = (),
) -> str:
    """Return log text with known secrets and credential fields masked."""
    redacted = str(message)
    for sensitive_value in _normalize_sensitive_values(sensitive_values):
        redacted = redacted.replace(sensitive_value, REDACTED)

    for pattern in (
        _SENSITIVE_PARAMETER_PATTERN,
        _AUTHORIZATION_PATTERN,
        _URL_PASSWORD_PATTERN,
        _TELEGRAM_BOT_TOKEN_PATTERN,
    ):
        redacted = pattern.sub(_mask_pattern, redacted)
    return redacted


class RedactingJsonFormatter(jsonlogger.JsonFormatter):
    """JSON formatter that sanitizes the complete rendered log record."""

    def __init__(
        self,
        *args,
        sensitive_values: Iterable[object] = (),
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._sensitive_values = _normalize_sensitive_values(sensitive_values)

    def format(self, record: logging.LogRecord) -> str:
        rendered = super().format(record)
        return redact_credentials(rendered, self._sensitive_values)


def configure_logging(
    *,
    level: str | int,
    sensitive_values: Iterable[object] = (),
    stream: TextIO | None = None,
    file_path: str | Path | None = None,
    file_max_bytes: int = 10 * 1024 * 1024,
    file_backup_count: int = 5,
) -> None:
    """Install protected console and optional rotating-file root handlers."""
    formatter = RedactingJsonFormatter(sensitive_values=sensitive_values)
    console_handler = logging.StreamHandler(
        sys.stdout if stream is None else stream
    )
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)

    if file_path is not None:
        log_path = Path(file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=file_max_bytes,
            backupCount=file_backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    root_logger.setLevel(level)
