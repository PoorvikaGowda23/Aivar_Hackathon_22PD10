"""
Structured JSON-lines logging for the compliance card service.

Every log line is a single JSON object written to stdout, which works
well with Render.com's log aggregation and any log-drain service.

Format per line:
  {"time": "...", "level": "INFO", "logger": "app", "message": "...", ...extra_fields}

Usage:
  from logging_config import setup_logging
  logger = setup_logging()
  logger.info("request completed", extra={"request_id": "abc", "duration_ms": 45})
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

# Fields that are internal to the LogRecord and should NOT be forwarded
_INTERNAL_FIELDS = frozenset({
    "args", "asctime", "created", "exc_info", "exc_text",
    "filename", "funcName", "id", "levelname", "levelno",
    "lineno", "module", "msecs", "message", "msg", "name",
    "pathname", "process", "processName", "relativeCreated",
    "stack_info", "thread", "threadName", "taskName",
})


class _JsonFormatter(logging.Formatter):
    """Formats every log record as a single JSON object on one line."""

    def format(self, record: logging.LogRecord) -> str:
        # Base fields always present
        entry: dict = {
            "time":    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level":   record.levelname,
            "logger":  record.name,
            "message": record.getMessage(),
        }

        # Attach exception traceback when present
        if record.exc_info:
            entry["exc_info"] = self.formatException(record.exc_info)

        # Merge any extra= fields the caller passed in
        for key, val in record.__dict__.items():
            if key not in _INTERNAL_FIELDS and not key.startswith("_"):
                try:
                    json.dumps(val)        # guard: only include JSON-serialisable values
                    entry[key] = val
                except TypeError:
                    entry[key] = str(val)

        return json.dumps(entry, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    Configures root logger with JSON output to stdout.

    Call once at application startup. Returns the 'app' logger.
    Suppresses noisy third-party loggers that would otherwise flood stdout.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())

    root = logging.getLogger()
    # Avoid adding duplicate handlers on hot-reload
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Quiet down libraries that are too chatty at DEBUG/INFO
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return logging.getLogger("app")
