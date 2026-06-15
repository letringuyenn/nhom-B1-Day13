from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import httpx

from runtime_config import DEFAULT_BASE_URL, normalize_base_url

EXPECTED_PATH = Path("data/expected_answers.jsonl")
EVIDENCE_PATH = Path("data/evidence/quality_eval.json")


def evaluate(base_url: str) -> dict[str, Any]:
    cases = [
        json.loads(line)
        for line in EXPECTED_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    results = []
    with httpx.Client(timeout=30.0) as client:
        for index, case in enumerate(cases, start=1):
            endpoint = f"{base_url}/chat"
            try:
                response = client.post(
                    endpoint,
                    json={
                        "user_id": f"eval-user-{index}",
                        "session_id": "quality-eval",
                        "feature": "qa",
                        "message": case["question"],
                    },
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    raise RuntimeError(
                        f"Endpoint not found: {endpoint}\n"
                        "Ban co dang chay app o port 8013 khong?\n"
                        "Hay chay: uvicorn app.main:app --reload "
                        "--env-file .env --port 8013"
                    ) from exc
                raise
            answer = response.json()["answer"]
            keyword_matches = {
                keyword: keyword.lower() in answer.lower()
                for keyword in case["must_include"]
            }
            score = sum(keyword_matches.values()) / len(keyword_matches)
            results.append(
                {
                    "question": case["question"],
                    "answer": answer,
                    "required_keywords": case["must_include"],
                    "keyword_matches": keyword_matches,
                    "score": round(score, 4),
                    "correlation_id": (
                        response.headers.get("x-request-id")
                        or response.headers.get("x-correlation-id")
                    ),
                }
            )
    average = sum(result["score"] for result in results) / len(results)
    return {
        "cases": len(results),
        "average_quality_score": round(average, 4),
        "passed": average >= 0.75,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--evidence-path", type=Path, default=EVIDENCE_PATH)
    args = parser.parse_args()

    args.base_url = normalize_base_url(args.base_url)
    print(f"Quality evaluation endpoint: {args.base_url}/chat")
    try:
        result = evaluate(args.base_url)
    except (httpx.HTTPError, RuntimeError) as exc:
        print(f"Quality evaluation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    args.evidence_path.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"Average score: {result['average_quality_score']}")
    print("Passed" if result["passed"] else "Failed")
    print(f"Evidence written to {args.evidence_path}")
    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
