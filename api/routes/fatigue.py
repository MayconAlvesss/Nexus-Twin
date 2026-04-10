"""
NexusTwin — Fatigue Router
============================
Endpoints for Palmgren-Miner fatigue life calculation.

Endpoints:
  POST /api/v1/fatigue/compute   — run Miner's Rule on stress blocks
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import get_db, verified_api_key
from core.fatigue_engine import FatigueEngine, StressBlock
from core.exceptions import FatigueCalculationError
from database.twin_db import TwinDBManager
from ingestion.schemas import FatigueComputeRequest, FatigueComputeResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fatigue", tags=["Fatigue Analysis"])

# Module-level engine instance — stateless, safe to share across requests
_fatigue_engine = FatigueEngine()


@router.post(
    "/compute",
    response_model=FatigueComputeResponse,
    summary="Compute Miner's Rule cumulative fatigue damage",
    dependencies=[Depends(verified_api_key)],
)
async def compute_fatigue(
    payload: FatigueComputeRequest,
    db: TwinDBManager = Depends(get_db),
) -> FatigueComputeResponse:
    """
    Applies Palmgren-Miner's linear damage accumulation rule to the
    provided stress blocks.

    Stress blocks are typically extracted from a strain time-series
    via rainflow cycle counting (ASTM E1049). You can pre-process the
    time-series in a separate step and pass the blocks here, or supply
    them manually for design-check scenarios.

    The element must be registered in the twin for the request to succeed.
    """
    # Confirm element exists
    element = await db.get_element(payload.element_id)
    if not element:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Element '{payload.element_id}' not found. Register it first.",
        )

    # Convert Pydantic input models to domain StressBlock objects
    domain_blocks = [
        StressBlock(
            stress_range_mpa = b.stress_range_mpa,
            cycle_count      = b.cycle_count,
        )
        for b in payload.stress_blocks
    ]

    try:
        result = _fatigue_engine.calculate_damage(
            element_id     = payload.element_id,
            material_class = payload.material_class,
            stress_blocks  = domain_blocks,
        )
    except FatigueCalculationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # Optionally estimate remaining service life in years
    remaining_years = None
    if payload.element_age_years is not None:
        remaining_years = _fatigue_engine.estimate_remaining_life_years(
            damage_ratio       = result.damage_ratio,
            element_age_years  = payload.element_age_years,
        )

    logger.info(
        "Fatigue computed for %s: D=%.4f (%s), remaining=%.1f%%",
        result.element_id, result.damage_ratio,
        result.status, result.remaining_life_pct,
    )

    return FatigueComputeResponse(
        element_id           = result.element_id,
        material_class       = result.material_class,
        damage_ratio         = result.damage_ratio,
        remaining_life_pct   = result.remaining_life_pct,
        remaining_life_years = remaining_years,
        status               = result.status,
        total_cycles         = result.total_cycles,
        notes                = result.notes,
    )
