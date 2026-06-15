from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import httpx

from runtime_config import DEFAULT_BASE_URL, normalize_base_url

EVIDENCE_DIR = Path("data/evidence")
SAMPLE_REQUEST = {
    "user_id": "evidence-user",
    "session_id": "evidence-session",
    "feature": "qa",
    "message": "Explain why metrics traces and logs work together",
}


def write_json(name: str, payload: dict[str, Any]) -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / name).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def set_incident(client: httpx.Client, base_url: str, name: str, enabled: bool) -> None:
    action = "enable" if enabled else "disable"
    response = client.post(f"{base_url}/incidents/{name}/{action}")
    response.raise_for_status()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()
    args.base_url = normalize_base_url(args.base_url)

    with httpx.Client(timeout=45.0) as client:
        for incident in ("rag_slow", "tool_fail", "cost_spike"):
            set_incident(client, args.base_url, incident, False)

        baseline = client.post(f"{args.base_url}/chat", json=SAMPLE_REQUEST)
        baseline.raise_for_status()
        write_json("baseline_metrics.json", client.get(f"{args.base_url}/metrics").json())

        set_incident(client, args.base_url, "rag_slow", True)
        slow = client.post(f"{args.base_url}/chat", json=SAMPLE_REQUEST)
        slow.raise_for_status()
        write_json("rag_slow_metrics.json", client.get(f"{args.base_url}/metrics").json())
        set_incident(client, args.base_url, "rag_slow", False)

        set_incident(client, args.base_url, "cost_spike", True)
        costly = client.post(f"{args.base_url}/chat", json=SAMPLE_REQUEST)
        costly.raise_for_status()
        write_json("cost_spike_metrics.json", client.get(f"{args.base_url}/metrics").json())
        set_incident(client, args.base_url, "cost_spike", False)

        set_incident(client, args.base_url, "tool_fail", True)
        failed = client.post(f"{args.base_url}/chat", json=SAMPLE_REQUEST)
        if failed.status_code != 500:
            raise RuntimeError(f"Expected tool_fail to return 500, got {failed.status_code}")
        write_json("tool_fail_metrics.json", client.get(f"{args.base_url}/metrics").json())
        set_incident(client, args.base_url, "tool_fail", False)

    print(f"Evidence written to {EVIDENCE_DIR}")


if __name__ == "__main__":
    main()
