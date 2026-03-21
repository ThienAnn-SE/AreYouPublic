"""FastAPI application entry point for PIEA."""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from piea.api.routes import health, scans, reports
from piea.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Run startup and shutdown logic around the app's lifetime."""
    # Startup: nothing yet — DB tables are managed by Alembic migrations.
    yield
    # Shutdown: dispose the connection pool cleanly.
    from piea.db.session import engine
    await engine.dispose()


app = FastAPI(
    title="Public Information Exposure Analyzer",
    description=(
        "A consent-gated OSINT aggregation tool that builds an identity graph "
        "from publicly available sources and produces a risk-scored exposure report."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server (Phase 6)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(scans.router)
app.include_router(reports.router)
