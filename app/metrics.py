from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from statistics import mean
from threading import RLock
from typing import Any

REQUEST_LATENCIES: list[float] = []
RAG_LATENCIES: list[float] = []
LLM_LATENCIES: list[float] = []
REQUEST_COSTS: list[float] = []
REQUEST_TOKENS_IN: list[int] = []
REQUEST_TOKENS_OUT: list[int] = []
ERRORS: Counter[str] = Counter()
QUALITY_SCORES: list[float] = []
RECENT_REQUESTS: list[dict[str, Any]] = []
TOTAL_REQUESTS = 0
TOTAL_SUCCESS = 0
TOTAL_ERRORS = 0
LOCK = RLock()
RECENT_LIMIT = 100


def _append_recent(record: dict[str, Any]) -> None:
    RECENT_REQUESTS.append(
        {"timestamp": datetime.now(timezone.utc).isoformat(), **record}
    )
    del RECENT_REQUESTS[:-RECENT_LIMIT]


def record_success(
    *,
    latency_ms: float,
    rag_latency_ms: float,
    llm_latency_ms: float,
    estimated_cost: float,
    input_tokens: int,
    output_tokens: int,
    quality_score: float,
    correlation_id: str,
    incident_state: dict[str, bool],
) -> None:
    global TOTAL_REQUESTS, TOTAL_SUCCESS
    with LOCK:
        TOTAL_REQUESTS += 1
        TOTAL_SUCCESS += 1
        REQUEST_LATENCIES.append(latency_ms)
        RAG_LATENCIES.append(rag_latency_ms)
        LLM_LATENCIES.append(llm_latency_ms)
        REQUEST_COSTS.append(estimated_cost)
        REQUEST_TOKENS_IN.append(input_tokens)
        REQUEST_TOKENS_OUT.append(output_tokens)
        QUALITY_SCORES.append(quality_score)
        _append_recent(
            {
                "success": True,
                "correlation_id": correlation_id,
                "latency_ms": latency_ms,
                "rag_latency_ms": rag_latency_ms,
                "llm_latency_ms": llm_latency_ms,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "estimated_cost": estimated_cost,
                "quality_score": quality_score,
                "incident_state": incident_state,
            }
        )


def record_error(
    error_type: str,
    *,
    latency_ms: float = 0.0,
    rag_latency_ms: float = 0.0,
    correlation_id: str = "",
    incident_state: dict[str, bool] | None = None,
) -> None:
    global TOTAL_REQUESTS, TOTAL_ERRORS
    with LOCK:
        TOTAL_REQUESTS += 1
        TOTAL_ERRORS += 1
        ERRORS[error_type] += 1
        REQUEST_LATENCIES.append(latency_ms)
        if rag_latency_ms:
            RAG_LATENCIES.append(rag_latency_ms)
        _append_recent(
            {
                "success": False,
                "correlation_id": correlation_id,
                "latency_ms": latency_ms,
                "rag_latency_ms": rag_latency_ms,
                "error": error_type,
                "incident_state": incident_state or {},
            }
        )


def percentile(values: list[float] | list[int], p: int) -> float:
    if not values:
        return 0.0
    items = sorted(values)
    rank = (len(items) - 1) * (p / 100)
    lower = int(rank)
    upper = min(lower + 1, len(items) - 1)
    weight = rank - lower
    return round(float(items[lower] * (1 - weight) + items[upper] * weight), 2)


def _average(values: list[float] | list[int]) -> float:
    return round(float(mean(values)), 4) if values else 0.0


def snapshot(incident_state: dict[str, bool] | None = None) -> dict[str, Any]:
    with LOCK:
        error_rate = (TOTAL_ERRORS / TOTAL_REQUESTS) if TOTAL_REQUESTS else 0.0
        quality_passes = sum(score >= 0.75 for score in QUALITY_SCORES)
        return {
            "total_requests": TOTAL_REQUESTS,
            "total_success": TOTAL_SUCCESS,
            "total_errors": TOTAL_ERRORS,
            "error_rate": round(error_rate, 4),
            "error_rate_pct": round(error_rate * 100, 2),
            "error_breakdown": dict(ERRORS),
            "p50_latency_ms": percentile(REQUEST_LATENCIES, 50),
            "p95_latency_ms": percentile(REQUEST_LATENCIES, 95),
            "p99_latency_ms": percentile(REQUEST_LATENCIES, 99),
            "average_latency_ms": _average(REQUEST_LATENCIES),
            "rag_p50_latency_ms": percentile(RAG_LATENCIES, 50),
            "rag_p95_latency_ms": percentile(RAG_LATENCIES, 95),
            "llm_p50_latency_ms": percentile(LLM_LATENCIES, 50),
            "llm_p95_latency_ms": percentile(LLM_LATENCIES, 95),
            "total_input_tokens": sum(REQUEST_TOKENS_IN),
            "total_output_tokens": sum(REQUEST_TOKENS_OUT),
            "average_input_tokens": _average(REQUEST_TOKENS_IN),
            "average_output_tokens": _average(REQUEST_TOKENS_OUT),
            "total_cost": round(sum(REQUEST_COSTS), 6),
            "average_cost": round(_average(REQUEST_COSTS), 6),
            "average_quality_score": _average(QUALITY_SCORES),
            "quality_pass_rate": (
                round(quality_passes / len(QUALITY_SCORES), 4)
                if QUALITY_SCORES
                else 0.0
            ),
            "incident_state": incident_state or {},
            "recent_requests": list(RECENT_REQUESTS),
        }


def reset() -> None:
    global TOTAL_REQUESTS, TOTAL_SUCCESS, TOTAL_ERRORS
    with LOCK:
        REQUEST_LATENCIES.clear()
        RAG_LATENCIES.clear()
        LLM_LATENCIES.clear()
        REQUEST_COSTS.clear()
        REQUEST_TOKENS_IN.clear()
        REQUEST_TOKENS_OUT.clear()
        ERRORS.clear()
        QUALITY_SCORES.clear()
        RECENT_REQUESTS.clear()
        TOTAL_REQUESTS = 0
        TOTAL_SUCCESS = 0
        TOTAL_ERRORS = 0
