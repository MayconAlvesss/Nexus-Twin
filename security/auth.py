"""
NexusTwin — API Key Authentication
====================================
Simple but production-ready API key guard.
Every protected endpoint calls verify_api_key() via FastAPI's Depends().

The key is expected in the HTTP header:  X-NexusTwin-API-Key: <your-key>

Why not OAuth2 / JWT here?
  For a BIM plugin talking to a local or private API, a shared API key
  is simple to deploy and secure enough. For multi-tenant SaaS, swap this
  out for a proper JWT layer (FastAPI's OAuth2PasswordBearer, etc.).
"""

import logging
from fastapi import Header, HTTPException, status
from config.settings import get_settings

logger = logging.getLogger(__name__)


async def verify_api_key(
    x_nexustwin_api_key: str = Header(
        ...,
        alias="X-NexusTwin-API-Key",
        description="Shared API key issued to each authorised client.",
    )
) -> str:
    """
    FastAPI dependency — injected into any route that requires authentication.

    Returns the key string on success so routes can log which client called them
    (useful when you have per-client keys in a real deployment).

    Raises 401 if the key is missing or wrong.
    """
    expected = get_settings().NEXUS_API_KEY

    if x_nexustwin_api_key != expected:
        # Log the attempt but don't reveal the expected key in the error body.
        logger.warning(
            "Rejected request with invalid API key: %s***",
            x_nexustwin_api_key[:6] if len(x_nexustwin_api_key) >= 6 else "???",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return x_nexustwin_api_key
