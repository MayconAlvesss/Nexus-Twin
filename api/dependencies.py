"""
NexusTwin — FastAPI Dependency Injectors
==========================================
Centralised Depends() factories.

Pattern:
  Every route that needs the database or auth injects these via:
    db:    TwinDBManager = Depends(get_db)
    _key:  str           = Depends(verified_api_key)

This keeps routes thin and makes the dependencies fully mock-able in tests
(just override the dependency in the test fixture).
"""

from database.twin_db import get_db_manager, TwinDBManager
from security.auth import verify_api_key


def get_db() -> TwinDBManager:
    """
    Returns the live TwinDBManager singleton.
    Import and use this instead of get_db_manager() in route files so
    FastAPI can properly inject it via Depends().
    """
    return get_db_manager()


# Re-export verify_api_key so routes only import from this module
verified_api_key = verify_api_key
