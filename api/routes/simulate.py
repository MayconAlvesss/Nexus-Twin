"""
NexusTwin — Sensor Simulation Router
========================================
Development / demo endpoints that drive the sensor models to produce
synthetic readings. These are NOT protected by API key so the Swagger UI
and the lab/run_simulation.py script can call them freely.

Why a separate router for simulation?
  Production systems replace sensor.read() with real IoT broker calls.
  Keeping the simulation logic in its own router makes it easy to
  disable (just remove this router import in api/main.py) before going live.

Endpoints:
  POST /api/v1/simulate/register   — create a sensor suite for an element
  POST /api/v1/simulate/tick       — produce one reading from a sensor suite
  POST /api/v1/simulate/run        — run N ticks and return all readings
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from core.sensor_model import create_sensor_suite, BaseSensor
from ingestion.schemas import SimulateTickResponse, SimulatedReadingResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simulate", tags=["Sensor Simulation"])

# In-process sensor suite registry.
# Key: element_id, Value: dict of sensor_type → BaseSensor instance
_suites: dict[str, dict[str, BaseSensor]] = {}


@router.post(
    "/register",
    summary="Create a sensor suite for an element (no auth required for demo)",
)
async def register_sensor_suite(element_id: str) -> dict:
    """
    Instantiates one StrainSensor, AccelerometerSensor, and TemperatureSensor
    for the given element and registers them in the in-process registry.

    Idempotent — calling it again replaces the existing suite.
    """
    _suites[element_id] = create_sensor_suite(element_id)
    logger.info("Sensor suite registered for element %s.", element_id)
    return {
        "status":     "ok",
        "element_id": element_id,
        "sensors":    list(_suites[element_id].keys()),
    }


@router.post(
    "/tick",
    response_model=SimulateTickResponse,
    summary="Produce one simulated sensor reading tick",
)
async def simulate_tick(element_id: str) -> SimulateTickResponse:
    """
    Fires all sensors in the element's suite and returns their current
    readings. The base signals remain constant between ticks unless you
    use /simulate/inject to push an anomalous event.
    """
    suite = _suites.get(element_id)
    if not suite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No sensor suite for '{element_id}'. "
                   "Call POST /simulate/register first.",
        )

    ts = datetime.now(timezone.utc).isoformat()
    readings = []
    for sensor_type, sensor in suite.items():
        reading = sensor.read(ts)
        readings.append(
            SimulatedReadingResponse(
                sensor_id   = reading.sensor_id,
                element_id  = reading.element_id,
                sensor_type = reading.sensor_type.value,
                value       = reading.value,
                unit        = reading.unit,
                timestamp   = reading.timestamp,
            )
        )

    return SimulateTickResponse(
        element_id = element_id,
        tick_ts    = ts,
        readings   = readings,
    )


@router.post(
    "/run",
    summary="Run N simulation ticks and return all readings",
)
async def simulate_run(element_id: str, ticks: int = 10) -> dict:
    """
    Useful for quickly populating the database with test data.
    Returns all readings from N consecutive ticks so you can pipe them
    directly into POST /api/v1/health/compute.
    """
    if ticks < 1 or ticks > 10_000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ticks must be between 1 and 10,000.",
        )

    suite = _suites.get(element_id)
    if not suite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No sensor suite for '{element_id}'. Register it first.",
        )

    all_readings: list[dict] = []
    for _ in range(ticks):
        ts = datetime.now(timezone.utc).isoformat()
        for sensor in suite.values():
            r = sensor.read(ts)
            all_readings.append({
                "sensor_id":   r.sensor_id,
                "sensor_type": r.sensor_type.value,
                "value":       r.value,
                "unit":        r.unit,
                "timestamp":   r.timestamp,
            })

    return {
        "element_id": element_id,
        "ticks":      ticks,
        "readings":   all_readings,
    }


@router.post(
    "/inject",
    summary="Override a sensor's base signal to simulate a fault",
)
async def inject_signal(
    element_id:  str,
    sensor_type: str,
    base_signal: float,
) -> dict:
    """
    Manually set the base signal of a specific sensor to simulate a fault
    (e.g. increase strain base to 1500 µε to trigger a WARNING).

    sensor_type must be: strain | vibration | temperature
    """
    suite = _suites.get(element_id)
    if not suite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No sensor suite for '{element_id}'.",
        )

    sensor = suite.get(sensor_type)
    if not sensor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sensor type '{sensor_type}' not found. "
                   "Valid types: strain | vibration | temperature",
        )

    sensor.set_base_signal(base_signal)
    logger.info(
        "Signal injected for %s / %s: base=%.2f",
        element_id, sensor_type, base_signal,
    )
    return {
        "status":      "ok",
        "element_id":  element_id,
        "sensor_type": sensor_type,
        "new_base":    base_signal,
    }
