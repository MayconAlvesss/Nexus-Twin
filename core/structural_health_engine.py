"""
NexusTwin — Structural Health Index (SHI) Engine
==================================================
Computes a 0–100 health score for each monitored structural element by
combining normalised sub-scores from three sensor channels plus the fatigue
damage ratio from the FatigueEngine.

SHI = 100 means perfect health (brand-new structure, no stress, no damage).
SHI = 0   means complete failure (all sensors critical, fatigue limit exceeded).

Scoring methodology:
  Each sensor reading is mapped to a 0–100 sub-score via a piecewise linear
  function anchored at the thresholds defined in config/thresholds.py.
  Sub-scores are then combined using the SHI_WEIGHTS from the same module.

  The final SHI is clamped to [0, 100] to absorb any floating-point drift.

References:
  - Farrar & Worden (2012) — Structural Health Monitoring: A Machine Learning
    Perspective, Chapter 4 (damage index formulation)
  - ISO 13381-1:2015 — Condition monitoring and diagnostics, Section 6
"""

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

from config.thresholds import SENSOR_LIMITS, SHI_WEIGHTS
from core.exceptions import InsufficientReadingsError

logger = logging.getLogger(__name__)

# Minimum number of readings we need before we trust the SHI score.
MIN_READINGS_REQUIRED = 5


@dataclass
class SHIResult:
    """Full SHI result for a single structural element."""
    element_id:       str
    shi_score:        float         # 0–100 (higher is healthier)
    strain_score:     float         # sub-score for strain channel
    vibration_score:  float         # sub-score for vibration channel
    temperature_score: float        # sub-score for temperature channel
    fatigue_score:    float         # sub-score derived from Miner's damage ratio D
    status:           str           # "HEALTHY" | "WARNING" | "CRITICAL"
    reading_count:    int           # how many readings contributed to this score
    notes: Optional[str] = None     # human-readable context for the score


