"""Fingerprint computation for error grouping."""
import re
from app.schema import CanonicalLog


def _normalize_message_for_fingerprint(message: str) -> str:
    """Replace numbers, UUIDs, and hex IDs with placeholders to group similar messages."""
    if not message:
        return ""
    # UUIDs
    text = re.sub(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        "<uuid>",
        message,
    )
    # Hex IDs (e.g. 0x7f8a or object ids)
    text = re.sub(r"\b0x[0-9a-fA-F]+\b", "<hex>", text)
    # Integers and numeric IDs
    text = re.sub(r"\b\d+\b", "<n>", text)
    # Optional: file paths with line numbers (e.g. file.py:123)
    text = re.sub(r":\s*<n>", ":<n>", text)
    return text.strip()


def compute_fingerprint(log: CanonicalLog) -> str:
    """Produce a stable fingerprint for grouping similar errors."""
    normalized_msg = _normalize_message_for_fingerprint(log.message)
    parts = [log.service, log.level, normalized_msg]
    return "|".join(p for p in parts if p)
