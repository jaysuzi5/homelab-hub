# OTEL Logging — Homelab Hub

## Overview

Homelab Hub displays observability data collected from a set of external Python collector services. The collectors use a custom structured logging library (`jTookkit.jLogging`) whose output is routed through an OpenTelemetry Collector, stored in Splunk, and surfaced on the dashboard's **Collector Job Summary** tab.

The Django application itself does **not** have any OpenTelemetry instrumentation. Page-level observability recommendations are in the final section.

---

## Architecture

```
External Collectors (Python)
  └── jTookkit.jLogging (Python stdlib logging)
        └── OTEL Python SDK bridge (OTLPLogExporter)
              └── OpenTelemetry Collector (otel-collector, monitoring namespace)
                    ├── Logs  → Splunk HEC → index: otel_logging
                    ├── Traces → Tempo (tempo.monitoring.svc.cluster.local:4317)
                    └── Metrics → Prometheus (port 8890)

Homelab Hub (Django)
  └── dashboard/services/splunk.py
        └── Queries Splunk index=otel_logging via web proxy (port 8000)
              └── Renders "Collector Job Summary: Last 24 hours" tab
```

---

## External Collector Logging (jTookkit.jLogging)

### Library

**Package:** `j-utilities-toolkit` (`jTookkit.jLogging`)  
**Transport:** Python stdlib `logging` module → OTEL SDK log bridge → OTLP gRPC (port 4317)

### Event Types

All collectors emit four structured event types:

| EventType | When Emitted | Required Fields |
|---|---|---|
| `transaction_start` | Beginning of each collection cycle | `transaction_id`, `timestamp` |
| `transaction_end` | End of each collection cycle | `transaction_id`, `return_code`, `duration`, `timestamp` |
| `span_start` | Beginning of a sub-operation (e.g., API call, DB insert) | `transaction_id`, `source_transaction_id`, `source_component` |
| `span_end` | End of a sub-operation | `transaction_id`, `source_transaction_id`, `return_code`, `duration` |

A `message` event type also exists for freeform log lines within a transaction.

### Log Levels

| Level | Condition |
|---|---|
| `INFO` | All transaction/span start and end events; standard `message()` calls |
| `ERROR` | `message()` called with `exception=` or `error=True` |
| `DEBUG` | `message()` called with `debug=True`; also requires `LOG_LEVEL=DEBUG` env var |

Default level is `INFO` (controlled by `LOG_LEVEL` environment variable).

### Log Format

Events are structured Python dicts serialized to the log body. A `transaction_end` event looks like:

```python
{
    "level": "INFO",
    "event_type": "transaction_end",
    "timestamp": "2026-05-06T11:40:22.123456+00:00",
    "transaction_id": "a1b2c3d4-...",
    "component": "enphase-collector",
    "component_type": "python",
    "return_code": 200,
    "duration": 0.842
}
```

A `message` event with error context:

```python
{
    "level": "ERROR",
    "event_type": "message",
    "timestamp": "...",
    "transaction_id": "...",
    "component": "enphase-collector",
    "component_type": "python",
    "message": "Exception inserting Enphase data locally",
    "data": {
        "exception": "ConnectionError(...)",
        "status_code": 500,
        "response.text": "..."
    },
    "stack_trace": "Traceback (most recent call last):\n  ..."
}
```

In Splunk, these dicts land in the `_raw` field as Python repr strings (single-quoted keys). The dashboard SPL query uses `rex` field extractions to parse them.

### Collector Components

| Component Name | Description |
|---|---|
| `enphase-collector` | Solar panel production data from Enphase API |
| `emporia-collector` | Home energy usage from Emporia Vue |
| `network-collector` | Network traffic metrics |
| `synology-collector` | NAS health and storage metrics from Synology |
| `weather-collector` | Local weather data |

---

## OpenTelemetry Collector Configuration

**K8s resource:** `OpenTelemetryCollector/otel-collector` in `monitoring` namespace  
**Image:** `otel/opentelemetry-collector-contrib:0.96.0`

### Receivers

| Protocol | Endpoint | Use |
|---|---|---|
| OTLP gRPC | `0.0.0.0:4317` | Collector logs and traces |
| OTLP HTTP | `0.0.0.0:4318` | Alternative HTTP transport |

### Pipelines

| Pipeline | Receiver | Processor | Exporter |
|---|---|---|---|
| `logs` | otlp | batch | splunk_hec, debug |
| `traces` | otlp | batch | otlp → Tempo |
| `metrics` | otlp | batch | prometheus |

### Log Exporter (Splunk HEC)

```
Endpoint:   https://splunk.splunk.svc.cluster.local:8088/services/collector
Index:      otel_logging
Sourcetype: otel:logs
Source:     otel
TLS:        insecure_skip_verify (internal cluster)
```

### Collector Self-Telemetry

The OTEL Collector itself emits internal metrics and logs at:
- Internal logs: `debug` level (stdout)
- Internal metrics: `detailed` level on port `8889`

---

## Dashboard Display — Collector Job Summary

**Location:** `dashboard/services/splunk.py` → `splunk_collector_summary()`  
**Tab:** "Collector Job Summary: Last 24 hours" on `homelab-hub.com/`

### What Is Displayed

Only `transaction_end` events are queried and surfaced. Per-component, per-return-code aggregations over the last 24 hours:

