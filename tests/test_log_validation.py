from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import logging_config
from app.main import app
from scripts.validate_logs import validate_log_file

client = TestClient(app)


def test_log_validation_passes_for_generated_logs(
    tmp_path: Path, monkeypatch
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)
    for index in range(2):
        response = client.post(
            "/chat",
            headers={"X-Correlation-ID": f"validation-{index}"},
            json={
                "user_id": f"raw-user-{index}",
                "session_id": "validation",
                "feature": "qa",
                "message": "What is your refund policy? student@example.com",
            },
        )
        assert response.status_code == 200

    result = validate_log_file(log_path)
    assert result["passed"] is True
    assert result["score"] == 100
    assert result["pii_leaks"] == []
