# Day 13 Observability Lab

FastAPI AI Agent lab for practicing structured logging, correlation IDs, PII
redaction, Langfuse tracing, dashboard-ready metrics, SLOs, alerts, incident
debugging, and evidence collection.

## Architecture

```text
Client -> POST /chat -> CorrelationIdMiddleware -> LabAgent
       -> rag.retrieve -> llm.generate -> metrics.record
       -> JSONL logs + Langfuse trace -> response
```

The RAG corpus and LLM are deterministic local fakes, so the lab runs without
external model credentials. Langfuse is optional at runtime but required for
the trace evidence portion of grading.

## Windows PowerShell Setup

Run commands from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Add Langfuse credentials to `.env` to export traces. Never commit `.env`.

```text
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_TRACING_ENABLED=True
LANGFUSE_TRACING_ENVIRONMENT=dev
LANGFUSE_RELEASE=day13-observability-lab
```

## Run the API

```powershell
uvicorn app.main:app --reload --env-file .env --port 8013
```

Default URLs:

- Swagger: `http://127.0.0.1:8013/docs`
- Health: `http://127.0.0.1:8013/health`
- Metrics: `http://127.0.0.1:8013/metrics`

All API scripts default to port 8013. Resolution order is explicit
`--base-url`, then `LAB_BASE_URL`, then `BASE_URL`, then
`http://127.0.0.1:8013`.

## Call Chat

```powershell
$body = @{
  user_id = "student-01"
  session_id = "demo-01"
  feature = "qa"
  message = "What is your refund policy? student@example.com"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8013/chat `
  -Headers @{"X-Correlation-ID" = "mentor-demo-001"} `
  -ContentType "application/json" `
  -Body $body
```

The same correlation ID appears in the response header, JSON logs, metrics
recent-request record, and Langfuse trace metadata.

The middleware treats `x-request-id` as the original public header. It falls
back to `X-Correlation-ID`, then generates a UUID. Every response returns both
headers with the same value.

## Incidents

```powershell
python scripts\inject_incident.py --base-url http://127.0.0.1:8013 --scenario rag_slow
python scripts\inject_incident.py --base-url http://127.0.0.1:8013 --scenario rag_slow --disable

python scripts\inject_incident.py --base-url http://127.0.0.1:8013 --scenario tool_fail
python scripts\inject_incident.py --base-url http://127.0.0.1:8013 --scenario tool_fail --disable

python scripts\inject_incident.py --base-url http://127.0.0.1:8013 --scenario cost_spike
python scripts\inject_incident.py --base-url http://127.0.0.1:8013 --scenario cost_spike --disable
```

- `rag_slow`: adds about 2.5 seconds to `rag.retrieve`.
- `tool_fail`: raises a controlled retrieval error; API returns 500 and stays alive.
- `cost_spike`: multiplies output token usage by four.

Use the investigation path `Metrics -> Traces -> Logs`.

## Test and Verify

```powershell
python -m pytest tests -v
python scripts\validate_logs.py
python scripts\eval_quality.py --base-url http://127.0.0.1:8013
python scripts\load_test.py --base-url http://127.0.0.1:8013 --concurrency 5
python scripts\collect_evidence.py --base-url http://127.0.0.1:8013
python scripts\build_dashboard.py
python scripts\check_alerts.py
python scripts\export_langfuse_evidence.py
```

One-command local verification on port 8013:

```powershell
.\scripts\verify_lab.ps1 -BaseUrl http://127.0.0.1:8013
```

The load test sends all 10 sample queries, producing at least 10
`chat_request` traces when Langfuse is configured.

## Two-Terminal Verification

Terminal 1:

```powershell
cd F:\VinUni_Lab\VinUni_Day13\nhom-B1-Day13
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --env-file .env --port 8013
```

Terminal 2:

```powershell
cd F:\VinUni_Lab\VinUni_Day13\nhom-B1-Day13
.\.venv\Scripts\Activate.ps1
python -m pytest tests -v
python scripts\validate_logs.py
python scripts\eval_quality.py --base-url http://127.0.0.1:8013
python scripts\load_test.py --base-url http://127.0.0.1:8013 --concurrency 5
python scripts\build_dashboard.py
python scripts\check_alerts.py
.\scripts\verify_lab.ps1 -BaseUrl http://127.0.0.1:8013
```

## Metrics

`GET /metrics` returns:

- total requests, successes, errors, error rate, and error breakdown
- request P50/P95/P99 and average latency
- RAG and LLM P50/P95 latency
- total and average input/output tokens
- total and average estimated cost
- average quality score and quality pass rate
- incident state and the latest 100 request summaries

Metrics are intentionally in memory for this four-hour lab and reset on restart.
The six dashboard panels are specified in `docs/dashboard-spec.md` and rendered
as a real, self-contained local dashboard at
[`docs/dashboard.html`](docs/dashboard.html). Regenerate it from evidence with:

```powershell
python scripts\build_dashboard.py
```

This is intentionally not presented as Prometheus or Grafana. It is an HTML
evidence dashboard for the lab's exported metric snapshots.

## Alerts

`config/alert_rules.yaml` contains machine-readable alert definitions.
The local alert engine evaluates those rules against incident evidence:

```powershell
python scripts\check_alerts.py
```

It verifies that `rag_slow` fires the RAG latency alert, `tool_fail` fires the
error-rate alert, and `cost_spike` fires the token/cost alert. Results are
written to `data/evidence/alert_validation.json`. This validates alert logic
locally; it is not a deployed Alertmanager.

## Logs and PII

Logs are JSON Lines in `data/logs.jsonl`. The logging processor recursively
redacts email, phone, credit card, national ID, passport, nested dictionaries,
nested lists, and fields named `user_id`.

Validation writes `data/evidence/log_validation.json`:

```powershell
python scripts\validate_logs.py
```

## Langfuse

With valid keys, each request creates:

```text
chat_request
  rag.retrieve
  llm.generate
  metrics.record
```

The project uses Langfuse Python SDK v4. The root pipeline observation is created
with `@observe(capture_input=False, capture_output=False)`, and only sanitized
input/output previews are attached explicitly. User, session, feature, model,
and correlation attributes are propagated to every child observation. The
heuristic `quality_score` is also attached as a numeric Langfuse score.

Open the configured Langfuse project, filter trace name `chat_request`, and
run `python scripts\export_langfuse_evidence.py` to write the latest 10 trace
URLs to `data/evidence/trace_ids.md`.

## Evidence and Submission

Generated evidence:

```text
data/evidence/baseline_metrics.json
data/evidence/rag_slow_metrics.json
data/evidence/tool_fail_metrics.json
data/evidence/cost_spike_metrics.json
data/evidence/quality_eval.json
data/evidence/log_validation.json
data/evidence/alert_validation.json
data/evidence/trace_ids.md
```

The individual submission report, evidence links, and screenshots are collected
in `docs/blueprint-template.md`.

## Rubric Status: 8/8

| Requirement | Evidence | Status |
|---|---|---|
| Starter app runs | `/health`, `/metrics`, verification script | Complete |
| Correlation/request IDs | `x-request-id`, fallback header, logs/traces/metrics | Complete |
| Enriched JSON logs | `data/logs.jsonl` | Complete |
| Recursive PII sanitization | tests and `log_validation.json` | Complete |
| Automated log validation | `scripts/validate_logs.py` | Complete |
| Langfuse tracing | 10 real links in `trace_ids.md` | Complete |
| Six-panel dashboard | `docs/dashboard.html` | Complete |
| YAML alert validation | `scripts/check_alerts.py` | Complete |
