from __future__ import annotations

import time
from dataclasses import dataclass

from .incidents import STATE


@dataclass
class FakeUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class FakeResponse:
    text: str
    usage: FakeUsage
    model: str


class FakeLLM:
    def __init__(self, model: str = "claude-sonnet-4-5") -> None:
        self.model = model

    def generate(
        self,
        prompt: str,
        *,
        documents: list[str] | None = None,
        question: str = "",
    ) -> FakeResponse:
        time.sleep(0.15)
        documents = documents or []
        context = " ".join(documents)
        if "Do not expose PII" in context:
            answer = (
                f"{context} PII and other sensitive data must be redacted before logging."
            )
        elif context and not context.startswith("No domain document"):
            answer = context
        else:
            answer = (
                "Use metrics to detect symptoms, traces to localize slow or failing spans, "
                "and structured logs with a correlation ID to explain the root cause."
            )

        input_tokens = max(20, len(prompt) // 4)
        output_tokens = max(20, len(answer) // 4)
        if STATE["cost_spike"]:
            output_tokens *= 4
        return FakeResponse(
            text=answer,
            usage=FakeUsage(input_tokens=input_tokens, output_tokens=output_tokens),
            model=self.model,
        )
