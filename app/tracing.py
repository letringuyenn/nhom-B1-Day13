from __future__ import annotations

import os
from contextlib import contextmanager
from functools import lru_cache
from typing import Any, Callable, Iterator

import structlog

# Langfuse v4 prefers LANGFUSE_BASE_URL. Keep existing LANGFUSE_HOST setups working.
if os.getenv("LANGFUSE_HOST") and not os.getenv("LANGFUSE_BASE_URL"):
    os.environ["LANGFUSE_BASE_URL"] = os.environ["LANGFUSE_HOST"]
if os.getenv("APP_ENV") and not os.getenv("LANGFUSE_TRACING_ENVIRONMENT"):
    os.environ["LANGFUSE_TRACING_ENVIRONMENT"] = os.environ["APP_ENV"]

try:
    from langfuse import get_client, observe, propagate_attributes
except ImportError as exc:  # pragma: no cover - only without installed SDK
    get_client = None
    observe = None
    propagate_attributes = None
    LANGFUSE_IMPORT_ERROR: Exception | None = exc
else:
    LANGFUSE_IMPORT_ERROR = None

log = structlog.get_logger()


class SafeObservation:
    def __init__(self, observation: Any = None) -> None:
        self._observation = observation

    def update(self, **kwargs: Any) -> None:
        if self._observation is None:
            return
        try:
            self._observation.update(**kwargs)
        except Exception as exc:
            _log_failure("observation_update", exc)


def _log_failure(operation: str, exc: Exception) -> None:
    log.warning(
        "tracing_failed",
        service="tracing",
        operation=operation,
        error=type(exc).__name__,
    )


def tracing_enabled() -> bool:
    return bool(
        get_client
        and os.getenv("LANGFUSE_PUBLIC_KEY")
        and os.getenv("LANGFUSE_SECRET_KEY")
        and os.getenv("LANGFUSE_TRACING_ENABLED", "True").lower()
        not in {"false", "0", "no"}
    )


def tracing_status() -> dict[str, Any]:
    if LANGFUSE_IMPORT_ERROR:
        return {
            "enabled": False,
            "reason": "langfuse_import_failed",
            "error": type(LANGFUSE_IMPORT_ERROR).__name__,
        }
    if not tracing_enabled():
        return {"enabled": False, "reason": "missing_credentials"}
    return {"enabled": True, "reason": None}


@lru_cache(maxsize=1)
def _client() -> Any:
    if not tracing_enabled():
        return None
    try:
        return get_client()
    except Exception as exc:
        _log_failure("client_init", exc)
        return None


def traced(
    *,
    name: str,
    as_type: str = "span",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Create an observation without automatically capturing raw arguments."""
    if observe is None:
        return lambda function: function
    return observe(
        name=name,
        as_type=as_type,
        capture_input=False,
        capture_output=False,
    )


@contextmanager
def trace_attributes(
    *,
    trace_name: str,
    user_id: str,
    session_id: str,
    tags: list[str],
    metadata: dict[str, str],
) -> Iterator[None]:
    if _client() is None or propagate_attributes is None:
        yield
        return

    manager = propagate_attributes(
        trace_name=trace_name,
        user_id=user_id,
        session_id=session_id,
        tags=tags,
        metadata=metadata,
    )
    try:
        manager.__enter__()
    except Exception as exc:
        _log_failure("attribute_propagation.start", exc)
        yield
        return

    body_error: BaseException | None = None
    try:
        yield
    except BaseException as exc:
        body_error = exc
        raise
    finally:
        try:
            manager.__exit__(
                type(body_error) if body_error else None,
                body_error,
                body_error.__traceback__ if body_error else None,
            )
        except Exception as exc:
            _log_failure("attribute_propagation.finish", exc)


@contextmanager
def observation(
    name: str,
    *,
    as_type: str = "span",
    input: Any = None,
    metadata: dict[str, Any] | None = None,
    model: str | None = None,
) -> Iterator[SafeObservation]:
    client = _client()
    if client is None:
        yield SafeObservation()
        return

    try:
        manager = client.start_as_current_observation(
            name=name,
            as_type=as_type,
            input=input,
            metadata=metadata,
            model=model,
        )
        raw_observation = manager.__enter__()
    except Exception as exc:
        _log_failure(f"{name}.start", exc)
        yield SafeObservation()
        return

    safe_observation = SafeObservation(raw_observation)
    body_error: BaseException | None = None
    try:
        yield safe_observation
    except BaseException as exc:
        body_error = exc
        safe_observation.update(
            level="ERROR",
            status_message=f"{type(exc).__name__}: {exc}",
            metadata={"error": type(exc).__name__},
        )
        raise
    finally:
        try:
            manager.__exit__(
                type(body_error) if body_error else None,
                body_error,
                body_error.__traceback__ if body_error else None,
            )
        except Exception as exc:
            _log_failure(f"{name}.finish", exc)


def update_current_observation(**kwargs: Any) -> None:
    client = _client()
    if client is None:
        return
    try:
        client.update_current_span(**kwargs)
    except Exception as exc:
        _log_failure("current_observation_update", exc)


def current_trace_id() -> str | None:
    client = _client()
    if client is None:
        return None
    try:
        return client.get_current_trace_id()
    except Exception as exc:
        _log_failure("trace_id", exc)
        return None


def score_current_observation(
    *,
    name: str,
    value: float,
    comment: str,
) -> None:
    client = _client()
    if client is None:
        return
    try:
        client.score_current_span(
            name=name,
            value=value,
            data_type="NUMERIC",
            comment=comment,
        )
    except Exception as exc:
        _log_failure("score_current_observation", exc)


def flush_traces() -> None:
    client = _client()
    if client is None:
        return
    try:
        client.flush()
    except Exception as exc:
        _log_failure("flush", exc)
