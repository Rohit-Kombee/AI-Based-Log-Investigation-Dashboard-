"""Convert raw log payloads to canonical schema."""
import re
from datetime import datetime
from typing import Any

from app.schema import CanonicalLog


# Common aliases from various log formats
LEVEL_ALIASES = {
    "lvl", "level", "severity", "log_level", "severityLevel",
    "logLevel", "severity_level",
}
MESSAGE_ALIASES = {"msg", "message", "text", "log", "description"}
SERVICE_ALIASES = {"service", "service_name", "app", "application", "source", "logger"}
CORRELATION_ALIASES = {"correlation_id", "correlationId", "request_id", "trace_id", "traceId", "requestId"}
TIMESTAMP_ALIASES = {"timestamp", "time", "ts", "@timestamp", "datetime", "date"}


def _find_value(data: dict[str, Any], *keys: str) -> Any:
    """Return first value found for any of the given keys (case-insensitive)."""
    data_lower = {k.lower(): v for k, v in data.items()}
    for key in keys:
        if key.lower() in data_lower:
            return data_lower[key.lower()]
    return None


def _coerce_timestamp(ts: Any) -> datetime:
    """Parse timestamp from int (epoch), float, or ISO string."""
    if ts is None:
        return datetime.utcnow()
    if isinstance(ts, (int, float)):
        if ts > 1e12:  # milliseconds
            ts = ts / 1000.0
        return datetime.utcfromtimestamp(ts)
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            pass
        try:
            return datetime.utcfromtimestamp(float(ts))
        except Exception:
            pass
    return datetime.utcnow()


def _coerce_level(level: Any) -> str:
    """Normalize level to uppercase string."""
    if level is None:
        return "INFO"
    s = str(level).strip().upper()
    return s if s else "INFO"


def _coerce_string(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip()


def normalize(raw: dict[str, Any]) -> CanonicalLog:
    """Convert a raw log object to canonical schema."""
    ts = _find_value(raw, *TIMESTAMP_ALIASES)
    level = _find_value(raw, *LEVEL_ALIASES)
    message = _find_value(raw, *MESSAGE_ALIASES)
    service = _find_value(raw, *SERVICE_ALIASES)
    correlation_id = _find_value(raw, *CORRELATION_ALIASES)

    # Build metadata from remaining keys (exclude known ones)
    known = set()
    for aliases in (LEVEL_ALIASES, MESSAGE_ALIASES, SERVICE_ALIASES, CORRELATION_ALIASES, TIMESTAMP_ALIASES):
        known.update(aliases)
    data_lower = {k.lower(): (k, v) for k, v in raw.items()}
    metadata = {}
    for k, v in raw.items():
        if k.lower() not in {a.lower() for a in known} and v is not None:
            metadata[k] = v

    return CanonicalLog(
        timestamp=_coerce_timestamp(ts),
        level=_coerce_level(level),
        message=_coerce_string(message) or "(no message)",
        service=_coerce_string(service) or "unknown",
        correlation_id=_coerce_string(correlation_id) or "",
        metadata=metadata,
        raw=str(raw) if raw else "",
    )
