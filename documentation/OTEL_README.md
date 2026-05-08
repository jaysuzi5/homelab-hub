# OTEL — Homelab Hub

Two distinct OTEL concerns:

1. **Application Instrumentation** — what the Django app itself emits (logs, traces, metrics)
2. **Dashboard Display** — what OTEL data is surfaced in the UI (Logging/Trace/Metrics explorers + Collector Job Summary)

---

---

# Part 1: Application Instrumentation

The Django app emits OTEL signals for every page request via `hub/otel.py` and `hub/middleware.py`.

## Setup — `hub/otel.py`

Called once at startup by `PageLoggingMiddleware`. Initializes three providers, all exporting over OTLP/HTTP to `OTLP_ENDPOINT`:

| Provider | Export endpoint | Signal |
|---|---|---|
| `TracerProvider` | `$OTLP_ENDPOINT/v1/traces` | Distributed traces |
| `MeterProvider` | `$OTLP_ENDPOINT/v1/metrics` | Metrics |
| `LoggerProvider` | `$OTLP_ENDPOINT/v1/logs` | Structured logs |

If `OTLP_ENDPOINT` is unset, providers are still initialized but nothing is exported.

**Metric created:** `page_visits_total` (counter, unit `"1"`) — incremented per response with labels `endpoint`, `method`, `status`.

**Tracer created:** `_tracer` (service name from `OTEL_SERVICE_NAME`, default `"homelab-hub"`) — used by middleware and dashboard views for manual spans.

## Middleware — `hub/middleware.py` → `PageLoggingMiddleware`

Wraps every request. Skips paths matching `_SKIP_PREFIXES`: `/admin/`, `/accounts/`, `/static/`, `/favicon`, `/__reload__`.

**Per request:**

1. Generates a `transaction_id` (UUID4), stored on `request.otel_transaction_id`
2. Resolves path to a logical `endpoint` string (e.g. `dashboard/home`, `financial/calculator`)
3. Emits a **Request log** (JSON to `page` logger → OTLP logs)
4. Starts an OTEL span with kind `SERVER`, attributes: `http.method`, `http.path`, `transaction_id`
5. Calls the view
6. Closes span, captures `trace_id` and `span_id` from span context
7. Emits a **Response log** (JSON to `page` logger → OTLP logs)
8. Increments `page_visits_total` metric

## Log Format

Both request and response events are structured JSON dicts emitted to the `page` Python logger, which is bridged to OTLP via `LoggingHandler`. They land in Splunk at index `otel_logging`.

**Request event fields:**

| Field | Value |
|---|---|
| `event` | `"Request"` |
| `method` | HTTP method |
| `version` | `"v1"` (hardcoded) |
| `service` | `OTEL_SERVICE_NAME` |
| `timestamp` | UTC ISO 8601 |
| `transaction_id` | UUID4 |
| `level` | `"INFO"` |
| `endpoint` | logical endpoint string |
| `hostname` | pod hostname |
| `path` | raw URL path |
| `remote_addr` | client IP (respects `X-Forwarded-For`) |
| `request_body` | `{}` (not captured) |
| `query_params` | `dict(request.GET)` |

**Response event adds:**

| Field | Value |
|---|---|
| `event` | `"Response"` |
| `duration_seconds` | float, rounded to 6 decimal places |
| `status` | HTTP status code (int) |
| `level` | `"INFO"` if status < 400, `"ERROR"` otherwise |
| `response_body` | `request.otel_page_summary` dict (set by the view) |
| `trace_id` | 32-char hex trace ID (if span was active) |
| `span_id` | 16-char hex span ID (if span was active) |

## Manual Spans — `dashboard/views.py`

The `home()` view wraps each dashboard card in a child span under the request span:

