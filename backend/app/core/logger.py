"""
Structured JSON logging configuration for LogiScan.
Produces machine-parseable logs with consistent schema for monitoring.
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class JSONFormatter(logging.Formatter):
    """
    Custom formatter that outputs log records as JSON objects.
    Compatible with log aggregation systems like ELK, Datadog, and CloudWatch.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Include exception info if present
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = {
                "type": type(record.exc_info[1]).__name__,
                "message": str(record.exc_info[1]),
            }

        # Include extra fields added via `extra=` kwarg
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)

        return json.dumps(log_entry, default=str)


def setup_logging(level: str = "INFO") -> None:
    """
    Configure root logger with JSON formatting.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR)
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, level.upper()))

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized at level {level.upper()}.")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    Convenience wrapper around logging.getLogger.
    """
    return logging.getLogger(name)
