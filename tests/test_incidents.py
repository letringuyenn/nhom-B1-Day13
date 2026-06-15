from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

PAYLOAD = {
    "user_id": "incident-user",
    "session_id": "incident-session",
    "feature": "qa",
    "message": "Explain why metrics traces and logs work together",
}


def test_rag_slow_increases_rag_latency() -> None:
    assert client.post("/incidents/rag_slow/enable").status_code == 200
    response = client.post("/chat", json=PAYLOAD)
    metrics = client.get("/metrics").json()
    assert response.status_code == 200
    assert metrics["rag_p95_latency_ms"] >= 2400
    assert metrics["incident_state"]["rag_slow"] is True


def test_tool_fail_increases_error_rate_without_crashing_server() -> None:
    assert client.post("/incidents/tool_fail/enable").status_code == 200
    response = client.post("/chat", json=PAYLOAD)
    metrics = client.get("/metrics").json()
    assert response.status_code == 500
    assert response.headers["x-correlation-id"]
    assert metrics["total_errors"] == 1
    assert metrics["error_rate"] == 1.0
    assert metrics["error_breakdown"]["RuntimeError"] == 1
    assert client.get("/health").status_code == 200


def test_cost_spike_increases_tokens_and_cost() -> None:
    baseline = client.post("/chat", json=PAYLOAD).json()
    assert client.post("/incidents/cost_spike/enable").status_code == 200
    spike = client.post("/chat", json=PAYLOAD).json()
    metrics = client.get("/metrics").json()
    assert spike["tokens_out"] == baseline["tokens_out"] * 4
    assert spike["cost_usd"] > baseline["cost_usd"]
    assert metrics["total_output_tokens"] == baseline["tokens_out"] + spike["tokens_out"]