| Span name | What it covers |
|---|---|
| `card.k8s` | Kubernetes metrics collection |
| `card.synology` | NAS health and storage metrics |
| `card.claude` | Claude API usage data |
| `card.network` | Network traffic metrics |
| `card.emporia_chart` | Energy usage chart data |
| `card.emporia_daily` | Daily energy usage summary |
| `card.splunk` | Splunk collector job summary |
| `card.weather` | Weather data |

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `OTLP_ENDPOINT` | `""` (disabled) | Base URL for OTLP/HTTP export, e.g. `http://otel-collector.monitoring.svc.cluster.local:4318` |
| `OTEL_SERVICE_NAME` | `"homelab-hub"` | Service name on all signals |

## Dependencies (`pyproject.toml`)

```toml
"opentelemetry-api>=1.24.0",
"opentelemetry-sdk>=1.24.0",
"opentelemetry-exporter-otlp-proto-http>=1.24.0",
```

## Signal Destinations

All signals route through the OTEL Collector (`otel-collector`, `monitoring` namespace):

```
homelab-hub (Django)
  └── hub/otel.py + PageLoggingMiddleware
        └── OTLP/HTTP (port 4318) → OpenTelemetry Collector
              ├── Logs  → Splunk HEC → index: otel_logging
              ├── Traces → Tempo (tempo.monitoring.svc.cluster.local:3100)
              └── Metrics → Prometheus (prometheus-operator, port 9090)
```

---

---

# Part 2: Dashboard Display

The dashboard has four OTEL-related UI areas, each backed by a different data source.

## OTEL Overview — `/otel/`

**View:** `otel_overview()` in `dashboard/views.py`  
**Template:** `dashboard/otel.html`  
**Source:** Splunk index `otel_logging`  
**Service function:** `otel_service_status_summary()` in `dashboard/services/splunk.py`

Displays a pivot table of **service × HTTP status code** with transaction counts. Each row is a service; columns are status codes found in the time window. Supports a time range selector (1h, 6h, 24h, 7d, 30d).

Clicking a service row navigates to the Logging Explorer filtered to that service.

**AJAX endpoints used:**
- `/otel/endpoint-detail/?service=&earliest=` → `otel_endpoint_summary()` — per-endpoint breakdown for a service
- `/otel/transaction-detail/?service=&endpoint=&method=&status=&earliest=` → `otel_transaction_list()` — individual transaction records

---

## Logging Explorer — `/otel/logging/`

**View:** `otel_logging_overview()` in `dashboard/views.py`  
**Template:** `dashboard/otel_logging.html`  
**Source:** Splunk index `otel_logging`  
**Service function:** `otel_summary()` in `dashboard/services/splunk.py`

Displays a summary table of all `event="Response"` log records grouped by `service / endpoint / method / status`, showing:

| Column | Source |
|---|---|
| Service | `service` field |
| Endpoint | `endpoint` field |
| Method | HTTP method |
| Status | HTTP status code |
| Count | `dc(transaction_id)` |
| Avg Duration | `avg(duration_seconds)` |

Clicking a row opens a transaction list panel, loaded via AJAX to `/otel/logging/transactions/` → `otel_filtered_transactions()`. Each transaction shows timestamp, duration, trace_id (linked to Trace Explorer), and response body summary.

Supports time range selector (1h, 6h, 24h, 7d, 30d) and client-side filter/search.

---

## Trace Explorer — `/otel/trace/`

**View:** `otel_trace_overview()` in `dashboard/views.py`  
**Template:** `dashboard/otel_trace.html`  
**Source:** Grafana Tempo  
**Config:** `TEMPO_URL` env var (default: `http://tempo.monitoring.svc.cluster.local:3100`)  
**Service functions:** `tempo_services()`, `tempo_recent_traces()`, `tempo_trace_detail()` in `dashboard/services/tempo.py`

Displays recent distributed traces from Tempo, filterable by service and time range. Shows per-trace: trace ID, root span name, duration, start time, and span count.

Clicking a trace loads the full span waterfall detail (spans with parent/child relationships, duration bars, service labels).

