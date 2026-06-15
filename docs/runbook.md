# Incident Runbook

Investigation order for every incident:

```text
Metrics -> Traces -> Logs
```

Local evidence helpers:

```powershell
python scripts\build_dashboard.py
python scripts\check_alerts.py
```

The first refreshes `docs/dashboard.html`. The second evaluates
`config/alert_rules.yaml` against incident snapshots and writes
`data/evidence/alert_validation.json`.

## rag_slow

### Detection

`p95_latency_ms` or `rag_p95_latency_ms` rises above its normal range.
The local alert engine fires `rag_latency_spike` when the maximum recent RAG
latency exceeds 2000 ms.

### Metrics to check

- `p50_latency_ms`, `p95_latency_ms`, `p99_latency_ms`
- `rag_p50_latency_ms`, `rag_p95_latency_ms`
- `llm_p95_latency_ms`
- `incident_state.rag_slow`

### Traces to inspect

Open the slowest `chat_request` trace. Compare `rag.retrieve` with
`llm.generate`. The RAG span should account for approximately 2500 ms while
the LLM span remains near 150 ms.

### Logs to grep

```powershell
Select-String data\logs.jsonl -Pattern '"event": "rag_completed"'
Select-String data\logs.jsonl -Pattern '"rag_slow": true'
```

### Root cause

The `rag_slow` incident calls `time.sleep(2.5)` in the mock retrieval layer.

### Mitigation

Disable the incident, apply a retrieval timeout, use a fallback source, or
return cached documents.

### Prevention

Alert on RAG P95 independently, enforce timeout budgets, and load-test the
retrieval dependency.

## tool_fail

### Detection

`error_rate_pct` and `total_errors` increase; `error_breakdown.RuntimeError`
appears.
The local alert engine fires `high_error_rate` above 5%.

### Metrics to check

- `total_errors`
- `error_rate_pct`
- `error_breakdown`
- `incident_state.tool_fail`

### Traces to inspect

Open an errored `chat_request`; `rag.retrieve` is marked ERROR and later spans
are absent because retrieval failed before LLM generation.

### Logs to grep

```powershell
Select-String data\logs.jsonl -Pattern '"event": "agent_failed"'
Select-String data\logs.jsonl -Pattern '"event": "chat_failed"'
```

Use the shared `correlation_id` to join request, trace, and error records.

### Root cause

The mock vector store raises `RuntimeError("Vector store timeout")`.

### Mitigation

Disable the incident, retry only transient failures, or return a controlled
fallback answer. The current API returns a structured HTTP 500 and remains up.

### Prevention

Add dependency health checks, bounded retries, circuit breaking, and a tested
fallback response policy.

## cost_spike

### Detection

`average_output_tokens`, `total_output_tokens`, and `average_cost` rise without
a comparable traffic increase.
The local alert engine fires `cost_budget_spike` when a recent output token
count exceeds twice the baseline average.

### Metrics to check

- `average_output_tokens`
- `total_output_tokens`
- `average_cost`
- `total_cost`
- `incident_state.cost_spike`

### Traces to inspect

Open `llm.generate` and inspect `usage_details` and `cost_details`. RAG latency
should remain normal while output usage is approximately four times baseline.

### Logs to grep

```powershell
Select-String data\logs.jsonl -Pattern '"event": "llm_completed"'
Select-String data\logs.jsonl -Pattern '"cost_spike": true'
```

### Root cause

The cost incident multiplies reported output token usage by four.

### Mitigation

Disable the incident, cap output length, shorten prompts, route simple work to
a cheaper model, or use prompt caching.

### Prevention

Alert on token and cost baselines, enforce per-request output limits, and
review token usage by feature and model.
