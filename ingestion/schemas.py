"""
NexusTwin — Ingestion Schemas (Pydantic v2)
============================================
All request and response models used by the FastAPI layer live here.

Why keep schemas separate from domain models?
  Domain objects (SHIResult, FatigueResult, etc.) use plain dataclasses
  so they are fast and have no I/O coupling. Pydantic schemas handle:
    1. HTTP input validation (field types, ranges, required fields)
    2. Serialisation for JSON responses
  Keeping them in `ingestion/` mirrors the EcoBIM pattern where ingestion
  is responsible for validating what comes IN from external systems
  (Revit plugin, IoT broker, CSV upload).

Schema versioning note:
  These are v1 schemas. If we ever introduce breaking changes, bump to v2
  and keep v1 around for a deprecation window. The router prefix (/api/v1/)
  protects existing clients.
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Element registration — POST /api/v1/elements
# ---------------------------------------------------------------------------

class ElementRegisterRequest(BaseModel):
    """
    Payload sent by the BIM plugin or dashboard when adding a new structural
    element to the monitored twin.
    """
    element_id:     str  = Field(...,  min_length=1, max_length=64,  description="Unique BIM element ID (e.g. 'COLUMN-04A')")
    name:           str  = Field(...,  min_length=1, max_length=128, description="Human-readable label")
    element_type:   str  = Field(...,  description="COLUMN | BEAM | WALL | SLAB | TRUSS | OTHER")
    material_class: str  = Field(...,  description="steel | concrete | timber | aluminium | masonry | generic")
    age_years:      float = Field(0.0, ge=0.0, le=500.0, description="Element age in years")
    floor_level:    Optional[str] = Field(None, description="Floor/level tag, e.g. 'L3'")
    notes:          Optional[str] = Field(None, max_length=512)

    @field_validator("element_type")
    @classmethod
    def validate_element_type(cls, v: str) -> str:
        allowed = {"COLUMN", "BEAM", "WALL", "SLAB", "TRUSS", "OTHER"}
        if v.upper() not in allowed:
            raise ValueError(f"element_type must be one of {allowed}")
        return v.upper()

    @field_validator("material_class")
    @classmethod
    def validate_material_class(cls, v: str) -> str:
        allowed = {"steel", "concrete", "timber", "aluminium", "masonry", "generic"}
        if v.lower() not in allowed:
            raise ValueError(f"material_class must be one of {allowed}")
        return v.lower()


class ElementResponse(BaseModel):
    """Single element as returned by GET /api/v1/elements/{id}."""
    element_id:     str
    name:           str
    element_type:   str
    material_class: str
    age_years:      float
    floor_level:    Optional[str]
    notes:          Optional[str]
    created_at:     str
    updated_at:     str


# ---------------------------------------------------------------------------
# SHI computation — POST /api/v1/health/compute
# ---------------------------------------------------------------------------

class SensorReadingsBatch(BaseModel):
    """
    Multi-channel sensor data for a single structural element.
    All lists must cover the same time window (e.g. 24 h of 1-Hz data).
    Timestamps are validated but not required to be strictly monotonic —
    the SHI engine works on statistical summaries, not time-series order.
    """
    element_id:           str        = Field(..., description="Must exist in the element registry")
    strain_readings:      list[float] = Field(..., min_length=1, description="Strain in µε")
    vibration_readings:   list[float] = Field(..., min_length=1, description="Vibration in mm/s RMS")
    temperature_readings: list[float] = Field(..., min_length=1, description="Temperature in °C")

    # Fatigue block input (optional — can be computed separately via /fatigue endpoint)
    miner_damage_ratio: float = Field(
        0.0, ge=0.0, le=10.0,
        description="Cumulative Miner damage ratio D from FatigueEngine (0.0 if unknown)"
    )

    @field_validator("strain_readings", "vibration_readings", "temperature_readings")
    @classmethod
    def non_empty_readings(cls, v: list[float]) -> list[float]:
        if not v:
            raise ValueError("Reading list cannot be empty.")
        return v


class SHIComputeResponse(BaseModel):
    """Response returned by POST /api/v1/health/compute."""
    element_id:       str
    shi_score:        float
    strain_score:     float
    vibration_score:  float
    temperature_score: float
    fatigue_score:    float
    status:           str      # HEALTHY | WARNING | CRITICAL
    reading_count:    int
    notes:            Optional[str]


# ---------------------------------------------------------------------------
# Fatigue calculation — POST /api/v1/fatigue/compute
# ---------------------------------------------------------------------------

class StressBlockInput(BaseModel):
    """A constant-amplitude stress block for Miner's Rule."""
    stress_range_mpa: float = Field(..., gt=0, description="Δσ stress range in MPa")
    cycle_count:      int   = Field(..., gt=0, description="Number of cycles at this stress level")