If a `?trace_id=` query param is present on page load, that trace is auto-loaded and the service filter is auto-detected from the trace's `service.name` resource attribute.

The Logging Explorer links directly to this page via `?trace_id=<id>` on rows that have a `trace_id` field.

**AJAX endpoint:** `/otel/trace/detail/?trace_id=` → `otel_trace_detail_view()` → `tempo_trace_detail()`

---

## Metrics Explorer — `/otel/metrics/`

**View:** `otel_metrics_overview()` in `dashboard/views.py`  
**Template:** `dashboard/otel_metrics.html`  
**Source:** Prometheus  
**Config:** `PROMETHEUS_URL` env var (default: `http://prometheus-operator-kube-p-prometheus.monitoring.svc.cluster.local:9090`)  
**Service functions:** `prom_instant_query()`, `prom_range_query()` in `dashboard/services/prometheus_svc.py`

Provides a PromQL query interface. Supports two query modes:

| Mode | Endpoint | Prometheus API |
|---|---|---|
| Instant | `/otel/metrics/query/?type=instant&query=` | `/api/v1/query` |
| Range | `/otel/metrics/query/?type=range&query=&earliest=` | `/api/v1/query_range` with step `60s` |

Returns raw Prometheus result sets which the template renders as tables or charts.

Example query to see app traffic: `page_visits_total`

---

## Collector Job Summary — Main Dashboard `/`

**Tab:** "Collector Job Summary: Last 24 hours" on `homelab-hub.com/`  
**View:** `home()` → `card_splunk()` in `dashboard/views.py`  
**Source:** Splunk index `otel_logging`  
**Service function:** `splunk_collector_summary()` in `dashboard/services/splunk.py`

Displays `transaction_end` events emitted by external Python collector services (not the Django app itself). These services use `jTookkit.jLogging` which routes logs through the OTEL Collector to Splunk.

Aggregations per collector component per return code over last 24 hours:

| Column | Source | Notes |
|---|---|---|
| Component | `component` field | e.g. `emporia-collector`, `enphase-collector` |
| Return Code | `return_code` field | HTTP-style; 200 = success, 4xx/5xx = failure |
| Count | SPL `count` | Number of collection cycles |
| Avg Duration | SPL `avg(duration)` | Seconds per cycle |
| Last Run | `max(timestamp)` | Displayed in EST |
| Stale | Derived | Last run > 10 min ago (enphase: > 4 hours) |
| Bad Code | Derived | `return_code >= 400` |

Fields are embedded in Splunk's `_raw` as Python dict repr (single-quoted keys), so the SPL query uses `rex` extractions with `coalesce()` fallback.

**Collector components:**

| Component | Description |
|---|---|
| `enphase-collector` | Solar panel production (Enphase API) |
| `emporia-collector` | Home energy usage (Emporia Vue) |
| `network-collector` | Network traffic metrics |
| `synology-collector` | NAS health and storage (Synology DSM) |
| `weather-collector` | Local weather data |

---

## OTEL Collector Infrastructure

**K8s resource:** `OpenTelemetryCollector/otel-collector` in `monitoring` namespace  
**Image:** `otel/opentelemetry-collector-contrib:0.96.0`

### Receivers

| Protocol | Endpoint | Use |
|---|---|---|
| OTLP gRPC | `0.0.0.0:4317` | External collector services (jTookkit) |
| OTLP HTTP | `0.0.0.0:4318` | Django app (`OTLP_ENDPOINT`) |

### Pipelines

| Pipeline | Exporter |
|---|---|
| `logs` | Splunk HEC → index `otel_logging` |
| `traces` | OTLP → Tempo |
| `metrics` | Prometheus (scrape port `8890`) |

### Splunk HEC Config

```
Endpoint:   https://splunk.splunk.svc.cluster.local:8088/services/collector
Index:      otel_logging
Sourcetype: otel:logs
TLS:        insecure_skip_verify (internal cluster)
```
