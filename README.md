# Nexus-Twin: Structural Health Engine API

**Structural simulation, anomaly detection, and ML forecasting service for digital twin infrastructure.**

```bash
# Get current cluster health status
curl -X GET "http://localhost:8000/v1/status" \
     -H "X-Nexus-API-Key: your_key"
```

## 📡 API Endpoints

### Element Registry
- `POST /v1/elements`: Register a physical BIM element for tracking.
- `GET /v1/elements/{id}`: Retrieve current element snapshot and SHI.

### Health & Analytics
- `POST /v1/compute/health`: Process composite SHI from multi-channel sensor payloads (Strain, Vibration, Temp).
- `POST /v1/compute/fatigue`: Calculate linear damage accumulation (Palmgren-Miner).
- `POST /v1/detect/anomaly`: Execute two-layer detection (Z-Score + Isolation Forest).

### Prediction & Forecasting
- `GET /v1/forecast/{id}`: Predict SHI trajectory for T+7 days using Random Forest.

## 📦 Data Schema (Sensor Ingestion)
```json
{
  "element_id": "COL-10",
  "data": {
    "strain": 140.5,
    "vibration": 0.05,
    "temperature": 32.1
  },
  "timestamp": "2026-04-10T20:00:00Z"
}
```

## 🏗️ Core Architecture
1. **API Layer (`/api`)**: Async FastAPI implementation with Pydantic v2 validation.
2. **Logic Layer (`/core`)**: Domain engines for structural math and anomaly pipelines.
3. **Storage Layer (`/database`)**: Persistent `aiosqlite` history and element metadata.

## 🚀 Quick Setup
```bash
# 1. Install
pip install -r requirements.txt

# 2. Configure
cp .env.example .env

# 3. Serve
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

---
*Nexus-Twin Framework | Systems & Architecture by Maycon Alves.*
