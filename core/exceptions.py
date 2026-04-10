"""
NexusTwin — Domain Exceptions
================================
Custom exception hierarchy for the NexusTwin engine.

Why custom exceptions instead of generic ValueError / RuntimeError?
  1. We can catch them specifically in the API layer and return the right HTTP codes.
  2. The error message is structured — callers get the context they need for logging.
  3. It makes the codebase self-documenting: if you see SensorReadingError, you know
     exactly which subsystem failed.
"""


class NexusTwinError(Exception):
    """Base class for all NexusTwin domain errors."""


# ---------------------------------------------------------------------------
# Sensor layer errors
# ---------------------------------------------------------------------------

class SensorReadingError(NexusTwinError):
    """Raised when a sensor reading is outside the physically possible range."""

    def __init__(self, sensor_id: str, value: float, unit: str) -> None:
        self.sensor_id = sensor_id
        self.value = value
        self.unit = unit
        super().__init__(
            f"Sensor '{sensor_id}' produced an invalid reading: {value} {unit}. "
            "Check calibration or sensor hardware."
        )


class SensorNotFoundError(NexusTwinError):
    """Raised when a requested sensor ID does not exist in the twin registry."""

    def __init__(self, sensor_id: str) -> None:
        self.sensor_id = sensor_id
        super().__init__(f"Sensor '{sensor_id}' is not registered in this digital twin.")


# ---------------------------------------------------------------------------
# Structural Health Index errors
# ---------------------------------------------------------------------------

class InsufficientReadingsError(NexusTwinError):
    """
    Raised when the SHI engine doesn't have enough historical readings to
    compute a statistically meaningful health score.
    """

    def __init__(self, element_id: str, got: int, required: int) -> None:
        self.element_id = element_id
        self.got = got
        self.required = required
        super().__init__(
            f"Element '{element_id}' has only {got} reading(s); "
            f"at least {required} are required for a reliable SHI."
        )


# ---------------------------------------------------------------------------
# Fatigue engine errors
# ---------------------------------------------------------------------------

class FatigueCalculationError(NexusTwinError):
    """Raised when the fatigue engine encounters an irrecoverable calculation error."""

    def __init__(self, element_id: str, detail: str) -> None:
        self.element_id = element_id
        super().__init__(
            f"Fatigue calculation failed for element '{element_id}': {detail}"
        )


# ---------------------------------------------------------------------------
# BIM / IFC ingestion errors
# ---------------------------------------------------------------------------

class IFCParsingError(NexusTwinError):
    """Raised when the IFC parser cannot read or interpret a model file."""

    def __init__(self, filepath: str, reason: str) -> None:
        self.filepath = filepath
        super().__init__(
            f"Failed to parse IFC file '{filepath}': {reason}"
        )


class ElementNotFoundError(NexusTwinError):
    """Raised when a BIM element ID is referenced but doesn't exist in the twin."""

    def __init__(self, element_id: str) -> None:
        self.element_id = element_id
        super().__init__(f"BIM element '{element_id}' was not found in the digital twin.")
