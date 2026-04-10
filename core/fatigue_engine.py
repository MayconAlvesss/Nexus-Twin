"""
NexusTwin — Fatigue Engine (Miner's Rule)
==========================================
Implements Palmgren-Miner's linear damage accumulation rule for predicting
the remaining fatigue life of structural elements.

The fundamental equation is:
    D = Σ (nᵢ / Nᵢ)

Where:
    nᵢ  = observed number of cycles at stress range Δσᵢ
    Nᵢ  = number of cycles to failure at Δσᵢ (from the S-N curve)
    D   = cumulative damage ratio (failure when D ≥ 1.0)

S-N curve (Wöhler) formula used here:
    log₁₀(N) = log₁₀(A) - m × log₁₀(Δσ)
    ∴ N = A / (Δσ^m)

References:
    - Palmgren (1924) & Miner (1945) — original damage accumulation theory
    - EN 1993-1-9:2005 (Eurocode 3 Part 1-9) — fatigue for steel structures
    - ACI 215R-74 — considerations for design of concrete structures subject to fatigue
    - AASHTO LRFD Bridge Design Specifications (9th ed.) — cycle counting methodology

Limitations (intentionally kept simple for this portfolio project):
    - Uses simplified constant-amplitude stress blocks (not rainflow counting)
    - Does not model mean stress effects (Goodman correction)
    - Assumes linear damage accumulation (non-linear interaction neglected)
"""

import logging
import math
from dataclasses import dataclass
from typing import Optional

import numpy as np

from config.thresholds import SN_CURVES, DAMAGE_LIMIT_WARNING, DAMAGE_LIMIT_SAFE
from core.exceptions import FatigueCalculationError

logger = logging.getLogger(__name__)


@dataclass
class StressBlock:
    """
    Represents a group of cycles at a constant stress range amplitude.

    In a real fatigue analysis you'd extract these from rainflow counting on
    a stress time-series (see ASTM E1049). Here we accept them directly from
    the caller to keep the engine logic separate from the signal processing.
    """
    stress_range_mpa: float   # Δσ — peak-to-valley stress range (MPa)
    cycle_count: int          # nᵢ — number of cycles counted at this stress level


@dataclass
class FatigueResult:
    """
    Full result of a Miner's Rule calculation for one structural element.
    """
    element_id:       str
    material_class:   str
    damage_ratio:     float    # D = Σ(nᵢ/Nᵢ), failure criterion D ≥ 1.0
    remaining_life_pct: float  # (1 - D) × 100, convenience field
    status:           str      # "SAFE" | "WARNING" | "FAILED"
    total_cycles:     int      # Σnᵢ — total counted cycles
    notes:            Optional[str] = None


