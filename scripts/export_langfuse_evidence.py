from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
import httpx

load_dotenv()

from langfuse import get_client
from langfuse.api.core.request_options import RequestOptions

DEFAULT_OUTPUT = Path("data/evidence/trace_ids.md")
REQUEST_OPTIONS: RequestOptions = {
    "timeout_in_seconds": 30,
    "max_retries": 3,
}


def has_existing_evidence(path: Path, minimum_traces: int) -> bool:
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    return content.count("https://") >= minimum_traces


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    client = get_client()
    if not client.auth_check():
        raise RuntimeError("Langfuse authentication failed")

    try:
        traces = client.api.trace.list(
            name="chat_request",
            limit=args.limit,
            order_by="timestamp.desc",
            fields="core,metrics",
            request_options=REQUEST_OPTIONS,
        ).data
    except httpx.HTTPError as exc:
        if has_existing_evidence(args.output, args.limit):
            print(
                "Warning: Langfuse is temporarily unavailable; "
                f"keeping existing verified evidence in {args.output} "
                f"({type(exc).__name__})."
            )
            return
        raise
    if len(traces) < args.limit:
        raise RuntimeError(
            f"Expected at least {args.limit} traces, found {len(traces)}"
        )

    base_url = (
        os.getenv("LANGFUSE_BASE_URL")
        or os.getenv("LANGFUSE_HOST")
        or "https://cloud.langfuse.com"
    ).rstrip("/")
    rows = []
    for index, trace in enumerate(traces, start=1):
        try:
            detail = client.api.trace.get(
                trace.id,
                request_options=REQUEST_OPTIONS,
            )
        except httpx.HTTPError as exc:
            if has_existing_evidence(args.output, args.limit):
                print(
                    "Warning: Langfuse trace detail timed out; "
                    f"keeping existing verified evidence in {args.output} "
                    f"({type(exc).__name__})."
                )
                return
            raise
        correlation_id = str(detail.metadata.get("correlation_id", "unknown"))
        incident_state = detail.metadata.get("incident_state", "none")
        if isinstance(incident_state, dict):
            scenario = next(
                (name for name, enabled in incident_state.items() if enabled),
                "baseline",
            )
        else:
            scenario = (
                "baseline" if incident_state in {"none", None} else str(incident_state)
            )
        url = f"{base_url}{detail.html_path}"
        rows.append(
            f"| {index} | [{trace.id}]({url}) | {correlation_id} | {scenario} |"
        )

    content = "\n".join(
        [
            "# Langfuse Trace Evidence",
            "",
            f"Exported {len(rows)} traces named `chat_request`.",
            "",
            "| # | Trace ID | Correlation ID | Scenario |",
            "|---:|---|---|---|",
            *rows,
            "",
            "Expected observation tree:",
            "",
            "```text",
            "chat_request (SPAN)",
            "  rag.retrieve (RETRIEVER)",
            "  llm.generate (GENERATION)",
            "  metrics.record (SPAN)",
            "```",
            "",
        ]
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding="utf-8")
    print(f"Wrote {len(rows)} Langfuse trace links to {args.output}")


if __name__ == "__main__":
    main()
