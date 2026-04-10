"""
NexusTwin — Structural Thresholds & Alert Limits
=================================================
Centralised lookup tables for:
  - Safe operating ranges per sensor type and material class
  - Fatigue damage limits (Miner's Rule cumulative damage ratio)
  - S-N curve parameters (σ_r / N cycles at reference stress)

These values are sourced from:
  - EN 1993-1-9:2005 (Eurocode 3 — fatigue for steel)
  - ACI 215R-74 (fatigue of concrete)
  - ISO 13381-1:2015 (condition monitoring and diagnostics)
  - RICS Condition Monitoring Best Practice Note 2022
"""

from dataclasses import dataclass
from typing import Dict


# ---------------------------------------------------------------------------
# Sensor operating limits (safe ranges for each reading type)
# Units: strain → microstrain (µε), vibration → mm/s RMS, temp → °C
# ---------------------------------------------------------------------------
SENSOR_LIMITS: Dict[str, Dict[str, float]] = {
    "strain": {
        "safe_max":    800.0,   # µε — typical concrete cracking threshold
        "warning_max": 600.0,   # µε — yellow alert
        "critical_max": 900.0,  # µε — immediate inspection required
    },
    "vibration": {
        "safe_max":    2.5,     # mm/s RMS — ISO 10816 Zone A
        "warning_max": 4.5,     # mm/s RMS — Zone B (still acceptable)
        "critical_max": 7.1,    # mm/s RMS — Zone C (reduced acceptability)
    },
    "temperature": {
        "safe_max":    50.0,    # °C — ambient max for structural concrete
        "warning_max": 60.0,    # °C
        "critical_max": 80.0,   # °C — risk of differential thermal stress
    },
}


# ---------------------------------------------------------------------------
# S-N Curve parameters per material class
# Wöhler equation:  log(N) = log(A) - m * log(Δσ)
#   A   → material constant (cycles at reference stress range)
#   m   → slope of the S-N curve
#   Δσ_ref_mpa → reference stress range (MPa) at A cycles
#
# Sources:
#   Steel → EN 1993-1-9 Table B.1, Detail Category 71
#   Concrete → ACI 215R-74, modified Aas-Jakobsen equation
#   Timber → BS 5268-2, Table 5 (bending fatigue)
# ---------------------------------------------------------------------------
@dataclass
class SNParameters:
    """S-N curve parameters for Miner's Rule fatigue calculation."""
    A: float         # material constant (reference cycles)
    m: float         # slope exponent
    delta_sigma_ref_mpa: float   # reference stress range (MPa)
    endurance_limit_mpa: float   # below this Δσ, fatigue damage is negligible


SN_CURVES: Dict[str, SNParameters] = {
    "steel": SNParameters(
        A=3.98e12,
        m=3.0,
        delta_sigma_ref_mpa=71.0,
        endurance_limit_mpa=52.0,
    ),
    "concrete": SNParameters(
        A=1.00e10,
        m=10.0,             # concrete has a much steeper S-N slope
        delta_sigma_ref_mpa=14.5,
        endurance_limit_mpa=0.0,    # concrete has NO endurance limit
    ),
    "timber": SNParameters(
        A=5.00e9,
        m=8.0,
        delta_sigma_ref_mpa=20.0,
        endurance_limit_mpa=7.0,
    ),
    "aluminium": SNParameters(
        A=1.00e9,
        m=6.85,
        delta_sigma_ref_mpa=35.0,
        endurance_limit_mpa=0.0,    # aluminium has NO endurance limit
    ),
    "masonry": SNParameters(
        A=5.00e8,
        m=12.0,
        delta_sigma_ref_mpa=8.0,
        endurance_limit_mpa=3.5,
    ),
    "generic": SNParameters(
        A=2.00e10,
        m=5.0,
        delta_sigma_ref_mpa=30.0,
        endurance_limit_mpa=10.0,
    ),
}


# ---------------------------------------------------------------------------
# Miner's cumulative damage ratio limit
# D < DAMAGE_LIMIT_SAFE    → healthy
# D < DAMAGE_LIMIT_WARNING → monitor closely
# D ≥ DAMAGE_LIMIT_FAIL    → element has exceeded fatigue life
# ---------------------------------------------------------------------------
DAMAGE_LIMIT_SAFE      = 0.50   # 50% of fatigue life consumed
DAMAGE_LIMIT_WARNING   = 0.75   # 75%
DAMAGE_LIMIT_FAIL      = 1.00   # Miner's failure criterion


# ---------------------------------------------------------------------------
# Structural Health Index weights
# The SHI is a weighted sum of normalised sub-scores.
# Weights must sum to 1.0.
# ---------------------------------------------------------------------------
SHI_WEIGHTS: Dict[str, float] = {
    "strain_score":    0.35,   # highest weight — direct measure of load
    "vibration_score": 0.25,   # dynamic response
    "fatigue_score":   0.25,   # accumulated life consumption
    "temperature_score": 0.15, # environmental stress
}

assert abs(sum(SHI_WEIGHTS.values()) - 1.0) < 1e-9, "SHI weights must sum to 1.0"
