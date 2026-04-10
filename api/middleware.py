"""
NexusTwin — Performance Tracking Middleware
============================================
Logs the HTTP method, path, status code, and response time (ms) for every
request. Modelled after EcoBIM's api/middleware.py.

Why middleware instead of a logging decorator on each route?
  - Zero boilerplate on individual routes
  - Catches errors that propagate past route handlers
  - Gives you a single place to add future cross-cutting concerns
    (request IDs, rate-limiting counters, distributed tracing headers)
"""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("nexustwin.perf")


class PerformanceTrackingMiddleware(BaseHTTPMiddleware):
    """
    Adds an X-Process-Time header to every response and writes a
    structured log line so you can grep for slow endpoints.
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        start = time.perf_counter()
        response: Response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Attach the latency to the response so clients can read it
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.1f}"

        logger.info(
            "%s %s → %d | %.1f ms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )

        return response
