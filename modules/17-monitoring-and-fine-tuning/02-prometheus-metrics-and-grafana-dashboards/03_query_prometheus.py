"""17.2/3  Run the dashboard's queries against a real Prometheus

Needs Prometheus (PROMETHEUS_URL). Start it with `docker compose up -d` in this folder. Run
script 1 with LESSON_METRICS_PORT=8000 so there is something to scrape, then run this script.
It reads every PromQL expression from the dashboard JSON and asks the Prometheus HTTP API
(/api/v1/query) for the current value, so you can see which panels would be empty.

Run it:   ./run 17.2/3          (Windows: run 17.2/3)
     or:  python modules/17-monitoring-and-fine-tuning/02-prometheus-metrics-and-grafana-dashboards/03_query_prometheus.py
"""

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

from labkit import lesson
from labkit.services import require

DASHBOARD = Path(__file__).parent / "grafana" / "dashboards" / "helpdesk.json"


def query(base, expr):
    url = f"{base.rstrip('/')}/api/v1/query?" + urllib.parse.urlencode({"query": expr})
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


@lesson("17.2/3", "Run the dashboard's queries against a real Prometheus")
def main(ctx):
    ctx.step("Check that Prometheus is reachable")
    require("PROMETHEUS_URL")
    base = os.environ["PROMETHEUS_URL"].strip()
    ctx.note(f"Prometheus found at {base}")

    ctx.step("Is the helpdesk target being scraped?")
    up = query(base, 'up{job="helpdesk-assistant"}')["data"]["result"]
    ctx.note("target UP" if up and up[0]["value"][1] == "1" else "target missing or DOWN: run script 1 with LESSON_METRICS_PORT=8000 and look at /targets")

    ctx.step("Run each panel's query")
    dash = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    empty = 0
    for p in dash["panels"]:
        expr = p["targets"][0]["expr"]
        result = query(base, expr)["data"]["result"]
        values = [r["value"][1] for r in result]
        empty += not values
        ctx.console.print(f"{p['title']}: {values if values else 'no data yet'}", markup=False)
    ctx.note(f"{len(dash['panels']) - empty} of {len(dash['panels'])} panels have data.")
    ctx.note("Panels that use rate() need at least two scrapes in the window. If they are empty, wait 15 seconds and rerun.")


if __name__ == "__main__":
    main()
