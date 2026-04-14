# NexusTwin 🏗️ — Structural Digital Twin Engine

> [!IMPORTANT]
> **Project Status: Concept / Scaffold (2028+)**
> This repository is part of Maycon Alves' technical vision for the AEC Tech ecosystem. It is currently in the **concept and initial architecture phase**. Full development and core implementation will resume after the author returns from his mission in **2028**.




> **Real-time structural health monitoring, fatigue analysis, two-layer anomaly detection, and ML SHI forecasting for BIM-connected buildings.**  

---

## ✅ Status

> **Production-Ready Core Architecture.** Full FastAPI backend with 7 endpoints, async SQLite persistence, IsolationForest + Z-score anomaly detection, Random Forest SHI prediction, and automated PDF reporting. Designed as a serious portfolio piece following the same architectural standards as Aura EcoBIM.

---

## 🚀 Key Features

| Feature | Description |
|---|---|
| **Structural Health Index (SHI)** | 0–100 composite score from 4 weighted sensor channels — strain, vibration, temperature, and Miner fatigue damage |
| **Fatigue Engine** | Palmgren-Miner linear damage accumulation (EN 1993-1-9 / ACI 215R-74) with S-N curves for 5 material classes |
| **Two-Layer Anomaly Detection** | Z-score/CUSUM spike detector (stateless, microseconds) + IsolationForest (multi-channel pattern, trained at startup) |
| **ML SHI Forecasting** | Random Forest regressor predicts SHI T+7 snapshots ahead with a feature-importance breakdown and confidence band |
| **Async FastAPI Backend** | Secure, fully async API with API key auth, CORS, and request-timing middleware |
| **PDF Health Reports** | In-memory ReportLab/Matplotlib reports streamed as binary PDF — cover page, KPI table, trend chart, anomaly log, recommendations |
| **Async SQLite Persistence** | `aiosqlite`-backed element registry, SHI history, and anomaly audit log — ready to swap to PostgreSQL |
| **Sensor Simulation** | In-process sensor suite with Gaussian noise, calibration factors, fault injection — no IoT hardware required for demos |

---

## 🛠️ Technical Stack

| Layer | Technology |
|---|---|
| **API Framework** | Python 3.12, FastAPI, Uvicorn |
| **Data Validation** | Pydantic v2, pydantic-settings |
| **Structural Math** | NumPy, SciPy |
| **Machine Learning** | Scikit-learn (IsolationForest, RandomForestRegressor) |
| **Database** | SQLite (aiosqlite async driver) |
| **Reporting** | ReportLab, Matplotlib |
| **Testing** | Pytest, pytest-asyncio, FastAPI TestClient (httpx) |
| **Config** | Pydantic Settings + `.env` |

---

## 📂 Project Structure

```text
NexusTwin/
├── api/                         # FastAPI application
│   ├── main.py                  # App factory, lifespan, CORS, router registration
│   ├── middleware.py            # Performance-tracking middleware (X-Process-Time-Ms)
│   ├── dependencies.py          # FastAPI Depends() injectors (DB, auth)
│   └── routes/
│       ├── elements.py          # POST/GET /api/v1/elements — BIM element registry
│       ├── health.py            # POST /api/v1/health/compute — SHI scoring
│       ├── fatigue.py           # POST /api/v1/fatigue/compute — Miner's Rule
│       ├── anomaly.py           # POST /api/v1/anomaly/detect — two-layer detector
│       ├── simulate.py          # POST /api/v1/simulate/tick — sensor simulator
│       ├── prediction.py        # POST/GET /api/v1/predict — ML SHI forecast
│       └── reporting.py         # GET /api/v1/report/{id} — PDF report stream
│
├── core/                        # Pure domain engines (no I/O dependencies)
│   ├── sensor_model.py          # StrainSensor, AccelerometerSensor, TemperatureSensor
│   ├── structural_health_engine.py  # SHI composite scoring (piecewise linear)
│   ├── fatigue_engine.py        # Palmgren-Miner cumulative damage (EN 1993-1-9)
│   ├── anomaly_detector.py      # Z-score + IsolationForest detection pipeline
│   └── exceptions.py            # Typed domain exception hierarchy
│
├── ingestion/
│   └── schemas.py               # Pydantic v2 request/response models (API boundary)
│
├── database/
│   └── twin_db.py               # Async aiosqlite DB manager (element, SHI, anomaly tables)
│
├── ml/
│   └── health_predictor.py      # RandomForest SHI forecaster (T+7 prediction)
│
├── reporting/
│   └── pdf_report.py            # In-memory PDF report (ReportLab + Matplotlib)
│
├── config/
│   ├── settings.py              # Pydantic Settings (loaded from .env)
│   └── thresholds.py            # Sensor limits, S-N curves, SHI weights
│
├── security/
│   └── auth.py                  # FastAPI API-key guard (X-NexusTwin-API-Key header)
│
├── tests/
│   ├── test_core_engines.py     # Unit tests: engines, sensors, anomaly detector
│   └── test_api_integration.py  # Integration tests: full FastAPI TestClient suite
│
├── lab/
│   └── run_simulation.py        # Standalone end-to-end simulation demo (no server)
│
├── .env.example                 # Environment variable template
├── requirements.txt             # All Python dependencies (pinned)
└── pytest.ini                  # Test runner configuration
```

---

## ⚡ Quick Start

### Prerequisites

- Python **3.12+**
- pip (or conda)

---

### Step 1 — Environment Setup

```powershell
# Create an isolated virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install all dependencies
pip install -r requirements.txt
```

---

### Step 2 — Configure Environment

```powershell
# Copy the template
copy .env.example .env
```

