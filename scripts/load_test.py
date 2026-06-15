from __future__ import annotations

import argparse
import concurrent.futures
import json
import time
from pathlib import Path
from statistics import mean
from typing import Any

import httpx

from runtime_config import DEFAULT_BASE_URL, normalize_base_url

QUERIES = Path("data/sample_queries.jsonl")


def send_request(
    client: httpx.Client, base_url: str, payload: dict[str, Any]
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        endpoint = f"{base_url}/chat"
        response = client.post(endpoint, json=payload)
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        try:
            body = response.json()
        except ValueError:
            body = {}
        result = {
            "status_code": response.status_code,
            "correlation_id": (
                response.headers.get("x-request-id")
                or response.headers.get("x-correlation-id")
            ),
            "latency_ms": latency_ms,
            "feature": payload["feature"],
            "error": body.get("detail") if response.is_error else None,
            "url": endpoint,
        }
    except httpx.HTTPError as exc:
        result = {
            "status_code": 0,
            "correlation_id": None,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "feature": payload["feature"],
            "error": str(exc),
            "url": f"{base_url}/chat",
        }
    if result["status_code"] == 200:
        print(
            f"[200] {result['correlation_id']} | "
            f"{result['feature']} | {result['latency_ms']:.1f}ms"
        )
    else:
        print(
            f"[{result['status_code']}] {result['url']} | "
            f"{result['feature']} | {result['error'] or 'request failed'} | "
            f"{result['latency_ms']:.1f}ms"
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()
    args.base_url = normalize_base_url(args.base_url)
    print(f"Load test endpoint: {args.base_url}/chat")

    payloads = [
        json.loads(line)
        for line in QUERIES.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ] * max(1, args.repeat)

    with httpx.Client(timeout=45.0) as client:
        if args.concurrency > 1:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=args.concurrency
            ) as executor:
                futures = [
                    executor.submit(send_request, client, args.base_url, payload)
                    for payload in payloads
                ]
                results = [future.result() for future in futures]
        else:
            results = [
                send_request(client, args.base_url, payload) for payload in payloads
            ]

    successes = sum(result["status_code"] == 200 for result in results)
    latencies = [result["latency_ms"] for result in results]
    print("\n--- Load Test Summary ---")
    print(f"Requests: {len(results)}")
    print(f"Successes: {successes}")
    print(f"Errors: {len(results) - successes}")
    print(f"Average latency: {mean(latencies):.2f}ms")
    print(f"Unique correlation IDs: {len({r['correlation_id'] for r in results if r['correlation_id']})}")
    if successes != len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
