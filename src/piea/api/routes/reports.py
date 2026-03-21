"""Report retrieval endpoint (scaffold — full implementation in T5.4)."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/{scan_id}", summary="Get scan report")
async def get_report(scan_id: UUID) -> dict:
    """Retrieve the full report for a completed scan.

    Full implementation deferred to T5.4 once the scoring engine (Phase 4)
    and graph serializer (T2.11) are available.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Report endpoint will be implemented in T5.4.",
    )
