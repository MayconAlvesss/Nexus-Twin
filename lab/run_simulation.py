"""
NexusTwin — Lab Simulation Runner
====================================
Standalone end-to-end simulation script for the NexusTwin system.
No API server is required — everything runs in-process.

Purpose:
  1. Demonstrate the full engine pipeline: sensors → anomaly detection → SHI
  2. Validate that all engines produce sensible output together
  3. Provide a quick smoke-test for CI without needing a running server

Usage:
    python lab/run_simulation.py

What it does:
  - Creates one sensor suite per structural element (column, beam, slab)
  - Runs 300 simulation ticks (≈ 5 minutes of 1-Hz data)
  - Injects a degradation ramp at tick 200 to trigger anomalies and SHI drops
  - Computes SHI and fatigue at the end of each element's data window
  - Trains and runs the AnomalyDetector on the collected data
  - Prints a colour-coded summary table to stdout
"""

import sys
import os
import logging

# Allow running from the project root without installing as a package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.sensor_model        import create_sensor_suite
from core.anomaly_detector    import AnomalyDetector
from core.structural_health_engine import StructuralHealthEngine
from core.fatigue_engine       import FatigueEngine, StressBlock
from datetime                 import datetime, timezone

logging.basicConfig(
    level=logging.WARNING,                    # suppress DEBUG/INFO for cleaner output
    format="%(levelname)s | %(name)s | %(message)s"
)

TICK_COUNT    = 300
RAMP_START    = 200   # tick at which we start injecting degradation
RAMP_STEP     = 5.0   # µε increase per tick in strain base signal

# Elements to simulate
ELEMENTS = [
    {"id": "COL-001", "name": "Ground Floor Column A",    "material": "concrete"},
    {"id": "BM-012",  "name": "Level 3 Transfer Beam B",  "material": "steel"},
    {"id": "SLB-007", "name": "Basement Slab C",          "material": "concrete"},
]

SHI_ENGINE     = StructuralHealthEngine(warning_threshold=65.0, critical_threshold=40.0)
FATIGUE_ENGINE = FatigueEngine()


def run() -> None:
    print("\n" + "="*72)
    print("  NexusTwin — Lab Simulation Runner v1.0")
    print("="*72)

    results = []

    for elem in ELEMENTS:
        eid = elem["id"]
        suite = create_sensor_suite(eid)

        strain_readings:      list[float] = []
        vibration_readings:   list[float] = []
        temperature_readings: list[float] = []

        # Fit the anomaly detector with the first 100 ticks (baseline)
        print(f"\n[..] Collecting baseline for {eid}...")

        detector = AnomalyDetector(element_id=eid)

        for tick in range(TICK_COUNT):
            ts = datetime.now(timezone.utc).isoformat()

            # Inject degradation ramp starting at RAMP_START
            if tick == RAMP_START:
                suite["strain"].set_base_signal(400.0)   # ramp up from normal 150 µε

            if tick > RAMP_START and tick % 10 == 0:
                current = suite["strain"]._base_signal
                suite["strain"].set_base_signal(current + RAMP_STEP)

            strain_r  = suite["strain"].read(ts)
            vib_r     = suite["vibration"].read(ts)
            temp_r    = suite["temperature"].read(ts)

            strain_readings.append(strain_r.value)
            vibration_readings.append(vib_r.value)
            temperature_readings.append(temp_r.value)

            # Fit the IsolationForest after 100 baseline ticks
            if tick == 99:
                detector.fit(
                    strain_data      = strain_readings[:],
                    vibration_data   = vibration_readings[:],
                    temperature_data = temperature_readings[:],
                )
                print(f"  [OK] IsolationForest fitted for {eid} (baseline n=100)")

        # Run anomaly detection on all remaining ticks
        total_anomalies = []
        for i in range(100, TICK_COUNT):
            ts = datetime.now(timezone.utc).isoformat()
            anomalies = detector.detect(
                strain_value      = strain_readings[i],
                vibration_value   = vibration_readings[i],
                temperature_value = temperature_readings[i],
                timestamp         = ts,
            )
            total_anomalies.extend(anomalies)

        # Compute SHI from full reading window
        shi_result = SHI_ENGINE.compute(
            element_id           = eid,
            strain_readings      = strain_readings,
            vibration_readings   = vibration_readings,
            temperature_readings = temperature_readings,
            miner_damage_ratio   = 0.18,   # simulated for demo
        )

        # Compute fatigue from simplified stress blocks.
        # Stress ranges are kept material-appropriate:
        #   concrete → low service stress (~5 MPa), concrete has NO endurance limit
        #   steel    → moderate stress range (60 MPa), below the 71 MPa reference
        if elem["material"] == "concrete":
            stress_blocks = [
                StressBlock(stress_range_mpa=4.0,  cycle_count=5_000),
                StressBlock(stress_range_mpa=6.0,  cycle_count=20_000),
                StressBlock(stress_range_mpa=3.0,  cycle_count=50_000),
            ]
        else:
            stress_blocks = [
                StressBlock(stress_range_mpa=60.0, cycle_count=5_000),
                StressBlock(stress_range_mpa=45.0, cycle_count=20_000),
                StressBlock(stress_range_mpa=30.0, cycle_count=50_000),
            ]
        fatigue_result = FATIGUE_ENGINE.calculate_damage(
            element_id     = eid,
            material_class = elem["material"],
            stress_blocks  = stress_blocks,
        )

        results.append({
            "id":       eid,
            "name":     elem["name"],
            "shi":      shi_result.shi_score,
            "status":   shi_result.status,
            "fatigue":  fatigue_result.damage_ratio,
            "fat_stat": fatigue_result.status,
            "anomalies": len(total_anomalies),
        })

    # Print summary table
    print("\n" + "-"*72)
    print(f"  {'ELEMENT':<14} {'SHI':>6}  {'SHI STATUS':<10}  "
          f"{'FATIGUE D':>9}  {'FAT STATUS':<10}  {'ANOMALIES':>9}")
    print("-"*72)
    for r in results:
        shi_flag  = "[OK]" if r["status"] == "HEALTHY"  else ("[!!]" if r["status"] == "WARNING" else "[**]")
        fat_flag  = "[OK]" if r["fat_stat"] == "SAFE"   else ("[!!]" if r["fat_stat"] == "WARNING" else "[XX]")
        anom_flag = "[!]" if r["anomalies"] > 0 else " "
        print(
            f"  {r['id']:<14} {r['shi']:>6.1f}  {shi_flag} {r['status']:<8}  "
            f"{r['fatigue']:>9.4f}  {fat_flag} {r['fat_stat']:<8}  "
            f"{anom_flag} {r['anomalies']:>3} events"
        )
    print("-"*72)
    print("\n[DONE] Simulation complete.\n")


if __name__ == "__main__":
    run()
