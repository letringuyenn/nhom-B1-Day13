from app import metrics


def test_percentile_interpolates_values() -> None:
    assert metrics.percentile([100, 200, 300, 400], 50) == 250.0
    assert metrics.percentile([100, 200, 300, 400], 95) == 385.0
    assert metrics.percentile([], 95) == 0.0


def test_snapshot_contains_dashboard_metrics() -> None:
    metrics.record_success(
        latency_ms=200,
        rag_latency_ms=25,
        llm_latency_ms=150,
        estimated_cost=0.01,
        input_tokens=100,
        output_tokens=50,
        quality_score=0.8,
        correlation_id="cid-1",
        incident_state={},
    )
    snapshot = metrics.snapshot({"rag_slow": False})
    assert snapshot["total_requests"] == 1
    assert snapshot["total_success"] == 1
    assert snapshot["p95_latency_ms"] == 200
    assert snapshot["rag_p95_latency_ms"] == 25
    assert snapshot["total_input_tokens"] == 100
    assert snapshot["total_cost"] == 0.01
    assert snapshot["quality_pass_rate"] == 1.0
