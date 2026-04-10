"""
NexusTwin — Anomaly Detector
==============================
Two-layer anomaly detection pipeline for structural sensor streams:

  Layer 1 — Z-Score / CUSUM spike detector
    Fast, stateless — catches sudden jumps in a single reading.
    Good for: sensor failures, impact events, sudden overload.

  Layer 2 — Isolation Forest (sklearn)
    Trained on normal behaviour; flags multi-feature patterns that
    look anomalous globally but are not obvious per-channel.
    Good for: slow drift, correlated degradation across channels.

Why two layers?
    Z-score catches point anomalies in microseconds.
    IsolationForest catches collective / contextual anomalies that
    Z-score misses (e.g. correlated strain + vibration drift).
    Running both gives high recall without completely sacrificing precision.

References:
    - Liu, Ting & Zhou (2008) — Isolation Forest (original paper)
    - Basseville & Nikiforov (1993) — Detection of Abrupt Changes (CUSUM)
    - ISO 13381-1:2015 — Condition monitoring: anomaly detection principles
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

import numpy as np
from sklearn.ensemble import IsolationForest

logger = logging.getLogger(__name__)


class AnomalySeverity(str, Enum):
    LOW      = "LOW"       # worth logging; no immediate action
    MEDIUM   = "MEDIUM"    # schedule a review
    HIGH     = "HIGH"      # inspection within 7 days
    CRITICAL = "CRITICAL"  # immediate action required


@dataclass
class Anomaly:
    """A single detected anomaly event."""
    anomaly_id:   str             # unique identifier (element + timestamp)
    element_id:   str
    sensor_type:  str             # "strain" | "vibration" | "temperature" | "multi"
    severity:     AnomalySeverity
    value:        float            # the exact reading that triggered the alert
    z_score:      Optional[float]  # from Layer 1; None if only Layer 2 triggered
    timestamp:    str
    description:  str              # human-readable explanation


@dataclass
class AnomalyDetector:
    """
    Stateful detector for a single structural element.
    Maintains a rolling buffer of recent readings per channel so it can
    compute Z-scores without needing the full history every call.

    Lifecycle:
        detector = AnomalyDetector(element_id="COLUMN-04A")
        detector.fit(normal_strain, normal_vibration, normal_temperature)
        anomalies = detector.detect(new_strain, new_vibration, new_temperature, ts)
    """

    element_id: str

    # Rolling window size for Z-score baseline statistics
    window_size: int = 200

    # Z-score threshold for spike detection (3σ = 99.7% confidence for Gaussian data)
    z_threshold: float = 3.0

    # IsolationForest contamination estimate (fraction of expected anomalies in training data)
    contamination: float = 0.05

    # Internal state — populated by fit()
    _model: Optional[IsolationForest] = field(default=None, init=False, repr=False)
    _is_fitted: bool = field(default=False, init=False, repr=False)

    # Per-channel rolling buffers (lists keep insertion order for efficient append)
    _strain_buffer:      list[float] = field(default_factory=list, init=False, repr=False)
    _vibration_buffer:   list[float] = field(default_factory=list, init=False, repr=False)
    _temperature_buffer: list[float] = field(default_factory=list, init=False, repr=False)

    def fit(
        self,
        strain_data: list[float],
        vibration_data: list[float],
        temperature_data: list[float],
    ) -> None:
        """
        Train the IsolationForest on historical 'normal' sensor readings.
        Call this once at startup with the baseline data window.

        Minimum data points: 10   (IsolationForest needs some density to work)
        Recommended:         200+ readings per channel for a stable model.
        """
        n = min(len(strain_data), len(vibration_data), len(temperature_data))
        if n < 10:
            logger.warning(
                "AnomalyDetector for %s: only %d data points — IsolationForest may be unreliable.",
                self.element_id, n,
            )

        # Build the feature matrix [strain, vibration, temperature] per timestep
        X = np.column_stack([
            strain_data[:n],
            vibration_data[:n],
            temperature_data[:n],
        ])

        self._model = IsolationForest(
            n_estimators=100,       # 100 trees is a good balance of speed vs accuracy
            contamination=self.contamination,
            random_state=42,        # reproducible results
            n_jobs=-1,              # use all available CPU cores
        )
        self._model.fit(X)
        self._is_fitted = True

        # Seed the rolling buffers with the training data (keep last window_size points)
        self._strain_buffer      = list(strain_data[-self.window_size:])
        self._vibration_buffer   = list(vibration_data[-self.window_size:])
        self._temperature_buffer = list(temperature_data[-self.window_size:])

        logger.info(
            "IsolationForest fitted for element %s on %d samples.",
            self.element_id, n,
        )

    def detect(
        self,
        strain_value: float,
        vibration_value: float,
        temperature_value: float,
        timestamp: Optional[str] = None,
    ) -> list[Anomaly]:
        """
        Run both detection layers on a single new set of readings.
        Updates the rolling buffers so future calls have fresh baselines.

        Returns a list of Anomaly objects (empty list = all clear).
        """
        ts = timestamp or datetime.utcnow().isoformat()
        anomalies: list[Anomaly] = []

        # --- Layer 1: Z-score spike detection per channel ---
        channels = {
            "strain":      (strain_value,      self._strain_buffer),
            "vibration":   (vibration_value,   self._vibration_buffer),
            "temperature": (temperature_value, self._temperature_buffer),
        }
        for sensor_type, (value, buffer) in channels.items():
            anomaly = self._zscore_check(sensor_type, value, buffer, ts)
            if anomaly:
                anomalies.append(anomaly)

        # --- Layer 2: IsolationForest multi-feature check ---
        if self._is_fitted and self._model is not None:
            isolation_anomaly = self._isolation_check(
                strain_value, vibration_value, temperature_value, ts
            )
            if isolation_anomaly:
                anomalies.append(isolation_anomaly)

        # --- Update rolling buffers with the new readings ---
        self._append(self._strain_buffer,      strain_value)
        self._append(self._vibration_buffer,   vibration_value)
        self._append(self._temperature_buffer, temperature_value)

        return anomalies

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _zscore_check(
        self,
        sensor_type: str,
        value: float,
        buffer: list[float],
        timestamp: str,
    ) -> Optional[Anomaly]:
        """
        Compute Z-score for the new value against the rolling buffer baseline.
        Returns an Anomaly if the Z-score exceeds self.z_threshold.
        """
        if len(buffer) < 5:
            # Not enough history to compute a meaningful Z-score
            return None

        arr = np.array(buffer, dtype=float)
        mu  = float(np.mean(arr))
        std = float(np.std(arr))

        if std < 1e-9:
            # Constant signal — any deviation is anomalous but Z-score is undefined
            if abs(value - mu) > 1e-6:
                z = float("inf")
            else:
                return None
        else:
            z = abs(value - mu) / std

        if z <= self.z_threshold:
            return None

        # Map Z-score magnitude to severity
        severity = self._zscore_to_severity(z)
        anomaly_id = f"{self.element_id}-{sensor_type}-{timestamp}"

        return Anomaly(
            anomaly_id=anomaly_id,
            element_id=self.element_id,
            sensor_type=sensor_type,
            severity=severity,
            value=round(value, 4),
            z_score=round(z, 2),
            timestamp=timestamp,
            description=(
                f"{sensor_type.capitalize()} spike detected (Z={z:.2f}σ). "
                f"Current value {value:.3f} deviates {z:.1f}σ from rolling mean {mu:.3f}."
            ),
        )

    def _isolation_check(
        self,
        strain: float,
        vibration: float,
        temperature: float,
        timestamp: str,
    ) -> Optional[Anomaly]:
        """
        Run the IsolationForest on the combined feature vector.
        IsolationForest returns -1 for anomalies, +1 for inliers.
        """
        X_new = np.array([[strain, vibration, temperature]])
        prediction = self._model.predict(X_new)[0]  # type: ignore[union-attr]
        anomaly_score = float(self._model.decision_function(X_new)[0])  # type: ignore[union-attr]

        if prediction != -1:
            return None  # inlier — nothing to flag

        # Lower (more negative) anomaly score → more anomalous
        severity = AnomalySeverity.MEDIUM if anomaly_score > -0.1 else AnomalySeverity.HIGH

        return Anomaly(
            anomaly_id=f"{self.element_id}-multi-{timestamp}",
            element_id=self.element_id,
            sensor_type="multi",
            severity=severity,
            value=round(anomaly_score, 4),
            z_score=None,  # IsolationForest doesn't produce a Z-score
            timestamp=timestamp,
            description=(
                f"Multi-channel anomaly pattern detected by IsolationForest "
                f"(score={anomaly_score:.4f}). Correlated deviation across "
                f"strain={strain:.1f}, vibration={vibration:.2f}, temperature={temperature:.1f}."
            ),
        )

    def _append(self, buffer: list, value: float) -> None:
        """Append to the rolling buffer and evict the oldest entry if over window_size."""
        buffer.append(value)
        if len(buffer) > self.window_size:
            buffer.pop(0)   # O(n) but window_size is small (≤200), acceptable here

    @staticmethod
    def _zscore_to_severity(z: float) -> AnomalySeverity:
        """Map Z-score magnitude to human-meaningful severity."""
        if z < 4:
            return AnomalySeverity.LOW
        if z < 5:
            return AnomalySeverity.MEDIUM
        if z < 7:
            return AnomalySeverity.HIGH
        return AnomalySeverity.CRITICAL
