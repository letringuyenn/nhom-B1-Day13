from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

LOG_PATH = Path("data/logs.jsonl")
EVIDENCE_PATH = Path("data/evidence/log_validation.json")
REQUIRED_FIELDS = {"ts", "timestamp", "level", "service", "event", "correlation_id"}
REQUIRED_EVENTS = {
    "request_started",
    "request_completed",
    "chat_started",
    "agent_completed",
    "rag_completed",
    "llm_completed",
}
PII_PATTERNS = {
    "email": re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]?){15,16}\b"),
    "phone": re.compile(r"(?<!\d)(?:\+84|0)[ .-]?\d{3}[ .-]?\d{3}[ .-]?\d{3,4}(?!\d)"),
}


def validate_log_file(path: Path = LOG_PATH) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path),
        "valid_json_lines": 0,
        "invalid_json_lines": [],
        "missing_required_fields": [],
        "missing_correlation_ids": [],
        "pii_leaks": [],
        "events_found": [],
        "missing_events": [],
        "passed": False,
        "score": 0,
    }
    if not path.exists():
        result["error"] = "log_file_not_found"
        return result

    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            result["invalid_json_lines"].append(line_number)
            continue
        records.append(record)
        result["valid_json_lines"] += 1
        missing = sorted(REQUIRED_FIELDS - record.keys())
        if missing:
            result["missing_required_fields"].append(
                {"line": line_number, "fields": missing}
            )
        if not record.get("correlation_id"):
            result["missing_correlation_ids"].append(line_number)
        raw = json.dumps(record, ensure_ascii=False)
        for pii_type, pattern in PII_PATTERNS.items():
            if pattern.search(raw):
                result["pii_leaks"].append(
                    {"line": line_number, "type": pii_type}
                )

    events = {record.get("event") for record in records}
    result["events_found"] = sorted(event for event in events if event)
    result["missing_events"] = sorted(REQUIRED_EVENTS - events)
    checks = [
        not result["invalid_json_lines"],
        not result["missing_required_fields"],
        not result["missing_correlation_ids"],
        not result["pii_leaks"],
        not result["missing_events"],
        len({record.get("correlation_id") for record in records}) >= 2,
    ]
    result["score"] = round(sum(checks) / len(checks) * 100)
    result["passed"] = all(checks)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-path", type=Path, default=LOG_PATH)
    parser.add_argument("--evidence-path", type=Path, default=EVIDENCE_PATH)
    args = parser.parse_args()

    result = validate_log_file(args.log_path)
    args.evidence_path.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
