from __future__ import annotations

import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars

from .incidents import status


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        clear_contextvars()

        incoming = request.headers.get("x-request-id") or request.headers.get(
            "x-correlation-id"
        )
        correlation_id = incoming.strip() if incoming and incoming.strip() else str(uuid.uuid4())
        bind_contextvars(
            correlation_id=correlation_id,
            route=request.url.path,
            method=request.method,
        )
        request.state.correlation_id = correlation_id

        log = structlog.get_logger()
        start = time.perf_counter()
        log.info("request_started", service="api", incident_state=status())
        try:
            response = await call_next(request)
        except Exception as exc:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            log.exception(
                "request_unhandled_error",
                service="api",
                status_code=500,
                latency_ms=latency_ms,
                error=type(exc).__name__,
            )
            raise

        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["x-request-id"] = correlation_id
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Response-Time-Ms"] = str(latency_ms)
        log.info(
            "request_completed",
            service="api",
            status_code=response.status_code,
            latency_ms=latency_ms,
            incident_state=status(),
        )
        return response
