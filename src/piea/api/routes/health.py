"""Health check endpoint.

GET /health  — used by Docker, load balancers, and uptime monitors.
Returns 200 when the app is running; checks DB connectivity for the
detailed probe.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from piea.db.session import get_db

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    database: str
    version: str = "0.1.0"


@router.get("/health", response_model=HealthResponse, summary="Health check")
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """Return service health status.

    - **status**: "ok" if the application is running
    - **database**: "ok" if a DB round-trip succeeds, otherwise "unavailable"
    """
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "unavailable"

    return HealthResponse(status="ok", database=db_status)
