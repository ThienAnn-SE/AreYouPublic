"""Scan lifecycle endpoints.

POST /api/v1/scans        — create a new scan (requires consent)
GET  /api/v1/scans/{id}   — poll scan status
"""

import hashlib
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from piea.api.dependencies import get_client_ip, get_consent_service
from piea.api.schemas.scan_request import ScanRequest
from piea.api.schemas.scan_response import ScanCreatedResponse, ScanStatusResponse
from piea.core.consent import ConsentError, ConsentInput, ConsentService
from piea.db.models import Scan
from piea.db.session import get_db

router = APIRouter(prefix="/api/v1/scans", tags=["scans"])


def _hash(value: str | None) -> str | None:
    """SHA-256 hash a string for storage (never store raw PII)."""
    if value is None:
        return None
    return hashlib.sha256(value.encode()).hexdigest()


@router.post(
    "",
    response_model=ScanCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new scan",
)
async def create_scan(
    body: ScanRequest,
    client_ip: str = Depends(get_client_ip),
    consent_service: ConsentService = Depends(get_consent_service),
    db: AsyncSession = Depends(get_db),
) -> ScanCreatedResponse:
    """Submit a new scan request.

    The consent attestation is validated first. If valid, a ConsentRecord is
    persisted and a Scan row is created in 'queued' status. The actual scan
    work is dispatched to Celery (wired up in T5.1).
    """
    # 1. Build and validate the consent record.
    try:
        consent_input = ConsentInput(
            attestation_type=body.consent.attestation_type,
            operator_name=body.consent.operator_name,
            operator_ip=client_ip,
            consent_text_version=body.consent.consent_text_version,
        )
        consent_record = await consent_service.create(consent_input)
    except ConsentError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # 2. Create the Scan row (status=queued). PII fields are stored hashed.
    scan = Scan(
        consent_record_id=consent_record.id,
        status="queued",
        input_name_hash=_hash(body.target_name),
        input_email_hash=_hash(str(body.target_email) if body.target_email else None),
        input_username=body.target_username or "",
        modules_config={
            "modules": body.modules,
            "max_depth": body.max_depth,
            "has_email": body.target_email is not None,
            "has_domain": body.target_domain is not None,
        },
    )
    db.add(scan)
    await db.flush()

    # 3. TODO (T5.1): dispatch Celery task here.
    # scan_task.delay(str(scan.id))

    return ScanCreatedResponse(
        scan_id=scan.id,
        status=scan.status,
        consent_record_id=consent_record.id,
    )


@router.get(
    "/{scan_id}",
    response_model=ScanStatusResponse,
    summary="Get scan status",
)
async def get_scan_status(
    scan_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ScanStatusResponse:
    """Poll the status of a scan by its ID."""
    result = await db.execute(select(Scan).where(Scan.id == scan_id))
    scan = result.scalar_one_or_none()

    if scan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan {scan_id} not found.",
        )

    return ScanStatusResponse(
        scan_id=scan.id,
        status=scan.status,
        risk_score=scan.risk_score,
        risk_tier=scan.risk_tier,
        started_at=scan.started_at,
        completed_at=scan.completed_at,
        error_message=scan.error_message,
        created_at=scan.created_at,
    )
