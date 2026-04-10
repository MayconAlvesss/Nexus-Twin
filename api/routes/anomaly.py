"""
NexusTwin — Anomaly Detection Router
=======================================
Endpoints for the two-layer anomaly detection pipeline.

Endpoints:
  POST /api/v1/anomaly/detect              — detect anomalies in one sensor tick
  POST /api/v1/anomaly/{element_id}/fit    — (re-)train the IsolationForest
  GET  /api/v1/anomaly/{element_id}/log    — retrieve anomaly audit log

State management note:
  AnomalyDetector instances are stored in the module-level dict
  _detectors, keyed by element_id. This is fine for a single-process
  deployment. For multi-worker (Gunicorn/Uvicorn with --workers > 1),
  move detector state to a shared store (Redis, or serialize to DB).
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import get_db, verified_api_key
from core.anomaly_detector import AnomalyDetector
from database.twin_db import TwinDBManager
from ingestion.schemas import (
    AnomalyDetectRequest,
    AnomalyDetectResponse,
    AnomalyRecord,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/anomaly", tags=["Anomaly Detection"])

# In-process detector registry: element_id → AnomalyDetector instance
_detectors: dict[str, AnomalyDetector] = {}


def _get_or_create_detector(element_id: str) -> AnomalyDetector:
    """
    Return the existing detector for an element, or create a fresh (unfitted)
    one if this is the first call for this element.
    The IsolationForest layer only activates after /fit is called.
    The Z-score layer works from the moment enough readings accumulate.
    """
    if element_id not in _detectors:
        _detectors[element_id] = AnomalyDetector(element_id=element_id)
        logger.info("Created new AnomalyDetector for element %s.", element_id)
    return _detectors[element_id]


@router.post(
    "/detect",
    response_model=AnomalyDetectResponse,
    summary="Run anomaly detection on a new sensor reading",
    dependencies=[Depends(verified_api_key)],
)
async def detect_anomaly(
    payload: AnomalyDetectRequest,
    db: TwinDBManager = Depends(get_db),
) -> AnomalyDetectResponse:
    """
    Feed one timestep of multi-channel readings to the two-layer detector.

    Layer 1 (Z-score)  activates as soon as ≥5 readings have accumulated.
    Layer 2 (IsoForest) only activates after POST /anomaly/{id}/fit is called.

    All detected anomalies are persisted to the audit log for reporting.
    """
    # Confirm element is registered
    element = await db.get_element(payload.element_id)
    if not element:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Element '{payload.element_id}' not registered.",
        )

    detector = _get_or_create_detector(payload.element_id)

    anomalies = detector.detect(
        strain_value      = payload.strain_value,
        vibration_value   = payload.vibration_value,
        temperature_value = payload.temperature_value,
        timestamp         = payload.timestamp,
    )

    # Persist every detected anomaly to the DB audit log
    for anomaly in anomalies:
        await db.log_anomaly(
            anomaly_id  = anomaly.anomaly_id,
            element_id  = anomaly.element_id,
            sensor_type = anomaly.sensor_type,
            severity    = anomaly.severity.value,
            value       = anomaly.value,
            z_score     = anomaly.z_score,
            description = anomaly.description,
        )

    if anomalies:
        logger.warning(
            "%d anomaly(ies) detected for element %s.",
            len(anomalies), payload.element_id,
        )

    return AnomalyDetectResponse(
        element_id    = payload.element_id,
        anomaly_count = len(anomalies),
        anomalies     = [
            AnomalyRecord(
                anomaly_id  = a.anomaly_id,
                element_id  = a.element_id,
                sensor_type = a.sensor_type,
                severity    = a.severity.value,
                value       = a.value,
                z_score     = a.z_score,
                timestamp   = a.timestamp,
                description = a.description,
            )
            for a in anomalies
        ],
    )


@router.post(
    "/{element_id}/fit",
    summary="Train the IsolationForest on baseline sensor data",
    dependencies=[Depends(verified_api_key)],
)
async def fit_anomaly_model(
    element_id:        str,
    strain_data:       list[float],
    vibration_data:    list[float],
    temperature_data:  list[float],
    db: TwinDBManager = Depends(get_db),
) -> dict:
    """
    Train (or retrain) the IsolationForest layer on historical 'normal'
    sensor readings. At least 10 data points per channel are required;
    200+ is recommended for a reliable model.

    Typical usage:
      1. Collect a few hours of baseline sensor data during commissioning.
      2. POST this data to /fit once per structural element.
      3. All subsequent /detect calls will then use both detection layers.
    """
    element = await db.get_element(element_id)
    if not element:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Element '{element_id}' not registered.",
        )

    detector = _get_or_create_detector(element_id)
    detector.fit(
        strain_data      = strain_data,
        vibration_data   = vibration_data,
        temperature_data = temperature_data,
    )

    return {
        "status":       "ok",
        "element_id":   element_id,
        "fitted":       detector._is_fitted,
        "training_n":   min(len(strain_data), len(vibration_data), len(temperature_data)),
        "message":      "IsolationForest model fitted. Both detection layers are now active.",
    }


@router.get(
    "/{element_id}/log",
    summary="Retrieve anomaly audit log for an element",
    dependencies=[Depends(verified_api_key)],
)
async def get_anomaly_log(
    element_id: str,
    severity:   Optional[str] = None,
    limit:      int = 100,
    db: TwinDBManager = Depends(get_db),
) -> dict:
    """
    Returns the anomaly audit log for an element.
    Optionally filter by severity: LOW | MEDIUM | HIGH | CRITICAL.
    """
    events = await db.get_anomalies(element_id=element_id, severity=severity, limit=limit)
    return {
        "element_id": element_id,
        "count":      len(events),
        "events":     events,
    }
