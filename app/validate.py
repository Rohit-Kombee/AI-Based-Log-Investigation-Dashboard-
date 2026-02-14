"""Validate raw or normalized logs."""
import json
from typing import Any

from app.config import settings
from app.schema import CanonicalLog


def validate_log(log: Any) -> tuple[bool, list[str]]:
    """
    Validate a log (dict or CanonicalLog). Returns (valid, list of error messages).
    """
    errors: list[str] = []

    if isinstance(log, CanonicalLog):
        level = log.level
        message = log.message
        payload_size = len((log.raw or "").encode("utf-8")) + len(log.message.encode("utf-8"))
    elif isinstance(log, dict):
        level = (log.get("level") or log.get("lvl") or log.get("severity") or "INFO")
        if hasattr(level, "upper"):
            level = str(level).upper()
        else:
            level = "INFO"
        message = str(log.get("message") or log.get("msg") or log.get("text") or "")
        try:
            payload_size = len(json.dumps(log).encode("utf-8"))
        except Exception:
            payload_size = 0
    else:
        errors.append("Log must be a dict or CanonicalLog")
        return False, errors

    if level not in settings.allowed_levels:
        errors.append(f"Invalid level: {level}. Allowed: {settings.allowed_levels}")

    if payload_size > settings.max_log_size_bytes:
        errors.append(f"Log payload too large: {payload_size} > {settings.max_log_size_bytes}")

    if not message and not isinstance(log, dict):
        errors.append("Message is required")

    return len(errors) == 0, errors
