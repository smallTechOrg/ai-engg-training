# 17.2 · Prometheus metrics and Grafana dashboards

**Module:** [17 · Monitoring, evaluation and fine-tuning](../README.md) · **Time:** 45-60 minutes · **Model needs:** chat (script 1 only) · **Packages:** `observability` extra (`prometheus-client`; install with `./setup.sh --all`) · **Services (optional):** Prometheus (`PROMETHEUS_URL`), Grafana (`GRAFANA_URL`)

## What you will learn

- How Prometheus collects metrics: it **pulls** (scrapes) a `/metrics` HTTP endpoint on a schedule.
- How to serve metrics from your own process and read them back with a plain HTTP request.
- How `rate()`, `increase()` and `histogram_quantile()` turn raw counters into per-second rates and percentiles.
- How a Grafana dashboard and data source are **provisioned from files**, so they live in git.
- How to check a dashboard offline: do its queries only use metrics the app really exposes?

Scripts 1 and 2 need no service. Only script 3 needs Prometheus.

## The idea

**What is new since 17.1.** In 17.1 you printed `generate_latest()` as text. Now the metrics are served by a real HTTP endpoint, parsed back like a scraper would, and you add the other half: a dashboard that charts them, defined in files.

Prometheus stores numbers over time. Every few seconds it GETs your `/metrics`, stamps the values with the time, and keeps them. Because it stores totals (counters only go up), a chart needs a function that turns totals into something readable:

| PromQL | Meaning |
| --- | --- |
| `rate(x_total[5m])` | per-second increase of a counter, averaged over 5 minutes |
| `increase(x_total[1h])` | how much a counter grew in an hour |
| `histogram_quantile(0.95, sum by (le) (rate(x_bucket[5m])))` | estimated 95th percentile from histogram buckets |
| `sum by (category) (...)` | add series together, keep one label |

```mermaid
flowchart LR
    App["Helpdesk app<br/>/metrics"] -- "scrape every 5 s" --> Prom["Prometheus<br/>:9090"]
    Prom -- "PromQL" --> Graf["Grafana<br/>:3000"]
    Files["grafana/provisioning/*.yml<br/>grafana/dashboards/helpdesk.json"] -- "loaded at start" --> Graf
    Prom --> Alert["Alert rules"]
```

**Provisioning** means Grafana reads files at start-up instead of you clicking in the UI. `provisioning/datasources/prometheus.yml` says where Prometheus is. `provisioning/dashboards/dashboards.yml` says which folder holds dashboard JSON. `dashboards/helpdesk.json` has six panels: request rate by category, error ratio, p95 latency, tokens per minute, dollars in the last hour, budget left. A dashboard in git can be reviewed, diffed and rolled back.

Two cautions. A histogram's p95 is an estimate that depends on your bucket edges (script 1 prints the bucket counts so you can see why). And `rate()` needs two scrapes inside its window, so a freshly started app shows empty panels for the first 10-15 seconds.

## Scripts

### 1. `01_serve_and_scrape.py` — serve `/metrics`, then scrape it yourself

Run: `./run 17.2/1`. Defines the metrics, starts `prometheus_client.start_http_server` on a free port (port 0) bound to `127.0.0.1`, makes four real calls, fetches `/metrics` with `urllib`, parses the text with `prometheus_client.parser`, and computes the average latency and the cumulative buckets by hand. Set `LESSON_METRICS_PORT=8000` to serve on a fixed port for a real Prometheus (the script then waits 60 seconds).

**Expected output** (trimmed, real run):

```text
Step 2: Start the metrics server on a free port
Serving http://127.0.0.1:62656/metrics from a background thread. Prometheus calls this a 'target'.
...
Step 4: Scrape it like Prometheus does: an HTTP GET to /metrics
HTTP 200, Content-Type: text/plain; version=0.0.4; charset=utf-8, 43 lines. The first helpdesk lines:
helpdesk_requests_total{category="network",status="ok"} 1.0
helpdesk_requests_total{category="account",status="ok"} 1.0
...
Step 5: Parse the scraped text into samples
25 samples parsed. helpdesk_requests_total{category=network,status=ok} = 1

Step 6: Compute by hand what PromQL would say
average latency = sum / count = 2.79 s / 4 = 0.70 s
  le=0.25s  0 of 4 calls
  le=0.5s  0 of 4 calls
  le=1s  4 of 4 calls
  le=2s  4 of 4 calls
...
Run summary: 4 model call(s), 101 in + 79 out = 180 tokens, 3.3s
```

