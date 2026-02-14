"""Server-side log generator: produces log batches and feeds them to ingest (no HTTP)."""
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app import ingest

SERVICES = ["api-gateway", "auth-service", "user-service", "order-service", "payment-service"]
LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
MESSAGES = [
    "Connection timeout to database",
    "User login failed for user_id=%s",
    "Rate limit exceeded for IP %s",
    "File not found: %s",
    "OutOfMemoryError in worker %s",
    "Invalid token received",
    "Request completed in %s ms",
    "Health check passed",
    "Cache miss for key %s",
]

SCENARIOS = {
    "normal": {"error_spike": False, "malformed_fraction": 0.0, "alt_fraction": 0.0},
    "error_spike": {"error_spike": True, "malformed_fraction": 0.0, "alt_fraction": 0.0},
    "malformed": {"error_spike": False, "malformed_fraction": 0.3, "alt_fraction": 0.0},
    "alt_fields": {"error_spike": False, "malformed_fraction": 0.0, "alt_fraction": 1.0},
    "mixed": {"error_spike": False, "malformed_fraction": 0.1, "alt_fraction": 0.4},
}


def one_log(
    level: Optional[str] = None,
    service: Optional[str] = None,
    use_correlation: bool = True,
    malformed: bool = False,
    alt_fields: bool = False,
) -> Dict[str, Any]:
    """Generate one raw log (same logic as generator/main.py)."""
    level = level or random.choice(LEVELS)
    service = service or random.choice(SERVICES)
    msg_tpl = random.choice(MESSAGES)
    msg = msg_tpl % (random.randint(1, 99999),) if "%s" in msg_tpl else msg_tpl
    ts = datetime.utcnow() - timedelta(seconds=random.randint(0, 3600))
    correlation = f"req-{random.randint(1000, 9999)}" if use_correlation else None

    if malformed:
        return {"level": "INVALID", "message": ""}
    if alt_fields:
        return {
            "lvl": level,
            "msg": msg,
            "service_name": service,
            "ts": int(ts.timestamp() * 1000),
            "traceId": correlation,
        }
    return {
        "timestamp": ts.isoformat() + "Z",
        "level": level,
        "message": msg,
        "service": service,
        "correlation_id": correlation,
    }


def run_scenario(
    scenario_id: str,
    batches: int = 20,
    batch_size: int = 5,
) -> Dict[str, Any]:
    """
    Run a generator scenario: produce batches and call ingest.process_logs for each.
    Returns total_accepted, total_rejected, batches_sent, message.
    """
    opts = SCENARIOS.get(scenario_id, SCENARIOS["normal"])
    total_accepted = 0
    total_rejected = 0
    batches_sent = 0
    for _ in range(batches):
        batch: List[Dict[str, Any]] = []
        for _ in range(batch_size):
            malformed = random.random() < opts["malformed_fraction"]
            alt = random.random() < opts["alt_fraction"] and not malformed
            level = "ERROR" if opts["error_spike"] else None
            batch.append(one_log(malformed=malformed, alt_fields=alt, level=level))
        accepted, rejected, _ = ingest.process_logs(batch)
        total_accepted += accepted
        total_rejected += rejected
        batches_sent += 1
    return {
        "total_accepted": total_accepted,
        "total_rejected": total_rejected,
        "batches_sent": batches_sent,
        "message": f"Sent {batches_sent} batches; {total_accepted} accepted, {total_rejected} rejected.",
    }
