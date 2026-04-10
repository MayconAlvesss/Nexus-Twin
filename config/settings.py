"""
NexusTwin — Application Settings
=================================
All runtime configuration lives here, loaded from the .env file via
Pydantic Settings so we get type validation for free.

Pattern:  read-once at startup, inject via FastAPI Depends() everywhere else.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Security ---
    NEXUS_API_KEY: str = "nexus-dev-key-change-me"

    # --- Health thresholds ---
    # Elements below WARNING threshold are flagged, below CRITICAL they're urgent.
    NEXUS_HEALTH_WARNING_THRESHOLD: float = 65.0
    NEXUS_HEALTH_CRITICAL_THRESHOLD: float = 40.0

    # --- CORS ---
    NEXUS_ALLOWED_ORIGINS: str = "http://localhost:5500,http://localhost:3000"

    # --- Database ---
    NEXUS_DB_PATH: str = "nexustwin.db"

    # --- Logging ---
    NEXUS_LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",   # don't crash if .env has unknown vars
    )

    @property
    def allowed_origins_list(self) -> list[str]:
        """Split the comma-separated CORS string into a Python list."""
        return [o.strip() for o in self.NEXUS_ALLOWED_ORIGINS.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the singleton Settings instance.
    Cached so we only read/parse the .env file once per process.
    """
    return Settings()


# Module-level shortcut used by non-DI code paths (CLI scripts, tests, etc.)
settings = get_settings()
