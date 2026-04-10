"""
NexusTwin — ML Prediction Router
===================================
Endpoints for the SHI Random Forest forecasting model.

Endpoints:
  POST /api/v1/predict/{element_id}/fit   — train the predictor on DB history
  GET  /api/v1/predict/{element_id}       — get the T+7d SHI forecast
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import get_db, verified_api_key
from database.twin_db import TwinDBManager
from ml.health_predictor import SHIPredictor, MIN_TRAINING_SAMPLES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predict", tags=["ML SHI Prediction"])

# Per-element predictor registry — same pattern as AnomalyDetector
_predictors: dict[str, SHIPredictor] = {}


def _get_or_create_predictor(element_id: str) -> SHIPredictor:
    if element_id not in _predictors:
        _predictors[element_id] = SHIPredictor(element_id=element_id)
    return _predictors[element_id]


@router.post(
    "/{element_id}/fit",
    summary="Train the SHI predictor on stored history",
    dependencies=[Depends(verified_api_key)],
)
async def fit_predictor(
    element_id: str,
    db: TwinDBManager = Depends(get_db),
) -> dict:
    """
    Pulls all SHI history records for the element from the DB and trains
    the Random Forest regressor.

    At least {MIN_TRAINING_SAMPLES} SHI snapshots are required.
    Compute SHI via POST /api/v1/health/compute to build up history.
    """
    element = await db.get_element(element_id)
    if not element:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Element '{element_id}' not found.",
        )

    history = await db.get_shi_history(element_id, limit=5000)

    if len(history) < MIN_TRAINING_SAMPLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Not enough SHI history to train the predictor. "
                f"Need at least {MIN_TRAINING_SAMPLES} snapshots, got {len(history)}."
            ),
        )

    predictor = _get_or_create_predictor(element_id)
    predictor.fit(history)

    return {
        "status":     "ok",
        "element_id": element_id,
        "fitted":     predictor._is_fitted,
        "trained_on": len(history),
        "message":    "Predictor trained. Call GET /predict/{element_id} for the forecast.",
    }


@router.get(
    "/{element_id}",
    summary="Get the 7-day SHI forecast",
    dependencies=[Depends(verified_api_key)],
)
async def get_prediction(
    element_id: str,
    db: TwinDBManager = Depends(get_db),
) -> dict:
    """
    Returns the Random Forest SHI prediction for T+7 snapshots ahead,
    including a 80% confidence band and a trend classification.

    Call POST /predict/{element_id}/fit first to train the model.
    """
    element = await db.get_element(element_id)
    if not element:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Element '{element_id}' not found.",
        )

    predictor = _predictors.get(element_id)
    if predictor is None or not predictor._is_fitted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Predictor for '{element_id}' is not trained yet. "
                "Call POST /predict/{element_id}/fit first."
            ),
        )

    result = predictor.predict()
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Prediction failed — check logs for details.",
        )

    return {
        "element_id":            result.element_id,
        "predicted_shi":         result.predicted_shi,
        "confidence_band_lower": result.confidence_band_lower,
        "confidence_band_upper": result.confidence_band_upper,
        "trend":                 result.trend,
        "trained_on_n":          result.trained_on_n,
        "feature_importances":   result.feature_importances,
        "horizon":               "T+7 SHI snapshots",
    }