class StructuralHealthEngine:
    """
    Computes the Structural Health Index for a set of sensor readings.

    Usage:
        engine = StructuralHealthEngine(
            warning_threshold=65.0,
            critical_threshold=40.0,
        )
        result = engine.compute(
            element_id="WALL-001",
            strain_readings=[120.5, 135.0, ...],      # µε
            vibration_readings=[1.2, 1.4, ...],        # mm/s
            temperature_readings=[22.1, 23.0, ...],    # °C
            miner_damage_ratio=0.15,                   # from FatigueEngine
        )
    """

    def __init__(
        self,
        warning_threshold: float = 65.0,
        critical_threshold: float = 40.0,
    ) -> None:
        self.warning_threshold  = warning_threshold
        self.critical_threshold = critical_threshold

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def compute(
        self,
        element_id: str,
        strain_readings: list[float],
        vibration_readings: list[float],
        temperature_readings: list[float],
        miner_damage_ratio: float = 0.0,
    ) -> SHIResult:
        """
        Compute the SHI for one element from its latest sensor readings.

        All reading lists should cover the same time window (e.g. the last
        24 hours of 1-Hz data). Having them the same length is recommended
        but not strictly required.

        miner_damage_ratio comes from FatigueEngine.calculate_damage() and
        represents the fraction of fatigue life consumed (0.0 = none, 1.0 = end).
        """
        # Pool all channels to check minimum data requirement
        total_readings = len(strain_readings) + len(vibration_readings) + len(temperature_readings)
        if total_readings < MIN_READINGS_REQUIRED:
            raise InsufficientReadingsError(
                element_id=element_id,
                got=total_readings,
                required=MIN_READINGS_REQUIRED,
            )

        strain_score      = self._score_strain(strain_readings)
        vibration_score   = self._score_vibration(vibration_readings)
        temperature_score = self._score_temperature(temperature_readings)
        fatigue_score     = self._score_fatigue(miner_damage_ratio)

        # Weighted combination
        shi = (
            SHI_WEIGHTS["strain_score"]      * strain_score +
            SHI_WEIGHTS["vibration_score"]   * vibration_score +
            SHI_WEIGHTS["fatigue_score"]     * fatigue_score +
            SHI_WEIGHTS["temperature_score"] * temperature_score
        )
        shi = float(np.clip(shi, 0.0, 100.0))

        status = self._classify(shi)

        logger.debug(
            "SHI for %s: %.1f (%s) | strain=%.1f vib=%.1f temp=%.1f fat=%.1f",
            element_id, shi, status, strain_score, vibration_score,
            temperature_score, fatigue_score,
        )

        return SHIResult(
            element_id=element_id,
            shi_score=round(shi, 2),
            strain_score=round(strain_score, 2),
            vibration_score=round(vibration_score, 2),
            temperature_score=round(temperature_score, 2),
            fatigue_score=round(fatigue_score, 2),
            status=status,
            reading_count=total_readings,
            notes=self._generate_notes(shi, miner_damage_ratio),
        )

    def compute_batch(
        self,
        element_readings: list[dict],
    ) -> list[SHIResult]:
        """
        Convenience method to score multiple elements at once.
        Each dict in element_readings must match the keyword args of compute().

        Errors for individual elements are caught and logged so one bad element
        doesn't abort the entire batch.
        """
        results = []
        for item in element_readings:
            try:
                result = self.compute(**item)
                results.append(result)
            except InsufficientReadingsError as exc:
                logger.warning("Skipping SHI for %s: %s", item.get("element_id"), exc)
        return results

    # -----------------------------------------------------------------------
    # Sub-score calculators
    # Each returns a float in [0, 100], where 100 = perfectly within safe limits.
    # -----------------------------------------------------------------------

    def _score_strain(self, readings: list[float]) -> float:
        """
        Score based on the 95th percentile strain value.
        We use the P95 (not the max) to be robust against occasional noise spikes.
        """
        if not readings:
            return 100.0  # no readings → assume healthy (no evidence of damage)

        p95 = float(np.percentile(np.abs(readings), 95))
        limits = SENSOR_LIMITS["strain"]

        return self._piecewise_score(p95, limits["warning_max"], limits["critical_max"])

    def _score_vibration(self, readings: list[float]) -> float:
        """Score based on the RMS vibration level (mean of all readings)."""
        if not readings:
            return 100.0

        rms = float(np.sqrt(np.mean(np.square(readings))))
        limits = SENSOR_LIMITS["vibration"]
        return self._piecewise_score(rms, limits["warning_max"], limits["critical_max"])

    def _score_temperature(self, readings: list[float]) -> float:
        """
        Score based on the maximum temperature recorded.
        High temperatures can degrade material properties and cause expansion cracking.
        """
        if not readings:
            return 100.0

        max_temp = float(np.max(readings))
        limits = SENSOR_LIMITS["temperature"]
        return self._piecewise_score(max_temp, limits["warning_max"], limits["critical_max"])

    def _score_fatigue(self, damage_ratio: float) -> float:
        """
        Map Miner's cumulative damage ratio D → sub-score.
          D = 0.0 → score = 100 (no fatigue consumed)
          D = 0.5 → score = 50  (halfway through fatigue life)
          D = 1.0 → score = 0   (fatigue failure criterion reached)
        """
        # Linear inversion: score = (1 - D) × 100
        score = (1.0 - float(np.clip(damage_ratio, 0.0, 1.0))) * 100.0
        return float(score)

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _piecewise_score(value: float, warning: float, critical: float) -> float:
        """
        Map a sensor value to a health sub-score using two breakpoints:

          value ≤ warning  → score is 100 → 60  (linearly declining)
          value ≤ critical → score is 60  → 0   (linearly declining)
          value > critical → score is 0

        This is deliberately simpler than a sigmoid curve for auditability.
        Auditors can verify the score by plugging numbers into these formulas.
        """
        if value <= 0:
            return 100.0
        if value <= warning:
            # 100 down to 60 across the "safe" band
            return 100.0 - (value / warning) * 40.0
        if value <= critical:
            # 60 down to 0 across the "warning" band
            fraction = (value - warning) / (critical - warning)
            return 60.0 * (1.0 - fraction)
        # Beyond critical — full alarm
        return 0.0

    def _classify(self, shi: float) -> str:
        """Return a status string based on the SHI thresholds."""
        if shi >= self.warning_threshold:
            return "HEALTHY"
        if shi >= self.critical_threshold:
            return "WARNING"
        return "CRITICAL"

    @staticmethod
    def _generate_notes(shi: float, damage_ratio: float) -> Optional[str]:
        """Return a human-readable one-liner about the SHI result for the report."""
        if shi >= 80:
            return "Structure is within normal operating parameters."
        if shi >= 65:
            return "Minor deviations detected; continue routine monitoring."
        if shi >= 40:
            return (
                f"Elevated stress detected. Miner damage ratio at {damage_ratio:.2f}. "
                "Schedule inspection within 30 days."
            )
        return (
            "CRITICAL: Multiple sensors outside safe range. "
            "Immediate structural inspection required."
        )
