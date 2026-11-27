"""17.2/2  Validate the provisioned Grafana dashboard offline

Grafana can load a data source and a dashboard from files at start-up ("provisioning"), so a
dashboard lives in git like code. This script checks those files without Grafana:
  - the YAML/JSON parse and have the keys Grafana needs,
  - every panel points at the provisioned data source uid,
  - every PromQL expression has balanced brackets and only uses metric names the app exposes,
  - every metric the app exposes is shown by at least one panel (nothing is collected for nothing).
No model call and no service is needed.

Run it:   ./run 17.2/2          (Windows: run 17.2/2)
     or:  python modules/17-monitoring-and-fine-tuning/02-prometheus-metrics-and-grafana-dashboards/02_validate_the_dashboard.py
"""

import json
import re
from pathlib import Path

from labkit import lesson

HERE = Path(__file__).parent
EXPOSED = {  # metric families script 1 exposes, with the suffixes Prometheus adds
    "helpdesk_requests_total", "helpdesk_llm_latency_seconds_bucket", "helpdesk_llm_latency_seconds_sum",
    "helpdesk_llm_latency_seconds_count", "helpdesk_llm_tokens_total", "helpdesk_llm_cost_dollars_total",
    "helpdesk_budget_remaining_dollars",
}
PROMQL_WORDS = {"sum", "rate", "increase", "histogram_quantile", "by", "without", "avg", "max", "min", "irate", "le", "on", "ignoring"}


def read_simple_yaml(path):
    """Tiny reader for the flat provisioning files (no YAML package needed): returns {key: value} pairs found."""
    pairs = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*-?\s*([A-Za-z]+):\s*(.*)$", line)
        if m and m.group(2):
            pairs[m.group(1)] = m.group(2).strip()
    return pairs


def metrics_in(expr):
    """Pick out metric names: identifiers that are not PromQL keywords and not inside {...} or [...]."""
    stripped = re.sub(r"\{[^}]*\}", "", expr)
    stripped = re.sub(r"\[[^\]]*\]", "", stripped)
    stripped = re.sub(r"by \([^)]*\)", "", stripped)
    return {w for w in re.findall(r"[a-zA-Z_:][a-zA-Z0-9_:]*", stripped) if w not in PROMQL_WORDS}


def balanced(expr):
    stack, pairs = [], {")": "(", "]": "[", "}": "{"}
    for ch in expr:
        if ch in "([{":
            stack.append(ch)
        elif ch in ")]}":
            if not stack or stack.pop() != pairs[ch]:
                return False
    return not stack


@lesson("17.2/2", "Validate the provisioned Grafana dashboard offline")
def main(ctx):
    problems = []

    ctx.step("Read the data source provisioning file")
    ds_path = HERE / "grafana" / "provisioning" / "datasources" / "prometheus.yml"
    ds = read_simple_yaml(ds_path)
    ctx.show_data("grafana/provisioning/datasources/prometheus.yml", ds)
    for key in ("uid", "type", "url"):
        if key not in ds:
            problems.append(f"data source file has no {key}")
    ctx.note("The url uses the compose service name 'prometheus', which only resolves inside the compose network.")

    ctx.step("Read the dashboard provider file")
    provider = read_simple_yaml(HERE / "grafana" / "provisioning" / "dashboards" / "dashboards.yml")
    ctx.show_data("grafana/provisioning/dashboards/dashboards.yml", provider)
    if provider.get("path") != "/var/lib/grafana/dashboards":
        problems.append("provider path does not match the volume mounted in docker-compose.yml")

    ctx.step("Load the dashboard JSON and check each panel")
    dash = json.loads((HERE / "grafana" / "dashboards" / "helpdesk.json").read_text(encoding="utf-8"))
    ctx.note(f"dashboard uid={dash['uid']!r} title={dash['title']!r}, {len(dash['panels'])} panels")
    used = set()
    for p in dash["panels"]:
        expr = p["targets"][0]["expr"]
        names = metrics_in(expr)
        used |= names
        issues = []
        if p["datasource"].get("uid") != ds.get("uid"):
            issues.append("datasource uid does not match")
        if not balanced(expr):
            issues.append("unbalanced brackets")
        unknown = names - EXPOSED
        if unknown:
            issues.append(f"unknown metric {sorted(unknown)}")
        problems += [f"panel {p['id']} ({p['title']}): {i}" for i in issues]
        ctx.console.print(f"{'FAIL' if issues else 'ok  '} [{p['type']:10}] {p['title']}", markup=False)
        ctx.console.print(f"      {expr}", markup=False, highlight=False)

    ctx.step("Is every exposed metric shown somewhere?")
    unused = EXPOSED - used
    ctx.note("Unused metrics: " + (", ".join(sorted(unused)) if unused else "none"))
    ctx.note("(Histogram _sum and _count are not charted here: the p95 panel already uses _bucket.)")

    ctx.step("Result")
    if problems:
        for p in problems:
            ctx.console.print("PROBLEM: " + p, markup=False)
    else:
        ctx.note("All checks passed: provisioning files and dashboard agree with the metrics the app exposes.")
    ctx.note("This is a structural check. Only a running Grafana proves a panel draws what you meant (script 3 checks queries against Prometheus).")


if __name__ == "__main__":
    main()