class FatigueComputeRequest(BaseModel):
    """
    Payload for the fatigue endpoint.
    Stress blocks are typically extracted from strain gauge data via
    rainflow counting (see ASTM E1049). The API accepts them pre-processed
    to keep the engine logic simple.
    """
    element_id:     str              = Field(..., description="Monitored element ID")
    material_class: str              = Field(..., description="steel | concrete | timber | aluminium | masonry | generic")
    stress_blocks:  list[StressBlockInput] = Field(..., min_length=0)
    element_age_years: Optional[float] = Field(
        None, ge=0.0,
        description="If provided, the response includes a remaining life estimate in years"
    )


class FatigueComputeResponse(BaseModel):
    """Response from POST /api/v1/fatigue/compute."""
    element_id:          str
    material_class:      str
    damage_ratio:        float
    remaining_life_pct:  float
    remaining_life_years: Optional[float]   # None if age not provided
    status:              str              # SAFE | WARNING | FAILED
    total_cycles:        int
    notes:               Optional[str]


# ---------------------------------------------------------------------------
# Anomaly detection — POST /api/v1/anomaly/detect
# ---------------------------------------------------------------------------

class AnomalyDetectRequest(BaseModel):
    """
    Single timestep of multi-channel readings to run through the
    two-layer anomaly detector (Z-score + IsolationForest).
    The detector is stateful per element — historic buffer is held in memory.
    """
    element_id:        str   = Field(...)
    strain_value:      float = Field(...)
    vibration_value:   float = Field(..., ge=0.0)
    temperature_value: float = Field(...)
    timestamp:         Optional[str] = Field(
        None, description="ISO 8601 timestamp; defaults to server UTC now"
    )


class AnomalyRecord(BaseModel):
    """A single detected anomaly event."""
    anomaly_id:  str
    element_id:  str
    sensor_type: str
    severity:    str
    value:       float
    z_score:     Optional[float]
    timestamp:   str
    description: str


class AnomalyDetectResponse(BaseModel):
    """Response from POST /api/v1/anomaly/detect."""
    element_id:     str
    anomaly_count:  int
    anomalies:      list[AnomalyRecord]


# ---------------------------------------------------------------------------
# Simulation — POST /api/v1/simulate/tick
# ---------------------------------------------------------------------------

class SimulateTickRequest(BaseModel):
    """
    Request one simulated sensor tick for testing / demo purposes.
    Each tick reads all sensors attached to the given element and returns
    the raw readings without computing SHI or running anomaly detection.
    """
    element_id: str = Field(..., description="Element ID whose sensor suite to tick")


class SimulatedReadingResponse(BaseModel):
    """One simulated reading from a single sensor."""
    sensor_id:   str
    element_id:  str
    sensor_type: str
    value:       float
    unit:        str
    timestamp:   str


class SimulateTickResponse(BaseModel):
    """All sensor readings produced by a single simulation tick."""
    element_id: str
    tick_ts:    str
    readings:   list[SimulatedReadingResponse]
