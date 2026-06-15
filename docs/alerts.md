# Alert Rules

Alert definitions live in `config/alert_rules.yaml`. Operational investigation
steps live in `docs/runbook.md`.

| Alert | Severity | Trigger | Runbook |
|---|---|---|---|
| `rag_latency_spike` | P2 | `max_recent_rag_latency_ms > 2000` | `docs/runbook.md#rag_slow` |
| `high_error_rate` | P1 | `error_rate_pct > 5` | `docs/runbook.md#tool_fail` |
| `cost_budget_spike` | P2 | `max_recent_output_tokens > 2x baseline` | `docs/runbook.md#cost_spike` |

The rules are owned by the individual project maintainer. The YAML is a
portable lab specification, not an active alerting server.
Import equivalent expressions into Grafana, Datadog, or another monitoring
platform for live notifications.