| Column | Source Field | Description |
|---|---|---|
| Component | `component` | Collector name (e.g., `emporia-collector`) |
| Return Code | `return_code` | HTTP-style status code (200 = success, 4xx/5xx = failure) |
| Count | SPL `count` | Number of collection cycles |
| Avg Duration | SPL `avg(duration)` | Average seconds per cycle |
| Last Run | `max(timestamp)` | Most recent `transaction_end` timestamp (displayed in EST) |
| Stale | Derived | `true` if last run > 10 min ago (enphase: > 4 hours) |
| Bad Code | Derived | `true` if `return_code >= 400` |

### SPL Query Summary

Fields `component`, `return_code`, `duration`, `timestamp`, and `event_type` are not top-level Splunk fields — they are embedded in `_raw` as a Python dict repr. The query uses `rex` extractions to pull them out, with `coalesce()` to prefer any already-indexed fields:

```spl
search index="otel_logging"
| rex field=_raw "['\"]event_type['\"]\s*:\s*['\"](?<_event_type>[^'\"]+)['\"]"
| rex field=_raw "['\"]component['\"]\s*:\s*['\"](?<_component>[^'\"]+)['\"]"
| ...
| where event_type="transaction_end" AND match(component, ".*-collector.*")
| stats count, avg(duration) as duration, max(timestamp) as last_run by component, return_code
```

### Staleness Thresholds

| Collector | Stale After |
|---|---|
| All collectors (default) | 10 minutes |
| `enphase-collector` | 4 hours (runs less frequently) |

---

## Page-Level OTEL — Current State

The homelab-hub Django application has **no OpenTelemetry instrumentation**. There are no:
- OTEL SDK packages installed
- OTEL middleware in `settings.py`
- Distributed traces for page requests
- Structured request/response logging
- Dashboard page view metrics

Errors and debug output are emitted via bare `print()` statements to stdout only.

---

## Recommendations: Adding Page-Level OTEL

### 1. Install OTEL Packages

Add to `pyproject.toml`:

```toml
"opentelemetry-api>=1.24.0",
"opentelemetry-sdk>=1.24.0",
"opentelemetry-exporter-otlp-proto-grpc>=1.24.0",
"opentelemetry-instrumentation-django>=0.45b0",
"opentelemetry-instrumentation-requests>=0.45b0",
"opentelemetry-instrumentation-logging>=0.45b0",
```

### 2. Initialize OTEL in Django Settings

Add to `hub/settings.py` (or a dedicated `hub/otel.py` imported at startup):

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

resource = Resource.create({"service.name": "homelab-hub", "service.version": "1.0"})
provider = TracerProvider(resource=resource)
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(
        endpoint="http://otel-collector.monitoring.svc.cluster.local:4317"
    ))
)
trace.set_tracer_provider(provider)
```

### 3. Auto-Instrument Django and Requests

```python
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

DjangoInstrumentor().instrument()
RequestsInstrumentor().instrument()
```

This automatically creates spans for:
- Every incoming HTTP request to the Django app (URL, method, status, duration)
- Every outbound `requests` call made by the service layer (API calls to Splunk, K8s, weather, etc.)

### 4. Structured Logging via jTookkit.jLogging

Since `jTookkit.jLogging` is already installed but unused in the Django app, it could instrument dashboard page loads the same way collectors do:

```python
from jTookkit.jLogging import Logger, LoggingInfo, EventType

_logging_info = LoggingInfo(component="homelab-hub", component_type="django")
_logger = Logger(_logging_info)

def home(request):
    txn = _logger.transaction_event(EventType.TRANSACTION_START)
    try:
        # ... data collection ...
        _logger.transaction_event(EventType.TRANSACTION_END, transaction=txn, return_code=200)
    except Exception as e:
        _logger.message(transaction=txn, message="Dashboard load failed", exception=e, error=True)
        _logger.transaction_event(EventType.TRANSACTION_END, transaction=txn, return_code=500)
```

This would make `homelab-hub` appear as a component in the existing Collector Job Summary display.

### 5. What Would Be Captured at Each Level

| Signal | Level | What It Covers |
|---|---|---|
| **Traces** | Span per request | URL, user, response time, downstream service calls (Splunk, K8s APIs, weather, etc.) |
| **Logs / INFO** | Per page load | `transaction_start` and `transaction_end` for `home()` and `k8s()` views |
| **Logs / ERROR** | On exception | Failed service calls, unhandled exceptions, partial data loads |
| **Logs / DEBUG** | Verbose | Individual service call durations, raw API responses (only when `LOG_LEVEL=DEBUG`) |
| **Metrics** | Aggregated | Request count, error rate, p95 latency per endpoint (auto from DjangoInstrumentor) |

### 6. Splunk Query Extension

With page-level jTookkit logging in place, the existing `splunk_collector_summary()` query would automatically include `homelab-hub` as a row in the Collector Job Summary tab, since it already filters on `match(component, ".*-collector.*")`. That pattern would need updating to also include `homelab-hub`:

```spl
| where event_type="transaction_end" AND (match(component, ".*-collector.*") OR component="homelab-hub")
```

Or broaden to all `transaction_end` events regardless of component:

```spl
| where event_type="transaction_end"
```

### 7. Add OTEL Env Var to K8s Deployment

```yaml
env:
  - name: OTEL_EXPORTER_OTLP_ENDPOINT
    value: "http://otel-collector.monitoring.svc.cluster.local:4317"
  - name: OTEL_SERVICE_NAME
    value: "homelab-hub"
  - name: OTEL_TRACES_EXPORTER
    value: "otlp"
  - name: OTEL_LOGS_EXPORTER
    value: "otlp"
```
