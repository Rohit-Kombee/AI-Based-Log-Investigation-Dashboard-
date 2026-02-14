"""Ingest: normalize, validate, store."""
import json
import logging
from datetime import datetime
from typing import Any, List, Dict

from app.db import get_connection, add_rejected_count

logger = logging.getLogger("app.ingest")

# Recent ingest results for dashboard (last N batches)
_RECENT_INGESTS: List[Dict[str, Any]] = []
_RECENT_MAX = 50
# Recent rejected log entries for drill-down (last N)
_RECENT_REJECTED: List[Dict[str, Any]] = []
_RECENT_REJECTED_MAX = 100
from app.fingerprint import compute_fingerprint
from app.normalize import normalize
from app.schema import CanonicalLog
from app.validate import validate_log


def store_log(conn, log: CanonicalLog, fingerprint: str, group_id: str) -> None:
    """Insert one canonical log into the database."""
    conn.execute(
        """
        INSERT INTO logs (timestamp, level, message, service, correlation_id, metadata, raw, fingerprint, group_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            log.timestamp.isoformat(),
            log.level,
            log.message,
            log.service,
            log.correlation_id,
            json.dumps(log.metadata) if log.metadata else "{}",
            log.raw,
            fingerprint,
            group_id,
        ),
    )


def process_logs(raw_logs: list[dict[str, Any]]) -> tuple[int, int, list[dict[str, Any]]]:
    """
    Normalize, validate, and store logs. Returns (accepted, rejected, errors).
    """
    accepted = 0
    rejected = 0
    errors: list[dict[str, Any]] = []

    with get_connection() as conn:
        for i, raw in enumerate(raw_logs):
            if not isinstance(raw, dict):
                rejected += 1
                err_msg = "Each log must be a JSON object"
                errors.append({"index": i, "error": err_msg})
                logger.warning("[INGEST] REJECT | index=%s | reason=%s", i, err_msg)
                continue
            try:
                canonical = normalize(raw)
            except Exception as e:
                rejected += 1
                err_msg = f"Normalization failed: {e}"
                errors.append({"index": i, "error": err_msg})
                logger.warning("[INGEST] REJECT | index=%s | reason=%s", i, err_msg)
                continue

            valid, err_list = validate_log(canonical)
            if not valid:
                rejected += 1
                err_msg = "; ".join(err_list)
                errors.append({"index": i, "error": err_msg})
                logger.warning("[INGEST] REJECT | index=%s | reason=%s", i, err_msg)
                continue

            fingerprint = compute_fingerprint(canonical)
            group_id = fingerprint  # use fingerprint as group_id for simplicity

            try:
                store_log(conn, canonical, fingerprint, group_id)
                conn.commit()
                accepted += 1
            except Exception as e:
                rejected += 1
                err_msg = f"Storage failed: {e}"
                errors.append({"index": i, "error": err_msg})
                logger.warning("[INGEST] REJECT | index=%s | reason=%s", i, err_msg)

    if rejected > 0:
        logger.info("[INGEST] BATCH | accepted=%s | rejected=%s | total=%s", accepted, rejected, accepted + rejected)
    # Persist total rejected (all time)
    if rejected > 0:
        add_rejected_count(rejected)
    # Store recent rejected for drill-down
    for err in errors:
        _RECENT_REJECTED.append({
            "at": datetime.utcnow().isoformat() + "Z",
            "error": err.get("error", ""),
            "index": err.get("index", -1),
        })
        if len(_RECENT_REJECTED) > _RECENT_REJECTED_MAX:
            _RECENT_REJECTED.pop(0)
    # Record batch for dashboard
    _RECENT_INGESTS.append({
        "accepted": accepted,
        "rejected": rejected,
        "at": datetime.utcnow().isoformat() + "Z",
    })
    if len(_RECENT_INGESTS) > _RECENT_MAX:
        _RECENT_INGESTS.pop(0)

    return accepted, rejected, errors


def get_recent_ingests() -> List[Dict[str, Any]]:
    """Return last N ingest batch results (for dashboard)."""
    return list(_RECENT_INGESTS)


def get_recent_rejected(limit: int = 10) -> List[Dict[str, Any]]:
    """Return last N rejected entries for drill-down."""
    return list(_RECENT_REJECTED)[-limit:][::-1]