Edit `.env` only if you want to change the API key or health thresholds:

```env
NEXUS_API_KEY=nexus-dev-key-change-me
NEXUS_HEALTH_WARNING_THRESHOLD=65
NEXUS_HEALTH_CRITICAL_THRESHOLD=40
NEXUS_ALLOWED_ORIGINS=http://localhost:5500,http://localhost:3000
NEXUS_DB_PATH=nexustwin.db
NEXUS_LOG_LEVEL=INFO
```

---

### Step 3 — Start the API

```powershell
python -m uvicorn api.main:app --reload --port 8000
```

Verify it is running:
```powershell
curl http://localhost:8000/
# → {"status": "NexusTwin Online", "version": "1.0.0", ...}
```

Interactive API docs: **http://localhost:8000/docs**

---

### Step 4 — Run the Lab Simulation (No Server Required)

The simulation runner exercises the full engine pipeline in-process with a
built-in degradation ramp and prints a colour-coded summary:

```powershell
python lab/run_simulation.py
```

Expected output:
```
========================================================================
  NexusTwin — Lab Simulation Runner v1.0
========================================================================

⏳  Collecting baseline for COL-001...
  ✔  IsolationForest fitted for COL-001 (baseline n=100)
...

------------------------------------------------------------------------
  ELEMENT        SHI  SHI STATUS    FATIGUE D  FAT STATUS   ANOMALIES
------------------------------------------------------------------------
  COL-001       72.3  🟢 HEALTHY    0.0009  ✅ SAFE         🔔  3 events
  BM-012        61.8  🟡 WARNING    0.0009  ✅ SAFE         🔔  5 events
  SLB-007       73.6  🟢 HEALTHY    0.0009  ✅ SAFE         🔔  2 events
------------------------------------------------------------------------
✅  Simulation complete.
```

---

### Step 5 — Run the Test Suite

```powershell
pytest tests/ -v
```

Expected: **≥20 tests** covering sensors, SHI, fatigue, anomaly, and all API endpoints.

---

## 🔗 API Endpoint Reference

All protected endpoints require: `X-NexusTwin-API-Key: <your-key>` header.

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/` | ❌ | Liveness probe |
| `POST` | `/api/v1/elements` | ✅ | Register / update BIM element |
| `GET` | `/api/v1/elements` | ✅ | List all registered elements |
| `GET` | `/api/v1/elements/{id}` | ✅ | Element detail + latest SHI |
| `POST` | `/api/v1/health/compute` | ✅ | Compute SHI from sensor data |
| `GET` | `/api/v1/health/{id}/history` | ✅ | SHI trend history |
| `POST` | `/api/v1/fatigue/compute` | ✅ | Miner's Rule fatigue damage |
| `POST` | `/api/v1/anomaly/detect` | ✅ | Two-layer anomaly detection |
| `POST` | `/api/v1/anomaly/{id}/fit` | ✅ | Train IsolationForest baseline |
| `GET` | `/api/v1/anomaly/{id}/log` | ✅ | Anomaly audit log |
| `POST` | `/api/v1/simulate/register` | ❌ | Create sensor suite |
| `POST` | `/api/v1/simulate/tick` | ❌ | One sensor tick |
| `POST` | `/api/v1/simulate/run` | ❌ | N simulation ticks |
| `POST` | `/api/v1/simulate/inject` | ❌ | Inject fault signal |
| `POST` | `/api/v1/predict/{id}/fit` | ✅ | Train SHI Random Forest |
| `GET` | `/api/v1/predict/{id}` | ✅ | T+7 SHI forecast |
| `GET` | `/api/v1/report/{id}` | ✅ | Download PDF health report |

---

## 🔐 Security

API key is sent as an HTTP header on every protected request:
```
X-NexusTwin-API-Key: nexus-dev-key-change-me
```

For production deployments, replace the shared key with per-client keys
or upgrade to JWT (FastAPI's `OAuth2PasswordBearer`).

---

## 🗺️ Roadmap

- [x] **Core SHI Engine** — strain, vibration, temperature, fatigue sub-scores
- [x] **Fatigue Engine** — Palmgren-Miner with 5 S-N material curves
- [x] **Two-Layer Anomaly Detection** — Z-score + IsolationForest
- [x] **Async SQLite Persistence** — element registry, SHI history, anomaly log
- [x] **ML SHI Forecasting** — Random Forest T+7d predictor with confidence band
- [x] **PDF Reports** — ReportLab + Matplotlib, streamed in-memory
- [x] **Lab Simulation Runner** — end-to-end demo with degradation injection
- [x] **Full Test Suite** — unit + integration tests (≥20 assertions)
- [ ] **IFC Connector** — parse real Revit models via `ifcopenshell`
- [ ] **WebSocket Live Feed** — real-time SHI push to dashboard
- [ ] **Prometheus Metrics** — `/metrics` endpoint for Grafana dashboards
- [ ] **PostgreSQL Migration** — asyncpg adapter for multi-project deployments
- [ ] **CI/CD Pipeline** — GitHub Actions: lint → test → Docker build on push
- [ ] **Docker Compose** — one-command `docker-compose up` for the full stack

---

## 📄 License

Developed for portfolio and research purposes.  
See internal documentation for specific licensing terms.

---

<div align="center">
  <b>Built with a focus on clean architecture, real structural engineering standards, and production-grade Python.</b>
  <br><br>
  <i>💡 Architecture & Engineering by <b>Maycon Alves</b></i>
  <br>
  <a href="https://github.com/MayconAlvesss" target="_blank">GitHub</a> | <a href="https://www.linkedin.com/in/maycon-alves-a5b9402bb/" target="_blank">LinkedIn</a>
</div>

