"""
NexusTwin — Structural Health Router
=======================================
Endpoints for computing and retrieving SHI scores.

Endpoints:
  POST /api/v1/health/compute         — compute SHI from sensor readings
  GET  /api/v1/health/{element_id}    — get SHI trend history
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import get_db, verified_api_key
from core.structural_health_engine import StructuralHealthEngine
from core.exceptions import InsufficientReadingsError, ElementNotFoundError
from database.twin_db import TwinDBManager
from ingestion.schemas import SensorReadingsBatch, SHIComputeResponse
from config.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["Structural Health Index"])

_settings = get_settings()
_shi_engine = StructuralHealthEngine(
    warning_threshold  = _settings.NEXUS_HEALTH_WARNING_THRESHOLD,
    critical_threshold = _settings.NEXUS_HEALTH_CRITICAL_THRESHOLD,
)


@router.post(
    "/compute",
    response_model=SHIComputeResponse,
    summary="Compute Structural Health Index from sensor readings",
    dependencies=[Depends(verified_api_key)],
)
async def compute_shi(
    payload: SensorReadingsBatch,
    db: TwinDBManager = Depends(get_db),
) -> SHIComputeResponse:
    """
    Accepts a batch of multi-channel sensor readings and returns the full
    SHI score breakdown. The result is also persisted to shi_history so
    the dashboard can render trend charts.

    The element must be registered via POST /api/v1/elements first.
    """
    # Verify element exists in the registry before doing any computation
    element = await db.get_element(payload.element_id)
    if not element:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Element '{payload.element_id}' is not registered. "
                   "Register it via POST /api/v1/elements first.",
        )

    try:
        result = _shi_engine.compute(
            element_id           = payload.element_id,
            strain_readings      = payload.strain_readings,
            vibration_readings   = payload.vibration_readings,
            temperature_readings = payload.temperature_readings,
            miner_damage_ratio   = payload.miner_damage_ratio,
        )
    except InsufficientReadingsError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # Persist the snapshot to the database for trend analysis
    await db.record_shi(
        element_id        = result.element_id,
        shi_score         = result.shi_score,
        strain_score      = result.strain_score,
        vibration_score   = result.vibration_score,
        temperature_score = result.temperature_score,
        fatigue_score     = result.fatigue_score,
        status            = result.status,
        reading_count     = result.reading_count,
        notes             = result.notes,
    )

    logger.info(
        "SHI computed for %s: %.1f (%s)",
        result.element_id, result.shi_score, result.status,
    )

    return SHIComputeResponse(
        element_id        = result.element_id,
        shi_score         = result.shi_score,
        strain_score      = result.strain_score,
        vibration_score   = result.vibration_score,
        temperature_score = result.temperature_score,
        fatigue_score     = result.fatigue_score,
        status            = result.status,
        reading_count     = result.reading_count,
        notes             = result.notes,
    )


@router.get(
    "/{element_id}/history",
    summary="Retrieve SHI history for trend charts",
    dependencies=[Depends(verified_api_key)],
)
async def get_shi_history(
    element_id: str,
    limit: int = 100,
    db: TwinDBManager = Depends(get_db),
) -> dict:
    """
    Returns the last N SHI snapshots for an element (newest-first).
    The dashboard uses this to render the health trend chart.
    """
    element = await db.get_element(element_id)
    if not element:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Element '{element_id}' not found.",
        )

    history = await db.get_shi_history(element_id, limit=limit)
    return {
        "element_id": element_id,
        "count":      len(history),
        "history":    history,
    }
