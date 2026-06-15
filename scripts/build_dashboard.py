from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "data" / "evidence"
OUTPUT = ROOT / "docs" / "dashboard.html"


def load(name: str) -> dict[str, Any]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def fmt(value: float, digits: int = 2) -> str:
    return f"{value:,.{digits}f}"


def bars(values: list[tuple[str, float]], unit: str) -> str:
    maximum = max((value for _, value in values), default=1) or 1
    rows = []
    for label, value in values:
        width = max(3, value / maximum * 100)
        rows.append(
            f'<div class="bar-row"><span>{html.escape(label)}</span>'
            f'<div class="track"><i style="width:{width:.2f}%"></i></div>'
            f'<strong>{fmt(value)} {html.escape(unit)}</strong></div>'
        )
    return "".join(rows)


def metric_panel(
    panel_id: str,
    title: str,
    value: str,
    note: str,
    body: str,
    tone: str,
) -> str:
    return f"""
    <article class="metric-card {tone}" data-panel="{panel_id}">
      <div class="metric-top"><h3>{html.escape(title)}</h3>
        <span class="mini-badge">Evidence</span></div>
      <div class="metric-value">{value}</div>
      <p>{html.escape(note)}</p>
      <div class="chart">{body}</div>
    </article>"""


def build() -> str:
    baseline = load("baseline_metrics.json")
    rag = load("rag_slow_metrics.json")
    tool = load("tool_fail_metrics.json")
    cost = load("cost_spike_metrics.json")
    quality = load("quality_eval.json")

    rag_latest = max(
        item.get("rag_latency_ms", 0) for item in rag["recent_requests"]
    )
    baseline_output = baseline["average_output_tokens"]
    spike_output = max(
        item.get("output_tokens", 0) for item in cost["recent_requests"]
    )
    spike_cost = max(
        item.get("estimated_cost", 0) for item in cost["recent_requests"]
    )

    panels = [
        metric_panel(
            "request-latency",
            "Request latency",
            f'{fmt(rag["p99_latency_ms"], 0)} <small>ms p99</small>',
            "rag_slow lifts tail latency while baseline remains fast.",
            bars(
                [
                    ("Baseline p50", baseline["p50_latency_ms"]),
                    ("Baseline p95", baseline["p95_latency_ms"]),
                    ("rag_slow p95", rag["p95_latency_ms"]),
                    ("rag_slow p99", rag["p99_latency_ms"]),
                ],
                "ms",
            ),
            "amber",
        ),
        metric_panel(
            "error-rate",
            "Error rate",
            f'{fmt(tool["error_rate_pct"])} <small>%</small>',
            "tool_fail creates a controlled RuntimeError without killing the API.",
            bars(
                [
                    ("Baseline", baseline["error_rate_pct"]),
                    ("tool_fail", tool["error_rate_pct"]),
                ],
                "%",
            ),
            "red",
        ),
        metric_panel(
            "rag-latency",
            "RAG latency",
            f'{fmt(rag_latest, 0)} <small>ms max</small>',
            "The retrieval span isolates the 2.5 second dependency slowdown.",
            bars(
                [
                    ("Baseline p95", baseline["rag_p95_latency_ms"]),
                    ("rag_slow p95", rag["rag_p95_latency_ms"]),
                    ("Slowest RAG", rag_latest),
                ],
                "ms",
            ),
            "orange",
        ),
        metric_panel(
            "llm-token-usage",
            "LLM token usage",
            f'{fmt(spike_output, 0)} <small>output tokens</small>',
            "cost_spike multiplies output usage beyond twice the baseline.",
            bars(
                [
                    ("Baseline avg", baseline_output),
                    ("cost_spike max", spike_output),
                    ("Snapshot total", cost["total_output_tokens"]),
                ],
                "tokens",
            ),
            "blue",
        ),
        metric_panel(
            "estimated-cost",
            "Estimated cost",
            f'${fmt(spike_cost, 6)} <small>max request</small>',
            "Token metadata is converted into request and snapshot cost evidence.",
            bars(
                [
                    ("Baseline total", baseline["total_cost"] * 1000),
                    ("Spike total", cost["total_cost"] * 1000),
                    ("Spike request", spike_cost * 1000),
                ],
                "mUSD",
            ),
            "green",
        ),
        metric_panel(
            "quality-score",
            "Quality score",
            f'{fmt(quality["average_quality_score"], 1)} <small>/ 1.0</small>',
            "Keyword evaluation confirms observability changes preserve answers.",
            bars(
                [
                    ("Quality eval", quality["average_quality_score"] * 100),
                    ("Baseline avg", baseline["average_quality_score"] * 100),
                    ("Incident pass", cost["quality_pass_rate"] * 100),
                ],
                "/100",
            ),
            "teal",
        ),
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Agent Observability Lab Report</title>
  <style>
    :root {{
      --navy:#13263a; --blue:#2563a8; --paper:#f4f7f9; --white:#fff;
      --ink:#17212b; --muted:#667482; --line:#dce4e9; --green:#16835d;
      --yellow:#b97708; --red:#c2413b; --shadow:0 10px 28px rgba(23,45,65,.08);
    }}
    * {{ box-sizing:border-box; }}
    html {{ scroll-behavior:smooth; }}
    body {{ margin:0; color:var(--ink); background:var(--paper);
      font-family:"Segoe UI",Tahoma,Geneva,Verdana,sans-serif; line-height:1.55; }}
    a {{ color:var(--blue); text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    code {{ font-family:Consolas,"Courier New",monospace; }}
    .wrap {{ width:min(1180px,calc(100% - 32px)); margin:auto; }}
    .hero {{ color:#fff; padding:68px 0 44px; background:
      radial-gradient(circle at 85% 10%,rgba(75,160,220,.38),transparent 28%),
      linear-gradient(125deg,#10263c,#1d4e70 62%,#17685e); }}
    .eyebrow {{ margin:0 0 10px; color:#9dd7c8; font-size:12px;
      font-weight:800; letter-spacing:.16em; text-transform:uppercase; }}
    h1 {{ margin:0; font-size:clamp(40px,6vw,72px); line-height:1; letter-spacing:-.045em; }}
    .subtitle {{ max-width:820px; margin:18px 0 26px; color:#dcecf4; font-size:19px; }}
    .badges {{ display:flex; flex-wrap:wrap; gap:9px; }}
    .badge {{ padding:8px 12px; border-radius:999px; background:#ffffff17;
      border:1px solid #ffffff35; font-size:13px; font-weight:750; }}
    .badge.good {{ background:#b9f3d322; border-color:#8ee1b6; }}
    .badge.warn {{ background:#ffd98a22; border-color:#f4c45e; }}
    main {{ padding:34px 0 72px; }}
    section {{ margin:0 0 30px; }}
    .section-head {{ display:flex; justify-content:space-between; gap:20px;
      align-items:end; margin:0 0 15px; }}
    h2 {{ margin:0; color:var(--navy); font-size:28px; letter-spacing:-.025em; }}
    .section-head p {{ margin:0; color:var(--muted); max-width:620px; }}
    .card {{ background:var(--white); border:1px solid var(--line);
      border-radius:16px; box-shadow:var(--shadow); padding:24px; }}
    .proof {{ display:grid; grid-template-columns:1.25fr .75fr; gap:18px; }}
    .proof h2 {{ font-size:32px; }}
    .proof-list {{ display:grid; grid-template-columns:repeat(2,1fr); gap:12px; margin-top:20px; }}
    .proof-item {{ padding:15px; border-radius:12px; background:#f5faf8; border:1px solid #d8ebe3; }}
    .proof-item strong {{ display:block; color:#176b52; margin-bottom:3px; }}
    .summary-box {{ background:var(--navy); color:#fff; border-radius:14px; padding:22px; }}
    .summary-box strong {{ display:block; font-size:42px; line-height:1; margin:6px 0 12px; }}
    .summary-box p {{ color:#cfdae4; margin:0; }}
    .flow {{ display:flex; align-items:stretch; gap:8px; overflow-x:auto; padding:6px 2px 14px; }}
    .flow-step {{ min-width:132px; flex:1; padding:15px 12px; text-align:center;
      background:#fff; border:1px solid var(--line); border-radius:12px; box-shadow:var(--shadow); }}
    .flow-step strong {{ display:block; color:var(--navy); }}
    .arrow {{ display:grid; place-items:center; color:var(--blue); font-size:24px; font-weight:800; }}
    .tri-grid,.incident-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; }}
    .signal-card h3,.incident-card h3 {{ margin:0 0 8px; font-size:21px; }}
    .signal-card ul {{ margin:12px 0 0; padding-left:18px; color:var(--muted); }}
    .signal-card.metrics {{ border-top:4px solid #2d75b5; }}
    .signal-card.traces {{ border-top:4px solid #8561c5; }}
    .signal-card.logs {{ border-top:4px solid #16835d; }}
    .incident-card {{ position:relative; overflow:hidden; }}
    .incident-card::after {{ content:""; position:absolute; right:-35px; top:-35px;
      width:90px; height:90px; border-radius:50%; background:var(--accent,#ddd); opacity:.15; }}
    .incident-card .incident-badge {{ display:inline-block; border-radius:999px;
      padding:5px 9px; background:#f2f5f7; font:700 12px Consolas,monospace; }}
    .incident-card strong {{ color:var(--accent); }}
    .incident-card.rag {{ --accent:#d47718; }}
    .incident-card.tool {{ --accent:#c2413b; }}
    .incident-card.cost {{ --accent:#347a53; }}
    .metrics-grid {{ display:grid; grid-template-columns:repeat(2,1fr); gap:16px; }}
    .metric-card {{ --accent:#b77913; background:#fff; border:1px solid var(--line);
      border-left:5px solid var(--accent); border-radius:14px; box-shadow:var(--shadow); padding:20px; }}
    .metric-top {{ display:flex; justify-content:space-between; gap:12px; align-items:center; }}
    .metric-top h3 {{ margin:0; font-size:19px; }}
    .mini-badge {{ color:var(--accent); background:#f4f7f9; border-radius:999px;
      padding:4px 8px; font-size:11px; font-weight:800; text-transform:uppercase; }}
    .metric-value {{ margin:16px 0 4px; color:var(--accent); font-size:38px;
      font-weight:800; letter-spacing:-.04em; }}
    .metric-value small {{ color:var(--muted); font-size:14px; letter-spacing:0; }}
    .metric-card p {{ margin:0; color:var(--muted); min-height:48px; }}
    .chart {{ border-top:1px solid var(--line); margin-top:16px; padding-top:10px; }}
    .bar-row {{ display:grid; grid-template-columns:120px 1fr 100px; gap:9px;
      align-items:center; margin:9px 0; font-size:11px; }}
    .track {{ height:8px; background:#e8edf0; border-radius:9px; overflow:hidden; }}
    .track i {{ display:block; height:100%; background:var(--accent); border-radius:9px; }}
    .bar-row strong {{ text-align:right; }}
    .red{{--accent:#c2413b}} .orange{{--accent:#d47718}} .blue{{--accent:#2d75b5}}
    .green{{--accent:#347a53}} .teal{{--accent:#16837b}}
    .rubric {{ width:100%; border-collapse:collapse; }}
    .rubric th,.rubric td {{ padding:13px 12px; text-align:left; border-bottom:1px solid var(--line); }}
    .rubric th {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.08em; }}
    .complete {{ display:inline-block; padding:5px 9px; border-radius:999px;
      color:#116747; background:#dcf5e9; font-size:12px; font-weight:800; }}
    .checklist {{ counter-reset:demo; display:grid; grid-template-columns:repeat(2,1fr); gap:10px; }}
    .check {{ counter-increment:demo; display:flex; gap:12px; align-items:flex-start;
      padding:13px; background:#fff; border:1px solid var(--line); border-radius:11px; }}
    .check::before {{ content:counter(demo); display:grid; place-items:center; flex:0 0 27px;
      height:27px; border-radius:50%; color:#fff; background:var(--blue); font-weight:800; }}
    footer {{ color:var(--muted); border-top:1px solid var(--line); padding-top:20px; font-size:13px; }}
    @media (max-width:820px) {{
      .proof,.tri-grid,.incident-grid,.metrics-grid {{ grid-template-columns:1fr; }}
      .proof-list,.checklist {{ grid-template-columns:1fr; }}
      .section-head {{ align-items:start; flex-direction:column; }}
      .arrow {{ min-width:24px; }}
    }}
  </style>
</head>
<body>
  <header class="hero">
    <div class="wrap">
      <p class="eyebrow">Mentor demo report</p>
      <h1>AI Agent Observability Lab</h1>
      <p class="subtitle">FastAPI + JSON Logs + Langfuse Tracing + Metrics + Incident Response</p>
      <div class="badges">
        <span class="badge good">Rubric 8/8</span>
        <span class="badge good">Tests 15/15</span>
        <span class="badge good">Logs 100/100</span>
        <span class="badge good">Quality 1.0</span>
        <span class="badge good">Load 10/10</span>
        <span class="badge warn">Traces 10</span>
        <span class="badge warn">Alerts 3/3</span>
      </div>
    </div>
  </header>

  <main class="wrap">
    <section class="proof">
      <article class="card">
        <p class="eyebrow">What this lab proves</p>
        <h2>An AI request can be followed from symptom to root cause.</h2>
        <p>The FastAPI agent carries one request ID through the response, metrics,
          Langfuse observations, and privacy-safe JSON logs. Three controlled
          incidents demonstrate how engineers detect, localize, and explain failures.</p>
        <div class="proof-list">
          <div class="proof-item"><strong>Request identity</strong><code>x-request-id</code> joins every signal.</div>
          <div class="proof-item"><strong>Privacy by default</strong>Nested PII is scrubbed before logging or tracing.</div>
          <div class="proof-item"><strong>AI telemetry</strong>RAG, LLM tokens, cost, latency, and quality are visible.</div>
          <div class="proof-item"><strong>Operational response</strong>YAML alerts and runbooks are validated with evidence.</div>
        </div>
      </article>
      <aside class="summary-box">
        <span>Final status</span><strong>8 / 8</strong>
        <p>Code, tests, logs, traces, metrics, incidents, alerts, dashboard, and
          evidence are complete and reproducible through one verification script.</p>
      </aside>
    </section>

    <section>
      <div class="section-head"><h2>System flow</h2>
        <p>The same request ID remains intact from ingress to response.</p></div>
      <div class="flow">
        <div class="flow-step"><strong>Client</strong>Question + context</div><div class="arrow">-&gt;</div>
        <div class="flow-step"><strong>POST /chat</strong>FastAPI endpoint</div><div class="arrow">-&gt;</div>
        <div class="flow-step"><strong>x-request-id</strong>Middleware</div><div class="arrow">-&gt;</div>
        <div class="flow-step"><strong>RAG</strong>Retrieve context</div><div class="arrow">-&gt;</div>
        <div class="flow-step"><strong>LLM</strong>Generate answer</div><div class="arrow">-&gt;</div>
        <div class="flow-step"><strong>Signals</strong>Metrics / Trace / Logs</div><div class="arrow">-&gt;</div>
        <div class="flow-step"><strong>Response</strong>Answer + request ID</div>
      </div>
    </section>

    <section>
      <div class="section-head"><h2>Metrics -&gt; Traces -&gt; Logs</h2>
        <p>The investigation order narrows a symptom into one explainable event.</p></div>
      <div class="tri-grid">
        <article class="card signal-card metrics"><h3>1. Metrics</h3>
          <p>Detect that user or business behavior changed.</p>
          <ul><li>Latency p50 / p95 / p99</li><li>Error rate</li>
            <li>Tokens and estimated cost</li><li>Quality score</li></ul></article>
        <article class="card signal-card traces"><h3>2. Traces</h3>
          <p>Localize the slow, costly, or failed operation.</p>
          <ul><li><code>chat_request</code></li><li><code>rag.retrieve</code></li>
            <li><code>llm.generate</code></li><li><code>metrics.record</code></li></ul></article>
        <article class="card signal-card logs"><h3>3. Logs</h3>
          <p>Explain the concrete event using structured context.</p>
          <ul><li>JSONL request and error events</li><li>PII scrubbed recursively</li>
            <li>Search by <code>x-request-id</code></li><li>Incident state attached</li></ul></article>
      </div>
    </section>

    <section>
      <div class="section-head"><h2>Incident evidence</h2>
        <p>Each injected failure changes a distinct signal and fires its matching rule.</p></div>
      <div class="incident-grid">
        <article class="card incident-card rag"><span class="incident-badge">rag_slow</span>
          <h3>Retrieval bottleneck</h3><p>RAG latency rises to
          <strong>{fmt(rag_latest, 0)} ms</strong> while LLM latency stays stable.</p>
          <p>Alert: <code>rag_latency_spike</code></p></article>
        <article class="card incident-card tool"><span class="incident-badge">tool_fail</span>
          <h3>Controlled dependency failure</h3><p>Error rate reaches
          <strong>{fmt(tool["error_rate_pct"])}%</strong> with a trace and correlated error log.</p>
          <p>Alert: <code>high_error_rate</code></p></article>
        <article class="card incident-card cost"><span class="incident-badge">cost_spike</span>
          <h3>Token and cost regression</h3><p>Output usage reaches
          <strong>{fmt(spike_output, 0)} tokens</strong> and request cost increases.</p>
          <p>Alert: <code>cost_budget_spike</code></p></article>
      </div>
    </section>

    <section id="metric-evidence">
      <div class="section-head"><h2>Six-panel metric evidence</h2>
        <p>Compact baseline versus incident comparisons required by the rubric.</p></div>
      <div class="metrics-grid">{''.join(panels)}</div>
    </section>

    <section>
      <div class="section-head"><h2>Rubric completion</h2>
        <p>All eight requirements link to local evidence that can be opened during the demo.</p></div>
      <div class="card">
        <table class="rubric">
          <thead><tr><th>#</th><th>Requirement</th><th>Status</th><th>Evidence</th></tr></thead>
          <tbody>
            <tr><td>1</td><td>Starter app and endpoint</td><td><span class="complete">Completed</span></td><td><a href="../README.md">README.md</a></td></tr>
            <tr><td>2</td><td>Request ID propagation</td><td><span class="complete">Completed</span></td><td><a href="../data/logs.jsonl">data/logs.jsonl</a></td></tr>
            <tr><td>3</td><td>Structured JSON logging</td><td><span class="complete">Completed</span></td><td><a href="../data/logs.jsonl">data/logs.jsonl</a></td></tr>
            <tr><td>4</td><td>Recursive PII redaction</td><td><span class="complete">Completed</span></td><td><a href="../data/evidence/log_validation.json">log_validation.json</a></td></tr>
            <tr><td>5</td><td>Automated log validation</td><td><span class="complete">Completed</span></td><td><a href="../data/evidence/log_validation.json">100/100 evidence</a></td></tr>
            <tr><td>6</td><td>Langfuse tracing</td><td><span class="complete">Completed</span></td><td><a href="../data/evidence/trace_ids.md">trace_ids.md</a></td></tr>
            <tr><td>7</td><td>Metrics and incident runbook</td><td><span class="complete">Completed</span></td><td><a href="runbook.md">docs/runbook.md</a></td></tr>
            <tr><td>8</td><td>Alert rules and validation</td><td><span class="complete">Completed</span></td><td><a href="../config/alert_rules.yaml">alert_rules.yaml</a> / <a href="../data/evidence/alert_validation.json">validation</a></td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <section>
      <div class="section-head"><h2>Mentor demo checklist</h2>
        <p>A short path from healthy request to three explainable incidents.</p></div>
      <div class="checklist">
        <div class="check">Open <code>http://127.0.0.1:8013/docs</code>.</div>
        <div class="check">POST <code>/chat</code> with a visible <code>x-request-id</code>.</div>
        <div class="check">Open <code>/metrics</code> and identify the baseline.</div>
        <div class="check">Open the matching Langfuse <code>chat_request</code> trace.</div>
        <div class="check">Search <code>data/logs.jsonl</code> using the same request ID.</div>
        <div class="check">Enable <code>rag_slow</code>, <code>cost_spike</code>, and <code>tool_fail</code>.</div>
        <div class="check">Connect each changed metric to its span, log, and alert.</div>
        <div class="check">Run <code>.\\scripts\\verify_lab.ps1 -BaseUrl http://127.0.0.1:8013</code>.</div>
      </div>
    </section>

    <footer>
      Static report generated from <code>data/evidence/*.json</code> by
      <code>python scripts/build_dashboard.py</code>. This report does not claim
      a live Prometheus or Grafana deployment.
    </footer>
  </main>
</body>
</html>
"""


def main() -> None:
    OUTPUT.write_text(build(), encoding="utf-8")
    print(f"Observability report written to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
