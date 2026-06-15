from __future__ import annotations

import time
from dataclasses import dataclass

from . import metrics
from .incidents import status
from .logging_config import get_logger
from .mock_llm import FakeLLM
from .mock_rag import retrieve
from .pii import hash_user_id, summarize_text
from .tracing import (
    current_trace_id,
    observation,
    score_current_observation,
    trace_attributes,
    traced,
    update_current_observation,
)

log = get_logger()


@dataclass
class AgentResult:
    answer: str
    latency_ms: int
    rag_latency_ms: int
    llm_latency_ms: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    quality_score: float
    trace_id: str | None = None


class LabAgent:
    def __init__(self, model: str = "claude-sonnet-4-5") -> None:
        self.model = model
        self.llm = FakeLLM(model=model)

    @traced(name="chat_request", as_type="span")
    def run(
        self,
        *,
        user_id: str,
        feature: str,
        session_id: str,
        message: str,
        correlation_id: str,
    ) -> AgentResult:
        started = time.perf_counter()
        rag_latency_ms = 0
        incident_state = status()
        trace_metadata = {
            "correlation_id": correlation_id,
            "request_id": correlation_id,
            "incident_state": incident_state,
            "feature": feature,
        }

        with trace_attributes(
            trace_name="chat_request",
            user_id=hash_user_id(user_id),
            session_id=session_id,
            tags=["lab", feature, self.model],
            metadata={
                "correlation_id": correlation_id,
                "request_id": correlation_id,
                "feature": feature,
                "incident_state": ",".join(
                    name for name, enabled in incident_state.items() if enabled
                ) or "none",
            },
        ):
            update_current_observation(
                input={
                    "message_preview": summarize_text(message),
                    "feature": feature,
                },
                metadata=trace_metadata,
            )
            try:
                rag_started = time.perf_counter()
                with observation(
                    "rag.retrieve",
                    as_type="retriever",
                    input={"query_preview": summarize_text(message)},
                    metadata={"incident_state": incident_state},
                ) as rag_span:
                    try:
                        docs = retrieve(message)
                    finally:
                        rag_latency_ms = int(
                            (time.perf_counter() - rag_started) * 1000
                        )
                    rag_span.update(
                        output={
                            "document_count": len(docs),
                            "document_previews": [
                                summarize_text(document) for document in docs
                            ],
                        },
                        metadata={
                            "retrieved_document_count": len(docs),
                            "rag_latency_ms": rag_latency_ms,
                            "incident_state": incident_state,
                        },
                    )
                log.info(
                    "rag_completed",
                    service="agent",
                    rag_latency_ms=rag_latency_ms,
                    retrieved_document_count=len(docs),
                    incident_state=incident_state,
                )

                prompt = f"Feature={feature}\nDocs={docs}\nQuestion={message}"
                llm_started = time.perf_counter()
                with observation(
                    "llm.generate",
                    as_type="generation",
                    input={"prompt_preview": summarize_text(prompt)},
                    metadata={"incident_state": incident_state},
                    model=self.model,
                ) as generation:
                    response = self.llm.generate(
                        prompt,
                        documents=docs,
                        question=message,
                    )
                    llm_latency_ms = int(
                        (time.perf_counter() - llm_started) * 1000
                    )
                    cost_usd = self._estimate_cost(
                        response.usage.input_tokens,
                        response.usage.output_tokens,
                    )
                    generation.update(
                        output={"answer_preview": summarize_text(response.text)},
                        usage_details={
                            "input": response.usage.input_tokens,
                            "output": response.usage.output_tokens,
                        },
                        cost_details={"total": cost_usd},
                        metadata={
                            "llm_latency_ms": llm_latency_ms,
                            "incident_state": incident_state,
                        },
                    )
                log.info(
                    "llm_completed",
                    service="agent",
                    llm_latency_ms=llm_latency_ms,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    estimated_cost=cost_usd,
                    incident_state=incident_state,
                )

                quality_score = self._heuristic_quality(
                    message, response.text, docs
                )
                latency_ms = int((time.perf_counter() - started) * 1000)
                with observation(
                    "metrics.record",
                    as_type="span",
                    metadata={"incident_state": incident_state},
                ) as metrics_span:
                    metrics.record_success(
                        latency_ms=latency_ms,
                        rag_latency_ms=rag_latency_ms,
                        llm_latency_ms=llm_latency_ms,
                        estimated_cost=cost_usd,
                        input_tokens=response.usage.input_tokens,
                        output_tokens=response.usage.output_tokens,
                        quality_score=quality_score,
                        correlation_id=correlation_id,
                        incident_state=incident_state,
                    )
                    metrics_span.update(
                        output={
                            "total_latency_ms": latency_ms,
                            "quality_score": quality_score,
                        }
                    )
                score_current_observation(
                    name="quality_score",
                    value=quality_score,
                    comment="Deterministic heuristic quality score for the lab.",
                )

                trace_id = current_trace_id()
                update_current_observation(
                    output={"answer_preview": summarize_text(response.text)},
                    metadata={
                        **trace_metadata,
                        "retrieved_document_count": len(docs),
                        "rag_latency_ms": rag_latency_ms,
                        "llm_latency_ms": llm_latency_ms,
                        "total_latency_ms": latency_ms,
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                        "estimated_cost": cost_usd,
                        "quality_score": quality_score,
                    },
                )
                log.info(
                    "agent_completed",
                    service="agent",
                    latency_ms=latency_ms,
                    rag_latency_ms=rag_latency_ms,
                    llm_latency_ms=llm_latency_ms,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    estimated_cost=cost_usd,
                    quality_score=quality_score,
                    incident_state=incident_state,
                    trace_id=trace_id,
                )
                return AgentResult(
                    answer=response.text,
                    latency_ms=latency_ms,
                    rag_latency_ms=rag_latency_ms,
                    llm_latency_ms=llm_latency_ms,
                    tokens_in=response.usage.input_tokens,
                    tokens_out=response.usage.output_tokens,
                    cost_usd=cost_usd,
                    quality_score=quality_score,
                    trace_id=trace_id,
                )
            except Exception as exc:
                latency_ms = int((time.perf_counter() - started) * 1000)
                metrics.record_error(
                    type(exc).__name__,
                    latency_ms=latency_ms,
                    rag_latency_ms=rag_latency_ms,
                    correlation_id=correlation_id,
                    incident_state=incident_state,
                )
                update_current_observation(
                    level="ERROR",
                    status_message=f"{type(exc).__name__}: {exc}",
                    metadata={
                        **trace_metadata,
                        "total_latency_ms": latency_ms,
                        "rag_latency_ms": rag_latency_ms,
                        "error": type(exc).__name__,
                    },
                )
                log.exception(
                    "agent_failed",
                    service="agent",
                    latency_ms=latency_ms,
                    rag_latency_ms=rag_latency_ms,
                    incident_state=incident_state,
                    error=type(exc).__name__,
                )
                raise

    @staticmethod
    def _estimate_cost(tokens_in: int, tokens_out: int) -> float:
        input_cost = (tokens_in / 1_000_000) * 3
        output_cost = (tokens_out / 1_000_000) * 15
        return round(input_cost + output_cost, 6)

    @staticmethod
    def _heuristic_quality(question: str, answer: str, docs: list[str]) -> float:
        score = 0.4
        if docs and not docs[0].startswith("No domain document"):
            score += 0.3
        if len(answer) > 40:
            score += 0.1
        question_terms = set(question.lower().split())
        answer_terms = set(answer.lower().split())
        if question_terms & answer_terms:
            score += 0.2
        return round(max(0.0, min(1.0, score)), 2)