Notice the `_created` lines: the client library adds a creation timestamp per series. Prometheus ignores them for charts.

### 2. `02_validate_the_dashboard.py` — validate the provisioned dashboard offline

Run: `./run 17.2/2`. No model call. Reads the three files in `grafana/`, checks the data source uid in each panel, brackets in each PromQL expression, and that every metric name is one the app exposes. It reports exposed metrics no panel uses.

**Expected output** (trimmed, real run):

```text
Step 3: Load the dashboard JSON and check each panel
dashboard uid='larkspur-helpdesk' title='Larkspur helpdesk assistant', 6 panels
ok   [timeseries] Requests per second by category
      sum by (category) (rate(helpdesk_requests_total[5m]))
...
Step 4: Is every exposed metric shown somewhere?
Unused metrics: helpdesk_llm_latency_seconds_count, helpdesk_llm_latency_seconds_sum
Step 5: Result
All checks passed: provisioning files and dashboard agree with the metrics the app exposes.
```

### 3. `03_query_prometheus.py` — run the dashboard's queries for real

Run: `./run 17.2/3`. Needs `PROMETHEUS_URL`. It calls `require("PROMETHEUS_URL")` first, then asks `/api/v1/query` for the current result of every panel expression and tells you which panels have data.

**Expected output on this machine (no Prometheus), real run, exit code 3:**

```text
Step 1: Check that Prometheus is reachable
This lesson needs Prometheus: PROMETHEUS_URL is not set.
- Start one: docker run --rm -p 9090:9090 prom/prometheus
- Then set it in .env, for example PROMETHEUS_URL=http://localhost:9090
```

(Use this lesson's `docker compose up -d` instead of `docker run`: it also loads `prometheus.yml` with the scrape target.) With the stack running and script 1 serving on port 8000, you will see `target UP`, then one line per panel with a value list (described, not pasted: not run here). Open Grafana at `http://localhost:3000`: the folder "Larkspur Labs" holds the dashboard.

## Try this

1. In script 1 add a `model` label to the request counter and call it with two different `--model` names. What does the scrape text look like now?
2. Change `BUCKETS` so the smallest bucket is 2 seconds. What does the "p95" become for calls that take 0.7 s? What does that tell you about choosing bucket edges?
3. Add a panel to `helpdesk.json` for `helpdesk_budget_remaining_dollars < 5` and run script 2. Then add a panel using a metric that does not exist and see it fail.
4. Write a PromQL expression for "dollars per ticket" (cost increase divided by request increase over an hour). Which two metrics does it need?
5. Scrape twice, ten seconds apart, and compute `rate()` yourself from the two counter values.
6. In `docker-compose.yml`, why is Grafana's provisioning folder mounted `:ro`? What would you lose by editing dashboards in the UI only?

## If it does not work

- Run `./run doctor` to see which services and extras are detected. Install the extra with `./setup.sh --all`.
- **The stack files:** `docker-compose.yml` starts Prometheus (`prom/prometheus:v3`, scraping `host.docker.internal:8000` per `prometheus.yml`) and Grafana (`grafana/grafana:12`, anonymous viewer access for local use). Ports are bound to `127.0.0.1`. Start with `docker compose up -d` in this folder, stop with `docker compose down`. Then set `PROMETHEUS_URL=http://localhost:9090` and `GRAFANA_URL=http://localhost:3000` in `.env`.
- **Honest note:** these files were verified by CI structure checks and script 2, not run on the author's machine (no Docker there). Image tags may have moved on; Grafana's dashboard JSON schema also evolves, so open the dashboard once and save it again if a panel looks odd.
- **Cloud or native instead of Docker:** set `PROMETHEUS_URL` (and `GRAFANA_URL`) in `.env` to the hosted address. For a hosted Prometheus you must make your app's metrics reachable (remote write or an agent); keep any credentials in `.env`.
- Target DOWN on Linux: the `extra_hosts` line is what makes `host.docker.internal` resolve; without it use your machine's address.
- `Address already in use` with `LESSON_METRICS_PORT`: pick another port and edit `prometheus.yml`.

## In the running scenario

The helpdesk assistant now has a wall display. Support leads see tickets per category, the share that failed, how slow the slow tail is, and how many dollars the day has cost. The dashboard is a file in the repo, so a new on-call engineer gets the same view by running one command.

**Next:** 17.3 · Cost tracking, budgets and service-level objectives (planned)
