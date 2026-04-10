<p align="center">
  <img src="https://img.icons8.com/wired/128/007ACC/server.png" width="80" />
</p>

# <p align="center">Nexus-Twin</p>

<p align="center">
  <strong>High-Performance Backend for Structural Digital Twin Ecosystems.</strong><br>
  Real-time health monitoring, anomaly detection, and ML-driven forecasting for smart infrastructure.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/API-FastAPI-007ACC?style=flat-square" />
  <img src="https://img.shields.io/badge/ML-Scikit_Learn-007ACC?style=flat-square" />
  <img src="https://img.shields.io/badge/Storage-Async_SQLite-007ACC?style=flat-square" />
  <img src="https://img.shields.io/badge/Status-Production_Ready-444444?style=flat-square" />
</p>

---

## ⚡ API Quick Start
Nexus-Twin exposes a high-performance REST and WebSocket interface for managing structural assets on-site.

```bash
# Ingest sensor payload and compute Structural Health Index (SHI)
curl -X POST "http://localhost:8000/api/v1/health/compute" \
     -H "X-Nexus-API-Key: your_key" \
     -d '{"element_id": "COL-A1", "data": {"strain": 120.5, "vibration": 0.05}}'
```

---

## 🧠 Core Engineering Components

- **SHI Engine**: Computes a composite health score from multiple sensor channels.
- **Fatigue Engine**: Linear damage accumulation (Palmgren-Miner) compliant with EN 1993-1-9.
- **Two-Layer Anomaly Detection**:
  1. **Z-Score**: High-frequency spike detection.
  2. **Isolation Forest**: Multi-channel behavioral pattern recognition.
- **ML Forecasting**: Random Forest regressor for predicting SHI trajectories (T+7 days).

## 🏗️ Internal Roadmap

### 1. The API Layer (`/api`)
Built on **FastAPI (Python 3.12)** for asynchronous data ingestion and Pydantic v2 validation.

### 2. The Logic Layer (`/core`)
Domain-specific engines that decouple structural math from I/O operations.

### 3. Telemetry Lab (`/lab`)
- **`test_ws_client.py`**: A sandbox for testing real-time WebSocket telemetry streams.

---

## 🚀 Deployment

```bash
# 1. Setup
pip install -r requirements.txt
copy .env.example .env

# 2. Start
python -m uvicorn api.main:app --port 8000 --reload
```

---
<p align="center">
  <i>Part of the <b>Nexus-Twin</b> Ecosystem | Engineering Strategy by <b>Maycon Alves</b></i>
</p>
