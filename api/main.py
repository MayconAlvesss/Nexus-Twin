"""
NexusTwin — FastAPI Application
=================================
Main entry point for the NexusTwin REST API.

Architecture overview:
  api/
    main.py          ← this file (app factory, lifespan, root routes)
    middleware.py    ← performance tracking middleware
    dependencies.py  ← FastAPI Depends() injectors (DB, auth, etc.)
    routes/
      elements.py    ← /api/v1/elements (CRUD for BIM element registry)
      health.py      ← /api/v1/health   (SHI computation)
      fatigue.py     ← /api/v1/fatigue  (Miner's Rule calculation)
      anomaly.py     ← /api/v1/anomaly  (two-layer anomaly detection)
      simulate.py    ← /api/v1/simulate (sensor simulation for demo/lab)
      prediction.py  ← /api/v1/predict  (ML-based SHI forecasting)
      reporting.py   ← /api/v1/report   (PDF export)

Design decisions:
  - Lifespan context manager (not deprecated @app.on_event) for startup/shutdown
  - AnomalyDetectors are kept in a module-level dict so they're stateful
    across requests (their rolling buffers accumulate). For multi-process
    deployments, move this state to Redis or the database.
  - ML SHIPredictor is fitted lazily on the first /predict request for each
    element (or explicitly via POST /predict/{element_id}/fit).
"""

import logging
import logging.config
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import get_settings
from database.twin_db import initialise_db, shutdown_db
from api.middleware import PerformanceTrackingMiddleware

# Import all sub-routers
from api.routes.elements   import router as elements_router
from api.routes.health     import router as health_router
from api.routes.fatigue    import router as fatigue_router
from api.routes.anomaly    import router as anomaly_router
from api.routes.simulate   import router as simulate_router
from api.routes.prediction import router as prediction_router
from api.routes.reporting  import router as reporting_router

settings = get_settings()

# ---------------------------------------------------------------------------
# Logging setup — configure before app creation so __name__ loggers work
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=getattr(logging, settings.NEXUS_LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan: startup and shutdown events
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager.
    Everything before 'yield' runs at startup; everything after at shutdown.
    This is the modern replacement for @app.on_event("startup").
    """
    logger.info("NexusTwin API startup initiated...")
    await initialise_db()
    logger.info("Database connected and schema verified.")
    yield
    # ── Shutdown ──────────────────────────────────────────────
    logger.info("NexusTwin API shutting down...")
    await shutdown_db()
    logger.info("Database connection closed cleanly.")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="NexusTwin — Structural Digital Twin API",
    description=(
        "Production-grade REST API for real-time structural health monitoring, "
        "fatigue analysis, anomaly detection, and ML-powered SHI forecasting."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS — allow the dashboard frontend and Swagger UI to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-NexusTwin-API-Key"],
    allow_credentials=False,
)

# Performance middleware — logs request duration for every call
app.add_middleware(PerformanceTrackingMiddleware)

# ---------------------------------------------------------------------------
# Routers — all prefixed under /api/v1/
# ---------------------------------------------------------------------------

API_PREFIX = "/api/v1"

app.include_router(elements_router,   prefix=API_PREFIX)
app.include_router(health_router,     prefix=API_PREFIX)
app.include_router(fatigue_router,    prefix=API_PREFIX)
app.include_router(anomaly_router,    prefix=API_PREFIX)
app.include_router(simulate_router,   prefix=API_PREFIX)
app.include_router(prediction_router, prefix=API_PREFIX)
app.include_router(reporting_router,  prefix=API_PREFIX)


# ---------------------------------------------------------------------------
# Root health-check endpoint (no auth required)
# ---------------------------------------------------------------------------

@app.get("/", tags=["Health Check"], summary="API liveness probe")
async def root() -> dict:
    """
    Returns 200 OK with version info.
    Used by load balancers, monitoring tools, and the CI pipeline
    to verify the API is alive.
    """
    return {
        "status": "NexusTwin Online",
        "version": app.version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "docs": "/docs",
    }
