from __future__ import annotations

import argparse

import httpx

from runtime_config import DEFAULT_BASE_URL, normalize_base_url


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario",
        required=True,
        choices=["rag_slow", "tool_fail", "cost_spike"],
    )
    parser.add_argument("--disable", action="store_true")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()
    args.base_url = normalize_base_url(args.base_url)

    action = "disable" if args.disable else "enable"
    path = f"/incidents/{args.scenario}/{action}"
    response = httpx.post(f"{args.base_url}{path}", timeout=10.0)
    response.raise_for_status()
    print(
        f"Incident '{args.scenario}' {action}d successfully: "
        f"{response.json()['incidents']}"
    )


if __name__ == "__main__":
    main()
