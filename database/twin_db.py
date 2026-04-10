"""
NexusTwin — Twin Database Manager
===================================
Async SQLite wrapper that persists:
  - BIM elements registered in the twin
  - SHI (Structural Health Index) snapshot history
  - Anomaly event log

Why aiosqlite?
  The FastAPI event loop must never be blocked. aiosqlite runs SQLite
  operations in a thread pool so the API stays responsive even during
  long table scans. For >10k elements/day consider migrating to PostgreSQL
  and using asyncpg instead — the interface here is designed to make that
  migration straightforward (all queries are in one place).

Patterns borrowed from EcoBIM's database.materials_db:
  - Single async factory function (get_db_manager) used as a FastAPI dependency
  - Context-manager style connections so cursors are always closed
  - Schema bootstrap runs at startup via _ensure_schema()
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import aiosqlite

from config.settings import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DDL — Table definitions
# ---------------------------------------------------------------------------

_DDL_ELEMENTS = """
CREATE TABLE IF NOT EXISTS elements (
    element_id      TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    element_type    TEXT NOT NULL,   -- COLUMN | BEAM | WALL | SLAB | etc.
    material_class  TEXT NOT NULL,   -- steel | concrete | timber | masonry
    age_years       REAL NOT NULL DEFAULT 0.0,
    floor_level     TEXT,            -- e.g. "L3", "B1" — optional metadata
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'utc')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now', 'utc'))
);
"""

_DDL_SHI_HISTORY = """
CREATE TABLE IF NOT EXISTS shi_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    element_id      TEXT NOT NULL REFERENCES elements(element_id),
    shi_score       REAL NOT NULL,
    strain_score    REAL NOT NULL,
    vibration_score REAL NOT NULL,
    temperature_score REAL NOT NULL,
    fatigue_score   REAL NOT NULL,
    status          TEXT NOT NULL,   -- HEALTHY | WARNING | CRITICAL
    reading_count   INTEGER NOT NULL,
    notes           TEXT,
    recorded_at     TEXT NOT NULL DEFAULT (datetime('now', 'utc'))
);
"""

_DDL_ANOMALY_LOG = """
CREATE TABLE IF NOT EXISTS anomaly_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    anomaly_id      TEXT NOT NULL,
    element_id      TEXT NOT NULL REFERENCES elements(element_id),
    sensor_type     TEXT NOT NULL,
    severity        TEXT NOT NULL,   -- LOW | MEDIUM | HIGH | CRITICAL
    value           REAL NOT NULL,
    z_score         REAL,            -- NULL when IsolationForest triggered
    description     TEXT NOT NULL,
    detected_at     TEXT NOT NULL DEFAULT (datetime('now', 'utc'))
);
"""

# Index for fast per-element history lookups
_DDL_INDICES = """
CREATE INDEX IF NOT EXISTS idx_shi_history_element ON shi_history(element_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_anomaly_element ON anomaly_log(element_id, detected_at DESC);
"""


# ---------------------------------------------------------------------------
# Manager class
# ---------------------------------------------------------------------------

class TwinDBManager:
    """
    Async database manager for NexusTwin.

    Usage (as a FastAPI dependency):
        db = TwinDBManager(db_path)
        await db.connect()
        ...in route handler...
        await db.upsert_element(...)
    """

    def __init__(self, db_path: str) -> None:
        self._path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    # -----------------------------------------------------------------------
    # Connection lifecycle
    # -----------------------------------------------------------------------

    async def connect(self) -> None:
        """Open the connection and ensure the schema is up to date."""
        self._conn = await aiosqlite.connect(self._path)
        # Return rows as sqlite3.Row objects so we can access columns by name
        self._conn.row_factory = aiosqlite.Row
        await self._ensure_schema()
        logger.info("NexusTwin DB connected: %s", self._path)

    async def disconnect(self) -> None:
        """Close the connection cleanly on app shutdown."""
        if self._conn:
            await self._conn.close()
            logger.info("NexusTwin DB disconnected.")

    async def _ensure_schema(self) -> None:
        """Create tables and indices if they don't exist yet (idempotent)."""
        if not self._conn:
            raise RuntimeError("DB not connected — call connect() first.")
        async with self._conn.executescript(
            _DDL_ELEMENTS + _DDL_SHI_HISTORY + _DDL_ANOMALY_LOG + _DDL_INDICES
        ):
            pass
        await self._conn.commit()

    # -----------------------------------------------------------------------
    # Element registry CRUD
    # -----------------------------------------------------------------------

    async def upsert_element(
        self,
        element_id: str,
        name: str,
        element_type: str,
        material_class: str,
        age_years: float = 0.0,
        floor_level: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> None:
        """
        Insert a new element or update it if it already exists.
        This is the main entry point when syncing BIM data to the twin.
        """
        now = datetime.now(timezone.utc).isoformat()
        await self._conn.execute(  # type: ignore[union-attr]
            """
            INSERT INTO elements
                (element_id, name, element_type, material_class, age_years,
                 floor_level, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(element_id) DO UPDATE SET
                name           = excluded.name,
                element_type   = excluded.element_type,
                material_class = excluded.material_class,
                age_years      = excluded.age_years,
                floor_level    = excluded.floor_level,
                notes          = excluded.notes,
                updated_at     = excluded.updated_at
            """,
            (element_id, name, element_type, material_class, age_years,
             floor_level, notes, now, now),
        )
        await self._conn.commit()  # type: ignore[union-attr]

    async def get_element(self, element_id: str) -> Optional[dict]:
        """Retrieve a single element record by its ID."""
        cursor = await self._conn.execute(  # type: ignore[union-attr]
            "SELECT * FROM elements WHERE element_id = ?", (element_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def list_elements(self) -> list[dict]:
        """Return all registered elements ordered by creation date."""
        cursor = await self._conn.execute(  # type: ignore[union-attr]
            "SELECT * FROM elements ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # -----------------------------------------------------------------------
    # SHI history
    # -----------------------------------------------------------------------

    async def record_shi(
        self,
        element_id: str,
        shi_score: float,
        strain_score: float,
        vibration_score: float,
        temperature_score: float,
        fatigue_score: float,
        status: str,
        reading_count: int,
        notes: Optional[str] = None,
    ) -> None:
        """Persist a SHI snapshot. Called by the API after every compute()."""
        now = datetime.now(timezone.utc).isoformat()
        await self._conn.execute(  # type: ignore[union-attr]
            """
            INSERT INTO shi_history
                (element_id, shi_score, strain_score, vibration_score,
                 temperature_score, fatigue_score, status, reading_count,
                 notes, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (element_id, shi_score, strain_score, vibration_score,
             temperature_score, fatigue_score, status, reading_count,
             notes, now),
        )
        await self._conn.commit()  # type: ignore[union-attr]

    async def get_shi_history(
        self, element_id: str, limit: int = 100
    ) -> list[dict]:
        """
        Fetch the N most recent SHI snapshots for an element.
        Used for trend charts on the dashboard.
        """
        cursor = await self._conn.execute(  # type: ignore[union-attr]
            """
            SELECT * FROM shi_history
            WHERE element_id = ?
            ORDER BY recorded_at DESC
            LIMIT ?
            """,
            (element_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_latest_shi(self, element_id: str) -> Optional[dict]:
        """Return only the most recent SHI snapshot for a quick status check."""
        cursor = await self._conn.execute(  # type: ignore[union-attr]
            """
            SELECT * FROM shi_history
            WHERE element_id = ?
            ORDER BY recorded_at DESC
            LIMIT 1
            """,
            (element_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    # -----------------------------------------------------------------------
    # Anomaly log
    # -----------------------------------------------------------------------

    async def log_anomaly(
        self,
        anomaly_id: str,
        element_id: str,
        sensor_type: str,
        severity: str,
        value: float,
        z_score: Optional[float],
        description: str,
    ) -> None:
        """Persist one anomaly event to the audit log."""
        now = datetime.now(timezone.utc).isoformat()
        await self._conn.execute(  # type: ignore[union-attr]
            """
            INSERT INTO anomaly_log
                (anomaly_id, element_id, sensor_type, severity, value,
                 z_score, description, detected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (anomaly_id, element_id, sensor_type, severity, value,
             z_score, description, now),
        )
        await self._conn.commit()  # type: ignore[union-attr]

    async def get_anomalies(
        self,
        element_id: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 200,
    ) -> list[dict]:
        """
        Retrieve anomaly records with optional filters.
        Useful for dashboard alert feeds and audit exports.
        """
        query = "SELECT * FROM anomaly_log WHERE 1=1"
        params: list[Any] = []
        if element_id:
            query += " AND element_id = ?"
            params.append(element_id)
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        query += " ORDER BY detected_at DESC LIMIT ?"
        params.append(limit)

        cursor = await self._conn.execute(query, params)  # type: ignore[union-attr]
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Singleton factory (used by FastAPI lifespan)
# ---------------------------------------------------------------------------

_db_instance: Optional[TwinDBManager] = None


def get_db_manager() -> TwinDBManager:
    """
    Return the application-wide TwinDBManager instance.
    Call this inside a FastAPI Depends() to inject the DB into routes.
    The instance is created at app startup via the lifespan context manager.
    """
    if _db_instance is None:
        raise RuntimeError(
            "Database not initialised. "
            "Ensure the FastAPI lifespan handler called db.connect()."
        )
    return _db_instance


async def initialise_db() -> TwinDBManager:
    """
    Create and connect the singleton DB manager.
    Called once during app startup (FastAPI lifespan).
    """
    global _db_instance
    db_path = get_settings().NEXUS_DB_PATH
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    _db_instance = TwinDBManager(db_path)
    await _db_instance.connect()
    return _db_instance


async def shutdown_db() -> None:
    """Gracefully close the DB connection on app shutdown."""
    global _db_instance
    if _db_instance:
        await _db_instance.disconnect()
        _db_instance = None
