"""
NexusTwin — SHI Predictive Model (Random Forest Regressor)
============================================================
Predicts the expected Structural Health Index 7 days into the future
using a sliding window of recent SHI history and sensor statistics.

Why Random Forest for time-series prediction here?
  A proper forecasting model (ARIMA, LSTM, Prophet) would be overkill
  for a portfolio piece and would require much more data. Random Forest
  on lag features is:
    1. Fast to train (seconds, not minutes)
    2. Interpretable — feature importances tell us which sensor channel
       is driving the degradation prediction
    3. Robust to small datasets (works with ~30+ snapshots)

Feature engineering:
  Given a window of N historical SHI snapshots, we extract:
    - Rolling mean / std of the SHI score (trend + volatility)
    - Latest sub-scores for each sensor channel
    - Miner damage ratio trend (linear slope over window)
  These features are fed to a RandomForestRegressor that outputs the
  predicted SHI score at T+7d.

References:
  - Breiman (2001) — Random Forests
  - ISO 13373-2:2016 — Condition monitoring for machinery: data processing
  - Farrar & Worden (2012) — Structural Health Monitoring, ch. 9
"""

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

# Minimum training samples required before the model is reliable
MIN_TRAINING_SAMPLES = 20

# Prediction horizon — how many SHI snapshots ahead we try to predict.
# If snapshots are taken daily, HORIZON=7 means 7 days.
HORIZON = 7


@dataclass
class PredictionResult:
    """Output of a single SHI prediction run."""
    element_id:        str
    predicted_shi:     float       # the 7-day-ahead SHI estimate
    confidence_band_lower: float   # 10th percentile of tree predictions
    confidence_band_upper: float   # 90th percentile of tree predictions
    trend:             str         # "IMPROVING" | "STABLE" | "DEGRADING"
    feature_importances: dict      # {feature_name: importance_score}
    trained_on_n:      int         # how many samples the model was trained on


class SHIPredictor:
    """
    Trains a Random Forest on historical SHI data and predicts future health.

    Lifecycle:
        predictor = SHIPredictor(element_id="COLUMN-04A")
        predictor.fit(history_records)            # list of shi_history dicts from DB
        result = predictor.predict()
    """

    # Feature names in the order the model is trained on
    FEATURE_NAMES = [
        "shi_mean",          # rolling mean of SHI over window
        "shi_std",           # rolling std (volatility)
        "shi_slope",         # linear trend slope (deg/snapshot)
        "strain_score_last", # most recent channel sub-scores
        "vibration_score_last",
        "temperature_score_last",
        "fatigue_score_last",
        "snapshots_in_window",
    ]

    def __init__(self, element_id: str, n_estimators: int = 200) -> None:
        self.element_id = element_id
        self._model = RandomForestRegressor(
            n_estimators=n_estimators,
            random_state=42,
            n_jobs=-1,
        )
        self._scaler = StandardScaler()
        self._is_fitted = False
        self._history: list[dict] = []

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def fit(self, history_records: list[dict]) -> None:
        """
        Train the model on a list of SHI history records (as returned by
        TwinDBManager.get_shi_history()).

        Each record must have at minimum:
            shi_score, strain_score, vibration_score,
            temperature_score, fatigue_score
        """
        if len(history_records) < MIN_TRAINING_SAMPLES:
            logger.warning(
                "SHIPredictor for %s: only %d samples (min=%d) — model not fitted.",
                self.element_id, len(history_records), MIN_TRAINING_SAMPLES,
            )
            return

        # Sort oldest→newest so lag windows make sense
        records = sorted(history_records, key=lambda r: r.get("recorded_at", ""))
        self._history = records

        X, y = self._build_training_set(records)

        if len(X) < 5:
            logger.warning(
                "SHIPredictor for %s: not enough labelled pairs (%d) after windowing.",
                self.element_id, len(X),
            )
            return

        X_scaled = self._scaler.fit_transform(X)
        self._model.fit(X_scaled, y)
        self._is_fitted = True

        logger.info(
            "SHIPredictor fitted for %s: %d training pairs, %d features.",
            self.element_id, len(X), len(self.FEATURE_NAMES),
        )

    def predict(self) -> Optional[PredictionResult]:
        """
        Return the T+HORIZON SHI prediction using the most recent window
        in the stored history.

        Returns None if the model hasn't been fitted yet.
        """
        if not self._is_fitted or not self._history:
            logger.info(
                "SHIPredictor for %s: model not ready — returning None.",
                self.element_id,
            )
            return None

        features = self._extract_features(self._history)
        if features is None:
            return None

        X = np.array([features])
        X_scaled = self._scaler.transform(X)

        # Collect individual tree predictions for the confidence band
        tree_preds = np.array([
            tree.predict(X_scaled)[0] for tree in self._model.estimators_
        ])

        predicted_shi   = float(np.clip(self._model.predict(X_scaled)[0], 0.0, 100.0))
        lower           = float(np.clip(np.percentile(tree_preds, 10), 0.0, 100.0))
        upper           = float(np.clip(np.percentile(tree_preds, 90), 0.0, 100.0))

        # Determine trend from the slope feature (index 2)
        slope = features[2]
        if slope > 0.5:
            trend = "IMPROVING"
        elif slope < -0.5:
            trend = "DEGRADING"
        else:
            trend = "STABLE"

        importances = {
            name: round(float(imp), 4)
            for name, imp in zip(self.FEATURE_NAMES, self._model.feature_importances_)
        }

        return PredictionResult(
            element_id=self.element_id,
            predicted_shi=round(predicted_shi, 2),
            confidence_band_lower=round(lower, 2),
            confidence_band_upper=round(upper, 2),
            trend=trend,
            feature_importances=importances,
            trained_on_n=len(self._history),
        )

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _build_training_set(
        self, records: list[dict]
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Build (X, y) pairs using a sliding window of size HORIZON.
        X = features from snapshot[i], y = shi_score at snapshot[i + HORIZON].
        """
        X_list, y_list = [], []

        for i in range(len(records) - HORIZON):
            window = records[:i + 1]          # all snapshots up to and including i
            target = records[i + HORIZON]["shi_score"]

            features = self._extract_features(window)
            if features is not None:
                X_list.append(features)
                y_list.append(target)

        return np.array(X_list), np.array(y_list)

    def _extract_features(self, window: list[dict]) -> Optional[list[float]]:
        """
        Compute the feature vector from a window of SHI snapshots.
        Returns None if the window is too small.
        """
        if not window:
            return None

        shi_scores = [r["shi_score"] for r in window]

        if len(shi_scores) < 2:
            shi_slope = 0.0
        else:
            # Simple linear regression slope across the window
            x     = np.arange(len(shi_scores), dtype=float)
            slope_coef = np.polyfit(x, shi_scores, 1)
            shi_slope  = float(slope_coef[0])

        last = window[-1]

        return [
            float(np.mean(shi_scores)),
            float(np.std(shi_scores)) if len(shi_scores) > 1 else 0.0,
            shi_slope,
            float(last.get("strain_score", 100.0)),
            float(last.get("vibration_score", 100.0)),
            float(last.get("temperature_score", 100.0)),
            float(last.get("fatigue_score", 100.0)),
            float(len(window)),
        ]
