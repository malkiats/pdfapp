"""Structured logging with event sanitization."""

from __future__ import annotations

import re
from typing import Any

import structlog

# Event name must be lowercase alphanumeric + underscore, 1-64 chars.
_EVENT_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_INVALID_EVENT = "log_event_invalid"


def _sanitize_event(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Validate and sanitize the event name. Non-matching events become 'log_event_invalid'."""
    event = event_dict.get("event", "")
    if event and not _EVENT_NAME_RE.match(str(event)):
        event_dict["event"] = _INVALID_EVENT
    return event_dict


def configure_logging() -> None:
    """Set up structlog for the application."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            _sanitize_event,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = __name__) -> structlog.wrap_logger:
    """Get a structlog logger."""
    return structlog.get_logger(name)
