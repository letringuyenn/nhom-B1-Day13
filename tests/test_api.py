from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import logging_config
from app.main import app

client = TestClient(app)

PAYLOAD = {
    "user_id": "student-raw-id",
    "session_id": "session-1",
    "feature": "qa",
    "message": "What is your refund policy?",
}


def test_generated_correlation_id_is_returned() -> None:
    response = client.post("/chat", json=PAYLOAD)
    assert response.status_code == 200
    correlation_id = response.headers["x-request-id"]
    assert correlation_id
    assert response.headers["x-correlation-id"] == correlation_id
    assert response.json()["correlation_id"] == correlation_id


def test_supplied_correlation_id_is_preserved() -> None:
    response = client.post(
        "/chat",
        json=PAYLOAD,
        headers={"X-Correlation-ID": "mentor-demo-123"},
    )
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "mentor-demo-123"
    assert response.headers["x-correlation-id"] == "mentor-demo-123"
    assert response.json()["correlation_id"] == "mentor-demo-123"


def test_x_request_id_takes_precedence_and_is_propagated() -> None:
    response = client.post(
        "/chat",
        json=PAYLOAD,
        headers={
            "x-request-id": "original-request-456",
            "X-Correlation-ID": "fallback-correlation-789",
        },
    )
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "original-request-456"
    assert response.headers["x-correlation-id"] == "original-request-456"
    assert response.json()["correlation_id"] == "original-request-456"


def test_metrics_increase_after_chat() -> None:
    before = client.get("/metrics").json()
    response = client.post("/chat", json=PAYLOAD)
    after = client.get("/metrics").json()
    assert response.status_code == 200
    assert after["total_requests"] == before["total_requests"] + 1
    assert after["total_success"] == 1
    assert after["total_input_tokens"] > 0
    assert after["average_quality_score"] >= 0.75


def test_log_file_contains_correlation_id_and_no_raw_pii(
    tmp_path: Path, monkeypatch
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)
    payload = {
        **PAYLOAD,
        "message": (
            "Email student@example.com, card 4111111111111111, "
            "phone 0987654321"
        ),
    }
    response = client.post(
        "/chat",
        json=payload,
        headers={"X-Correlation-ID": "pii-test-correlation"},
    )
    assert response.status_code == 200
    raw = log_path.read_text(encoding="utf-8")
    assert "pii-test-correlation" in raw
    assert "student@example.com" not in raw
    assert "4111111111111111" not in raw
    assert "0987654321" not in raw
    for line in raw.splitlines():
        json.loads(line)
