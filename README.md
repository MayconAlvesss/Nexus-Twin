# 🏗️ Nexus-Twin: Structural Digital Twin Engine

**Real-time structural health monitoring and ML-driven forecasting for BIM-connected assets.**

Nexus-Twin is a high-performance backend for managing Digital Twins. It translates raw sensor data (strain, vibration, fatigue) into a unified **Structural Health Index (SHI)**, enabling predictive maintenance and real-time anomaly detection.

---

## ⚡ Quick Start

### 1. Installation
```powershell
# Setup environment
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Configure defaults
copy .env.example .env
```

### 2. Launch the Engine
```powershell
python -m uvicorn api.main:app --reload --port 8000
```
Interactive API docs available at: `http://localhost:8000/docs`

---

## 🛠️ Developer Usage: The Simulation Loop

Nexus-Twin includes a built-in IoT simulator to exercise the health and anomaly pipelines without external hardware.

```python
import requests

API_URL = "http://localhost:8000/api/v1"
HEADERS = {"X-NexusTwin-API-Key": "your-dev-key"}

# 1. Register a physical element from BIM
requests.post(f"{API_URL}/elements", json={"id": "COL-A1", "type": "Column"}, headers=HEADERS)

# 2. Inject sensor data and compute SHI
sensor_payload = {
    "element_id": "COL-A1",
    "channels": {"strain": 120.5, "vibration": 0.02, "temp": 28.5}
}
response = requests.post(f"{API_URL}/health/compute", json=sensor_payload, headers=HEADERS)

print(f"Current Health Status: {response.json()['status']}")
```

---

## 🧠 Architectural Core

- **Fatigue Engine**: Linear damage accumulation using Palmgren-Miner rules (EN 1993-1-9 compliant SN curves).
- **Two-Layer Anomaly Detection**: 
    1. **Z-Score**: High-frequency spike detection (stateless).
    2. **Isolation Forest**: Multi-channel pattern recognition (trained on historical baseline).
- **ML Forecasting**: Random Forest Regressor predicting SHI trajectories (T+7 days).

---

## 📂 Internal Roadmap & WIP
- [x] Async SQLite Persistence (`aiosqlite`)
- [x] PDF Reporting Engine (`ReportLab`)
- [/] **Live WebSocket Stream** — *[Current Focus: Real-time telemetry feed]*
- [ ] **IFC Kernel Connector** — Direct Revit geometry synchronization via `ifcopenshell`

---

<div align="center">
  <i>Part of the <b>Nexus-Twin</b> Ecosystem</i><br>
  Designed by **Maycon Alves**
</div>
