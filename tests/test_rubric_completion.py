from __future__ import annotations

from pathlib import Path

from scripts.check_alerts import run_validation

ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_exists_with_six_panels() -> None:
    dashboard = ROOT / "docs" / "dashboard.html"
    assert dashboard.exists()
    content = dashboard.read_text(encoding="utf-8")
    assert content.count('data-panel="') == 6
    for panel in (
        "request-latency",
        "error-rate",
        "rag-latency",
        "llm-token-usage",
        "estimated-cost",
        "quality-score",
    ):
        assert f'data-panel="{panel}"' in content


def test_alert_validation_fires_for_all_incidents() -> None:
    payload = run_validation()
    assert payload["passed"] is True
    assert payload["firing_count"] == 3
    assert {
        alert["scenario"]
        for alert in payload["alerts"]
        if alert["firing"]
    } == {"rag_slow", "tool_fail", "cost_spike"}
    assert (ROOT / "data" / "evidence" / "alert_validation.json").exists()
