"""Log generator: POSTs sample/malformed logs to /ingest for testing."""
import os
import random
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    sys.exit(1)

INGEST_URL = os.environ.get("INGEST_URL", "http://127.0.0.1:5000/ingest")
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


def one_log(
    level: Optional[str] = None,
    service: Optional[str] = None,
    use_correlation: bool = True,
    malformed: bool = False,
    alt_fields: bool = False,
) -> Dict[str, Any]:
    """Generate one raw log (various shapes)."""
    level = level or random.choice(LEVELS)
    service = service or random.choice(SERVICES)
    msg_tpl = random.choice(MESSAGES)
    msg = msg_tpl % (random.randint(1, 99999),) if "%s" in msg_tpl else msg_tpl
    ts = datetime.utcnow() - timedelta(seconds=random.randint(0, 3600))
    correlation = f"req-{random.randint(1000, 9999)}" if use_correlation else None

    if malformed:
        return {"level": "INVALID", "message": ""}  # invalid level, empty message
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


def send_batch(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """POST logs to /ingest."""
    r = requests.post(INGEST_URL, json={"logs": logs}, timeout=10)
    r.raise_for_status()
    return r.json()


def run(
    count: int = 20,
    batch_size: int = 5,
    error_spike: bool = False,
    malformed_fraction: float = 0.0,
    alt_fraction: float = 0.3,
):
    """Generate and send logs. If error_spike, send many ERROR logs in a short time."""
    total_sent = 0
    for _ in range(count):
        batch = []
        for _ in range(batch_size):
            malformed = random.random() < malformed_fraction
            alt = random.random() < alt_fraction and not malformed
            level = "ERROR" if error_spike else None
            batch.append(one_log(malformed=malformed, alt_fields=alt, level=level))
        try:
            result = send_batch(batch)
            total_sent += result.get("accepted", 0)
            print(f"  accepted={result.get('accepted')}, rejected={result.get('rejected')}")
        except Exception as e:
            print(f"  error: {e}")
        time.sleep(0.1)
    print(f"Total accepted: {total_sent}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("-n", "--count", type=int, default=20, help="Number of batches")
    p.add_argument("-b", "--batch-size", type=int, default=5, help="Logs per batch")
    p.add_argument("--error-spike", action="store_true", help="Emit mostly ERROR logs")
    p.add_argument("--malformed", type=float, default=0.0, help="Fraction of malformed logs (0-1)")
    p.add_argument("--alt", type=float, default=0.3, help="Fraction with alternate field names")
    args = p.parse_args()
    run(
        count=args.count,
        batch_size=args.batch_size,
        error_spike=args.error_spike,
        malformed_fraction=args.malformed,
        alt_fraction=args.alt,
    )
