"""
NexusTwin — Elements Router
==============================
CRUD endpoints for the BIM element registry.

Endpoints:
  POST   /api/v1/elements            — register or update an element
  GET    /api/v1/elements            — list all registered elements
  GET    /api/v1/elements/{id}       — get a single element with latest SHI
  DELETE /api/v1/elements/{id}       — remove an element (and its history)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import get_db, verified_api_key
from database.twin_db import TwinDBManager
from ingestion.schemas import ElementRegisterRequest, ElementResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/elements", tags=["Element Registry"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Register or update a BIM element",
    dependencies=[Depends(verified_api_key)],
)
async def register_element(
    payload: ElementRegisterRequest,
    db: TwinDBManager = Depends(get_db),
) -> dict:
    """
    Idempotent upsert — safe to call on every BIM sync.
    If the element already exists, its metadata is updated.
    """
    await db.upsert_element(
        element_id    = payload.element_id,
        name          = payload.name,
        element_type  = payload.element_type,
        material_class= payload.material_class,
        age_years     = payload.age_years,
        floor_level   = payload.floor_level,
        notes         = payload.notes,
    )
    logger.info("Element registered/updated: %s", payload.element_id)
    return {
        "status":     "ok",
        "element_id": payload.element_id,
        "message":    f"Element '{payload.element_id}' registered successfully.",
    }


@router.get(
    "",
    summary="List all registered elements",
    dependencies=[Depends(verified_api_key)],
)
async def list_elements(
    db: TwinDBManager = Depends(get_db),
) -> dict:
    """Return every element in the twin registry, sorted newest-first."""
    elements = await db.list_elements()
    return {"count": len(elements), "elements": elements}


@router.get(
    "/{element_id}",
    summary="Get element detail with latest SHI snapshot",
    dependencies=[Depends(verified_api_key)],
)
async def get_element(
    element_id: str,
    db: TwinDBManager = Depends(get_db),
) -> dict:
    """
    Returns the element metadata plus its latest SHI snapshot
    so the dashboard can render the status card with a single request.
    """
    element = await db.get_element(element_id)
    if not element:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Element '{element_id}' not found in this twin.",
        )

    latest_shi = await db.get_latest_shi(element_id)

    return {
        "element":    element,
        "latest_shi": latest_shi,  # None if no SHI has been computed yet
    }