class FatigueEngine:
    """
    Computes Palmgren-Miner cumulative damage for a list of stress blocks.

    Usage:
        engine = FatigueEngine()
        blocks = [
            StressBlock(stress_range_mpa=60.0, cycle_count=10_000),
            StressBlock(stress_range_mpa=40.0, cycle_count=50_000),
        ]
        result = engine.calculate_damage(
            element_id="BEAM-012",
            material_class="steel",
            stress_blocks=blocks,
        )
    """

    def calculate_damage(
        self,
        element_id: str,
        material_class: str,
        stress_blocks: list[StressBlock],
    ) -> FatigueResult:
        """
        Apply Miner's Rule across all stress blocks.

        Returns a FatigueResult with the cumulative damage ratio D and
        a status classification.
        """
        if not stress_blocks:
            # No stress data — assume no damage (conservative side: D = 0)
            return FatigueResult(
                element_id=element_id,
                material_class=material_class,
                damage_ratio=0.0,
                remaining_life_pct=100.0,
                status="SAFE",
                total_cycles=0,
                notes="No stress data provided; assumed zero fatigue damage.",
            )

        sn = SN_CURVES.get(material_class, SN_CURVES["generic"])
        if material_class not in SN_CURVES:
            logger.warning(
                "Material class '%s' not in S-N curve table; using 'generic' fallback.",
                material_class,
            )

        cumulative_damage = 0.0
        total_cycles = 0

        for block in stress_blocks:
            delta_sigma = block.stress_range_mpa

            # Skip stress ranges below the endurance limit (if the material has one).
            # Below this threshold, the material theoretically never fails in fatigue.
            if sn.endurance_limit_mpa > 0 and delta_sigma <= sn.endurance_limit_mpa:
                logger.debug(
                    "Element %s: Δσ=%.1f MPa is below endurance limit %.1f MPa — skipping.",
                    element_id, delta_sigma, sn.endurance_limit_mpa,
                )
                continue

            # Protect against zero or negative stress ranges (bad input data)
            if delta_sigma <= 0:
                raise FatigueCalculationError(
                    element_id, f"stress_range_mpa must be > 0, got {delta_sigma}"
                )

            # Wöhler equation:  N = A / (Δσ^m)
            cycles_to_failure = sn.A / (delta_sigma ** sn.m)

            if cycles_to_failure <= 0 or not math.isfinite(cycles_to_failure):
                raise FatigueCalculationError(
                    element_id,
                    f"S-N calculation produced invalid Nᵢ={cycles_to_failure} "
                    f"for Δσ={delta_sigma} MPa.",
                )

            # Miner's partial damage for this block
            partial_damage = block.cycle_count / cycles_to_failure
            cumulative_damage += partial_damage
            total_cycles += block.cycle_count

            logger.debug(
                "Block Δσ=%.1f MPa | n=%d | N=%.2e | d=%.6f | D_cum=%.6f",
                delta_sigma, block.cycle_count, cycles_to_failure,
                partial_damage, cumulative_damage,
            )

        remaining_pct = max(0.0, (1.0 - cumulative_damage) * 100.0)
        status = self._classify_damage(cumulative_damage)

        return FatigueResult(
            element_id=element_id,
            material_class=material_class,
            damage_ratio=round(cumulative_damage, 6),
            remaining_life_pct=round(remaining_pct, 2),
            status=status,
            total_cycles=total_cycles,
            notes=self._generate_notes(cumulative_damage, material_class),
        )

    def estimate_remaining_life_years(
        self,
        damage_ratio: float,
        element_age_years: float,
    ) -> Optional[float]:
        """
        Extrapolate remaining service life in years, assuming the damage rate
        stays constant from here on.

        Formula:  remaining = age × (1 - D) / D

        Returns None if D == 0 (infinite life estimate — can't extrapolate).
        """
        if damage_ratio <= 0:
            return None   # no damage yet — can't extrapolate rate
        if damage_ratio >= 1.0:
            return 0.0    # already at or past failure criterion

        return round(element_age_years * (1.0 - damage_ratio) / damage_ratio, 1)

    @staticmethod
    def _classify_damage(damage_ratio: float) -> str:
        if damage_ratio < DAMAGE_LIMIT_SAFE:
            return "SAFE"
        if damage_ratio < DAMAGE_LIMIT_WARNING:
            return "WARNING"
        if damage_ratio < 1.0:
            return "WARNING"   # >75% but not yet failed — still warnable
        return "FAILED"

    @staticmethod
    def _generate_notes(damage_ratio: float, material_class: str) -> str:
        if damage_ratio < DAMAGE_LIMIT_SAFE:
            return f"{material_class.capitalize()} element is within safe fatigue life."
        if damage_ratio < 1.0:
            return (
                f"{damage_ratio*100:.1f}% of fatigue life consumed. "
                "Increase inspection frequency and monitor for crack propagation."
            )
        return (
            f"Miner's damage criterion exceeded (D={damage_ratio:.4f} ≥ 1.0). "
            "Element should be considered for replacement or major reinforcement."
        )
