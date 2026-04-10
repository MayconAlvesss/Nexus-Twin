"""
NexusTwin — Sensor Model
==========================
Defines the three sensor types used by the digital twin:
  - StrainSensor      → measures structural deformation (microstrain, µε)
  - AccelerometerSensor → measures vibration (mm/s RMS)
  - TemperatureSensor → measures surface/ambient temperature (°C)

Each sensor can generate a realistic simulated reading via .read(), which
applies Gaussian noise around a base signal. In a real deployment you'd
replace read() with an async call to your IoT broker (MQTT, Azure IoT Hub, etc.).

Design note:
  Using dataclasses instead of Pydantic here because these are internal
  runtime objects, not API boundary objects. Pydantic schemas live in ingestion/.
"""

import math
import random
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from core.exceptions import SensorReadingError

logger = logging.getLogger(__name__)


class SensorType(str, Enum):
    STRAIN        = "strain"
    VIBRATION     = "vibration"
    TEMPERATURE   = "temperature"


@dataclass
class SensorReading:
    """A single timestamped measurement from any sensor."""
    sensor_id:  str
    element_id: str
    sensor_type: SensorType
    value: float       # magnitude in the sensor's native unit
    unit: str          # µε | mm/s | °C
    timestamp: str     # ISO 8601 string — populated by the simulator or IoT broker


@dataclass
class BaseSensor:
    """
    Abstract base for all sensor types.
    Subclasses override _bounds and _unit and optionally _noise_std.
    """
    sensor_id:          str
    element_id:         str          # which structural element this is bonded to
    calibration_factor: float = 1.0  # applied after reading to correct for drift
    sampling_rate_hz:   float = 1.0  # how often (per second) the sensor fires

    # Internal — subclasses set these
    _sensor_type: SensorType = field(init=False)
    _unit: str               = field(init=False)
    _base_signal: float      = field(init=False, default=0.0)
    _noise_std: float        = field(init=False, default=1.0)

    def read(self, timestamp: str) -> SensorReading:
        """
        Produce one reading. Adds Gaussian noise to the base signal
        and applies the calibration factor.

        In production, override this to pull from an IoT broker.
        """
        raw = random.gauss(self._base_signal, self._noise_std)
        calibrated = raw * self.calibration_factor

        # Clamp to physically possible range
        low, high = self._bounds()
        calibrated = max(low, min(high, calibrated))

        # Sanity check — catch sensors that are clearly broken
        if not math.isfinite(calibrated):
            raise SensorReadingError(self.sensor_id, calibrated, self._unit)

        return SensorReading(
            sensor_id=self.sensor_id,
            element_id=self.element_id,
            sensor_type=self._sensor_type,
            value=round(calibrated, 4),
            unit=self._unit,
            timestamp=timestamp,
        )

    def _bounds(self) -> tuple[float, float]:
        """Override in subclass to define valid reading range."""
        return (-1e9, 1e9)

    def set_base_signal(self, value: float) -> None:
        """
        Adjust the simulated base signal (e.g. to simulate increasing load
        over time in the lab/run_simulation.py demo).
        """
        self._base_signal = value


@dataclass
class StrainSensor(BaseSensor):
    """
    Resistance strain gauge measuring deformation.
    Typical unit: microstrain (µε = 10⁻⁶ m/m).
    Positive = tension, negative = compression.

    Working range for structural concrete: ±2000 µε
    Cracking typically occurs around +600–800 µε in unreinforced zones.
    """

    def __post_init__(self) -> None:
        self._sensor_type = SensorType.STRAIN
        self._unit = "µε"
        self._base_signal = 150.0    # healthy resting strain (light dead load)
        self._noise_std = 12.0       # realistic gauge noise at 1 Hz

    def _bounds(self) -> tuple[float, float]:
        return (-2500.0, 2500.0)


@dataclass
class AccelerometerSensor(BaseSensor):
    """
    Piezoelectric accelerometer measuring structural vibration.
    Output is converted to velocity RMS (mm/s) for ISO 10816 compliance.

    ISO 10816-3 Zone boundaries:
      A → ≤ 2.3 mm/s (new/just-commissioned machine or structure)
      B → 2.3–4.5 mm/s (acceptable for long-term operation)
      C → 4.5–7.1 mm/s (reduced acceptability — monitor closely)
      D → > 7.1 mm/s   (damaging condition — immediate action required)
    """

    def __post_init__(self) -> None:
        self._sensor_type = SensorType.VIBRATION
        self._unit = "mm/s"
        self._base_signal = 1.2     # typical ambient vibration for a healthy structure
        self._noise_std = 0.15

    def _bounds(self) -> tuple[float, float]:
        # Vibration is always positive (RMS)
        return (0.0, 50.0)


@dataclass
class TemperatureSensor(BaseSensor):
    """
    Thermocouple or PT100 sensor measuring structural surface temperature.
    Used to detect differential thermal expansion and potential cracking.

    Reference: EN 1992-1-2 — temperature effects on concrete strength.
    """

    def __post_init__(self) -> None:
        self._sensor_type = SensorType.TEMPERATURE
        self._unit = "°C"
        self._base_signal = 22.0    # indoor ambient temperature
        self._noise_std = 0.5

    def _bounds(self) -> tuple[float, float]:
        # Structural materials rarely go below -40 or above 150°C in buildings
        return (-40.0, 150.0)


def create_sensor_suite(element_id: str, suffix: str = "") -> dict[str, BaseSensor]:
    """
    Factory that returns one of each sensor type for a given element.
    The suffix lets you attach multiple suites to the same element
    (e.g. top/bottom of a beam).

    Returns a dict keyed by sensor type string for easy lookup.
    """
    tag = f"{element_id}{suffix}"
    return {
        "strain":      StrainSensor(sensor_id=f"STR-{tag}",  element_id=element_id),
        "vibration":   AccelerometerSensor(sensor_id=f"VIB-{tag}", element_id=element_id),
        "temperature": TemperatureSensor(sensor_id=f"TMP-{tag}", element_id=element_id),
    }
