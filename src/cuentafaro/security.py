from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

SENSITIVE_KEY_PATTERN = re.compile(
    r"(?i)(\b(?:authorization|cookie|password|passwd|secret|token|api[_-]?key)\b"
    r"[\"']?\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^,;\n]+)"
)
BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
SENSITIVE_NAME_PATTERN = re.compile(
    r"(?i)authorization|cookie|password|passwd|secret|token|api[_-]?key"
)
REDACTED = "[REDACTED]"


def redact_text(value: str) -> str:
    redacted = BEARER_PATTERN.sub(f"Bearer {REDACTED}", value)
    return SENSITIVE_KEY_PATTERN.sub(lambda match: f"{match.group(1)}{REDACTED}", redacted)


def redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: REDACTED if SENSITIVE_NAME_PATTERN.search(str(key)) else redact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(str(record.msg))
        if record.args:
            record.args = redact_value(record.args)
        return True


def install_log_redaction() -> None:
    for logger_name in ("", "uvicorn", "uvicorn.error", "uvicorn.access", "cuentafaro"):
        logger = logging.getLogger(logger_name)
        for handler in logger.handlers:
            if not any(isinstance(item, SensitiveDataFilter) for item in handler.filters):
                handler.addFilter(SensitiveDataFilter())


def _apply_private_mode(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except OSError:
        pass


def prepare_private_file(path: Path) -> Path:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    _apply_private_mode(path.parent, 0o700)
    path.touch(mode=0o600, exist_ok=True)
    _apply_private_mode(path, 0o600)
    return path


def write_private_text(path: Path, content: str, *, overwrite: bool = False) -> Path:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    _apply_private_mode(path.parent, 0o700)
    flags = os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if overwrite else os.O_EXCL)
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(content)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    _apply_private_mode(path, 0o600)
    return path
