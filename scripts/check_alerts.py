from __future__ import annotations

import json
import operator
from pathlib import Path
from typing import Any, Callable

import yaml

ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT / "config" / "alert_rules.yaml"
EVIDENCE_DIR = ROOT / "data" / "evidence"
OUTPUT_PATH = EVIDENCE_DIR / "alert_validation.json"

OPERATORS: dict[str, Callable[[float, float], bool]] = {
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def derived_metrics(snapshot: dict[str, Any]) -> dict[str, float]:
    recent = snapshot.get("recent_requests", [])
    return {
        "max_recent_rag_latency_ms": max(
            (float(item.get("rag_latency_ms", 0)) for item in recent),
            default=0.0,
        ),
        "max_recent_output_tokens": max(
            (float(item.get("output_tokens", 0)) for item in recent),
            default=0.0,
        ),
    }


def metric_value(snapshot: dict[str, Any], metric: str) -> float:
    if metric in snapshot:
        return float(snapshot[metric])
    derived = derived_metrics(snapshot)
    if metric in derived:
        return derived[metric]
    raise KeyError(f"Metric not found: {metric}")


def evaluate_rule(
    rule: dict[str, Any],
    snapshot: dict[str, Any],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    value = metric_value(snapshot, rule["metric"])
    if "baseline_metric" in rule:
        baseline_value = metric_value(baseline, rule["baseline_metric"])
        threshold = baseline_value * float(rule.get("baseline_multiplier", 1))
    else:
        baseline_value = None
        threshold = float(rule["threshold"])

    comparison = OPERATORS[rule["operator"]]
    firing = comparison(value, threshold)
    return {
        "name": rule["name"],
        "scenario": rule["scenario"],
        "severity": rule["severity"],
        "firing": firing,
        "metric": rule["metric"],
        "value": round(value, 6),
        "operator": rule["operator"],
        "threshold": round(threshold, 6),
        "baseline_value": (
            round(baseline_value, 6) if baseline_value is not None else None
        ),
        "condition": rule["condition"],
        "runbook": rule["runbook"],
    }


def run_validation() -> dict[str, Any]:
    rules = yaml.safe_load(RULES_PATH.read_text(encoding="utf-8"))["alerts"]
    baseline = load_json(EVIDENCE_DIR / "baseline_metrics.json")
    results = []
    for rule in rules:
        snapshot = load_json(EVIDENCE_DIR / f"{rule['scenario']}_metrics.json")
        results.append(evaluate_rule(rule, snapshot, baseline))

    expected = {"rag_slow", "tool_fail", "cost_spike"}
    firing_scenarios = {
        result["scenario"] for result in results if result["firing"]
    }
    payload = {
        "rules_path": str(RULES_PATH.relative_to(ROOT)),
        "evidence_directory": str(EVIDENCE_DIR.relative_to(ROOT)),
        "alerts": results,
        "firing_count": sum(result["firing"] for result in results),
        "passed": expected.issubset(firing_scenarios),
    }
    OUTPUT_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return payload


def main() -> None:
    payload = run_validation()
    for alert in payload["alerts"]:
        state = "FIRING" if alert["firing"] else "OK"
        print(
            f"[{state}] {alert['name']} ({alert['scenario']}): "
            f"{alert['metric']}={alert['value']} "
            f"{alert['operator']} {alert['threshold']}"
        )
    print(f"Evidence written to {OUTPUT_PATH.relative_to(ROOT)}")
    if not payload["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
