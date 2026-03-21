"""Pydantic models for scan API responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ScanCreatedResponse(BaseModel):
    """Response body for POST /api/v1/scans (201 Created)."""

    scan_id: UUID
    status: str
    consent_record_id: UUID
    message: str = "Scan queued successfully."


class ScanStatusResponse(BaseModel):
    """Response body for GET /api/v1/scans/{scan_id}."""

    scan_id: UUID
    status: str          # queued | running | completed | failed
    risk_score: int | None
    risk_tier: str | None
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    created_at: datetime
