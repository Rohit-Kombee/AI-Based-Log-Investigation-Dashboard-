"""Canonical log schema and API request/response models."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel, Field


# ----- Canonical (internal) log schema -----


class CanonicalLog(BaseModel):
    """Normalized log entry used for storage and processing."""

    timestamp: datetime
    level: str
    message: str
    service: str = "unknown"
    correlation_id: str = ""  # optional: use "" when absent (avoids Optional for OpenAPI on Py3.9)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    raw: str = ""  # original payload as string for debugging; "" when absent


# ----- Raw ingest (accept various shapes) -----


class RawLogInput(BaseModel):
    """Single raw log as sent to /ingest. Flexible field names."""

    class Config:
        extra = "allow"  # accept any extra fields


# ----- API request/response -----


class IngestRequest(BaseModel):
    """Request body for POST /ingest."""

    logs: List[Dict[str, Any]] = Field(..., description="One or more raw log objects")


class IngestResponse(BaseModel):
    """Response from POST /ingest."""

    accepted: int
    rejected: int
    errors: List[Dict[str, Any]] = Field(default_factory=list)


class NormalizeRequest(BaseModel):
    """Request for POST /normalize."""

    log: Dict[str, Any]


class ValidateRequest(BaseModel):
    """Request for POST /validate."""

    log: Dict[str, Any]


class ValidateResponse(BaseModel):
    """Response from POST /validate."""

    valid: bool
    errors: List[str] = Field(default_factory=list)


class GroupItem(BaseModel):
    """One error group."""

    group_id: str
    fingerprint: str
    count: int
    level: str
    service: str
    sample_message: str
    first_seen: datetime
    last_seen: datetime


class GroupResponse(BaseModel):
    """Response from GET /group."""

    groups: List[GroupItem]
    total_groups: int


class SpikeItem(BaseModel):
    """One detected spike."""

    group_id: str
    service: str
    level: str
    window_start: str
    count: int
    baseline_avg: float
    ratio: float


class SpikesResponse(BaseModel):
    """Response from GET /spikes."""

    spikes: List[SpikeItem]


class InsightsResponse(BaseModel):
    """Response from GET /insights."""

    summary: str
    top_groups: List[Dict[str, Any]] = Field(default_factory=list)
    spikes: List[Dict[str, Any]] = Field(default_factory=list)
