import json
import requests as http_requests
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from dashboard.services.k8s import collect_k8s_metrics_summary, collect_k8s_metrics_detailed
from dashboard.services.synology import collect_synology_summary
from dashboard.services.network import collect_network_summary, collect_network_monthly_summary
from dashboard.services.emporia import collect_emporia_summary, collect_emporia_daily_summary, collect_emporia_monthly_summary, collect_emporia_monthly_category_summary
from dashboard.services.enphase import collect_enhase_summary
from dashboard.services.splunk import splunk_collector_summary, otel_response_summary, otel_service_status_summary, otel_endpoint_summary, otel_transaction_list, otel_recent_transactions, otel_summary, otel_filtered_transactions
from dashboard.services.tempo import tempo_services, tempo_recent_traces, tempo_trace_detail
from dashboard.services.prometheus_svc import prom_instant_query, prom_range_query
from dashboard.services.weather import collect_weather_summary
from dashboard.services.aws_billing import collect_aws_billing_summary
from dashboard.services.backup_status import collect_backup_status_summary
from dashboard.services.status_overview import collect_status_overview
from dashboard.services.chatbot import answer_question
from claude_usage.services import collect_claude_dashboard_summary
from monitoring.services import collect_host_status
from config.utils import get_config
from datetime import datetime
from opentelemetry import trace as otel_trace

_tracer = otel_trace.get_tracer("homelab-hub.dashboard")

_TODO_BASE = 'https://todo.jaycurtis.org/api/v1'
_TODO_LIST_ID = 3

def _todo_headers():
    token = get_config('TODO_API_TOKEN', '')
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

@login_required
def home(request):
    request.otel_page_summary = {"page": "home"}
    return render(request, "dashboard/home.html", {})


@login_required
def card_k8s(request):
    with _tracer.start_as_current_span("card.k8s"):
        pods_status, nodes, total_pods, cluster_cpu, cluster_mem = collect_k8s_metrics_summary()
    return render(request, "dashboard/partials/_card_k8s.html", {
        "pods": pods_status, "nodes": nodes, "total_pods": total_pods,
        "cluster_cpu_percent": cluster_cpu, "cluster_mem_percent": cluster_mem,
    })


@login_required
def card_synology(request):
    with _tracer.start_as_current_span("card.synology"):
        synology_metrics = collect_synology_summary()
    return render(request, "dashboard/partials/_card_synology.html", {
        "synology_metrics": synology_metrics,
    })


@login_required
def card_claude(request):
    with _tracer.start_as_current_span("card.claude"):
        claude_summary = collect_claude_dashboard_summary()
    return render(request, "dashboard/partials/_card_claude.html", {
        "claude_summary": claude_summary,
    })


@login_required
def card_network(request):
    with _tracer.start_as_current_span("card.network"):
        network_metrics = collect_network_summary() or {
            'tcp_latency': 0, 'internet_ping': 0,
            'internet_download': 0, 'internet_upload': 0, 'online': False,
        }
        host_status = collect_host_status()
    return render(request, "dashboard/partials/_card_network.html", {
        "network_metrics": network_metrics, "host_status": host_status,
    })


@login_required
def card_emporia_chart(request):
    with _tracer.start_as_current_span("card.emporia_chart"):
        emporia_metrics = collect_emporia_summary()
        enhase_summary = collect_enhase_summary()
    return render(request, "dashboard/partials/_card_emporia_chart.html", {
        "emporia_metrics": json.dumps(emporia_metrics, cls=DjangoJSONEncoder),
        "enphase_metrics": enhase_summary,
    })


@login_required
def card_emporia_daily(request):
    with _tracer.start_as_current_span("card.emporia_daily"):
        selected_day = request.GET.get('day', datetime.now().strftime('%Y-%m-%d'))
        emporia_daily_summary = collect_emporia_daily_summary(selected_day)
    return render(request, "dashboard/partials/_card_emporia_daily.html", {
        "emporia_daily_summary": emporia_daily_summary,
    })


@login_required
def card_splunk(request):
    with _tracer.start_as_current_span("card.splunk"):
        splunk_summary = splunk_collector_summary()
    return render(request, "dashboard/partials/_card_splunk.html", {
        "splunk_summary": splunk_summary,
    })


@login_required
def card_weather(request):
    with _tracer.start_as_current_span("card.weather"):
        weather_summary = collect_weather_summary()
    return render(request, "dashboard/partials/_card_weather.html", {
        "weather_summary": weather_summary,
    })


@login_required
def card_aws_billing(request):
    with _tracer.start_as_current_span("card.aws_billing"):
        billing = collect_aws_billing_summary()
    return render(request, "dashboard/partials/_card_aws_billing.html", {
        "billing": billing,
    })


@login_required
def card_status(request):
    with _tracer.start_as_current_span("card.status"):
        status = collect_status_overview()
    return render(request, "dashboard/partials/_card_status.html", {
        "status": status,
    })


@login_required
@require_http_methods(["POST"])
def status_chat(request):
    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"error": "Invalid request."}, status=400)
    history = payload.get("messages", [])
    if not isinstance(history, list) or not history:
        return JsonResponse({"error": "No message provided."}, status=400)
    with _tracer.start_as_current_span("status.chat"):
        result = answer_question(history)
    return JsonResponse(result)


@login_required
def telemetry_agent_calls(request):
    from dashboard.models import AgentCall
    q = (request.GET.get("q") or "").strip()
    only_errors = request.GET.get("errors") == "1"
    source = (request.GET.get("source") or "").strip()
    calls = AgentCall.objects.all()
    if q:
        calls = calls.filter(question__icontains=q)
    if only_errors:
        calls = calls.exclude(error="")
    if source:
        calls = calls.filter(source=source)
    calls = list(calls[:200])
    total = AgentCall.objects.count()
    error_count = AgentCall.objects.exclude(error="").count()
    sources = list(AgentCall.objects.order_by("source").values_list("source", flat=True).distinct())
    return render(request, "dashboard/telemetry_agent_calls.html", {
        "calls": calls,
        "q": q,
        "only_errors": only_errors,
        "source": source,
        "sources": sources,
        "total": total,
        "error_count": error_count,
    })


@login_required
def card_backup(request):
    with _tracer.start_as_current_span("card.backup"):
        backup = collect_backup_status_summary()
    return render(request, "dashboard/partials/_card_backup.html", {
        "backup": backup,
    })


@login_required
@require_http_methods(["POST"])
def card_aws_billing_refresh(request):
    with _tracer.start_as_current_span("card.aws_billing.refresh"):
        billing = collect_aws_billing_summary(force=True)
    return render(request, "dashboard/partials/_card_aws_billing.html", {
        "billing": billing,
    })

@login_required
def k8s(request):
    data = collect_k8s_metrics_detailed()
    request.otel_page_summary = {
        "page": "k8s",
        "pod_count": len(data.get("pods", [])) if data else 0,
        "node_count": len(data.get("nodes", [])) if data else 0,
    }
    return render(request, "dashboard/k8s.html", data)

@login_required
def energy(request):
    # Get month/year parameters for monthly chart, default to current month
    current_date = datetime.now()
    selected_month = int(request.GET.get('month', current_date.month))
    selected_year = int(request.GET.get('year', current_date.year))

    # Get day parameter for daily summary, default to current date
    selected_day = request.GET.get('day', current_date.strftime('%Y-%m-%d'))

    # Collect monthly metrics
    emporia_monthly_metrics = collect_emporia_monthly_summary(selected_year, selected_month)

    # Collect monthly category summary
    emporia_monthly_category_summary = collect_emporia_monthly_category_summary(selected_year, selected_month)

    # Collect daily summary
    emporia_daily_summary = collect_emporia_daily_summary(selected_day)

    context = {
        'selected_month': selected_month,
        'selected_year': selected_year,
        'selected_day': selected_day,
        'current_date': current_date.strftime('%Y-%m-%d'),
        'emporia_monthly_metrics': json.dumps(emporia_monthly_metrics, cls=DjangoJSONEncoder),
        'emporia_monthly_category_summary': emporia_monthly_category_summary,
        'emporia_daily_summary': emporia_daily_summary,
    }
    request.otel_page_summary = {
        "page": "energy",
        "selected_month": selected_month,
        "selected_year": selected_year,
        "selected_day": selected_day,
        "daily_usage_kwh": next((item["usage"] for item in emporia_daily_summary if item.get("name") == "Electricity Monitor"), None) if emporia_daily_summary else None,
    }
    return render(request, "dashboard/energy.html", context)

@login_required
def networking(request):
    # Get month/year parameters, default to current month
    current_date = datetime.now()
    selected_month = int(request.GET.get('month', current_date.month))
    selected_year = int(request.GET.get('year', current_date.year))

    # Collect current network summary
    network_metrics = collect_network_summary()
    if network_metrics is None:
        network_metrics = {
            'tcp_latency': 0,
            'internet_ping': 0,
            'internet_download': 0,
            'internet_upload': 0,
            'online': False
        }

    # Collect monthly historical metrics
    network_monthly_metrics = collect_network_monthly_summary(selected_year, selected_month)

    context = {
        'selected_month': selected_month,
        'selected_year': selected_year,
        'network_metrics': network_metrics,
        'network_monthly_metrics': json.dumps(network_monthly_metrics, cls=DjangoJSONEncoder),
    }
    request.otel_page_summary = {
        "page": "networking",
        "selected_month": selected_month,
        "selected_year": selected_year,
        "online": network_metrics.get("online"),
        "internet_download": network_metrics.get("internet_download"),
        "internet_upload": network_metrics.get("internet_upload"),
    }
    return render(request, "dashboard/networking.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def todo_tasks(request):
    try:
        if request.method == 'GET':
            resp = http_requests.get(
                f'{_TODO_BASE}/lists/{_TODO_LIST_ID}/tasks/',
                headers=_todo_headers(), timeout=5,
            )
            return JsonResponse(resp.json(), safe=False, status=resp.status_code)
        data = json.loads(request.body)
        resp = http_requests.post(
            f'{_TODO_BASE}/lists/{_TODO_LIST_ID}/tasks/',
            headers=_todo_headers(), json=data, timeout=5,
        )
        return JsonResponse(resp.json(), status=resp.status_code)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


@login_required
@require_http_methods(["POST"])
def todo_task_complete(request, task_id):
    try:
        resp = http_requests.post(
            f'{_TODO_BASE}/tasks/{task_id}/complete/',
            headers=_todo_headers(), timeout=5,
        )
        return JsonResponse(resp.json(), status=resp.status_code)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


_OTEL_TIME_RANGES = [
    ("-1h",  "Last 1 Hour"),
    ("-6h",  "Last 6 Hours"),
    ("-24h", "Last 24 Hours"),
    ("-7d",  "Last 7 Days"),
    ("-30d", "Last 30 Days"),
]

@login_required
def otel_overview(request):
    earliest = request.GET.get("earliest", "-1h")
    result = otel_service_status_summary(earliest)
    # Pre-process rows into lists for template (avoids custom template filter for dict key lookup)
    status_columns = result.get("status_columns", [])
    if result.get("success"):
        result["rows"] = [
            {
                "service": row.get("service", ""),
                "cells": [{"col": col, "count": row.get(col)} for col in status_columns],
            }
            for row in result.get("data", [])
        ]
    request.otel_page_summary = {
        "page": "otel",
        "earliest": earliest,
        "row_count": len(result.get("data", [])),
        "success": result.get("success"),
    }
    return render(request, "dashboard/otel.html", {
        "result": result,
        "earliest": earliest,
        "time_ranges": _OTEL_TIME_RANGES,
    })


@login_required
def otel_logging_overview(request):
    earliest = request.GET.get("earliest", "-1h")
    result = otel_summary(earliest)
    request.otel_page_summary = {"page": "otel_logging", "earliest": earliest,
                                  "row_count": len(result.get("data", [])), "success": result.get("success")}
    return render(request, "dashboard/otel_logging.html", {
        "result": result,
        "earliest": earliest,
        "time_ranges": _OTEL_TIME_RANGES,
    })


@login_required
@require_http_methods(["GET"])
def otel_logging_transactions(request):
    service = request.GET.get("service", "")
    endpoint = request.GET.get("endpoint", "")
    method = request.GET.get("method", "")
    status = request.GET.get("status", "")
    status_prefix = request.GET.get("status_prefix", "")
    earliest = request.GET.get("earliest", "-1h")
    return JsonResponse(otel_filtered_transactions(service, endpoint, method, status, status_prefix, earliest))


@login_required
@require_http_methods(["GET"])
def otel_endpoint_detail(request):
    service = request.GET.get("service", "")
    earliest = request.GET.get("earliest", "-1h")
    if not service:
        return JsonResponse({"success": False, "message": "service required"})
    return JsonResponse(otel_endpoint_summary(service, earliest))


@login_required
@require_http_methods(["GET"])
def otel_transaction_detail(request):
    service = request.GET.get("service", "")
    endpoint = request.GET.get("endpoint", "")
    method = request.GET.get("method", "")
    status = request.GET.get("status", "")
    earliest = request.GET.get("earliest", "-1h")
    if not all([service, endpoint, method, status]):
        return JsonResponse({"success": False, "message": "service, endpoint, method, status all required"})
    return JsonResponse(otel_transaction_list(service, endpoint, method, status, earliest))


@login_required
def otel_trace_overview(request):
    earliest = request.GET.get("earliest", "-1h")
    service = request.GET.get("service", "")
    root_span = request.GET.get("root_span", "")
    focus_trace_id = request.GET.get("trace_id", "")

    services_result = tempo_services()

    focus_trace_json = "null"
    if focus_trace_id:
        detail = tempo_trace_detail(focus_trace_id)
        if detail.get("success"):
            focus_trace_json = json.dumps(detail.get("data"), cls=DjangoJSONEncoder)
            if not service:
                for batch in detail.get("data", {}).get("batches", []):
                    for attr in batch.get("resource", {}).get("attributes", []):
                        if attr.get("key") == "service.name":
                            service = attr.get("value", {}).get("stringValue", "") or ""
                            break
                    if service:
                        break

    traces_result = tempo_recent_traces(service=service, earliest=earliest, limit=500, root_span=root_span)

    # Build root span list from full result, then filter
    all_traces = traces_result.get("data", [])
    tempo_metrics = traces_result.get("metrics", {})
    root_spans = sorted({t.get("rootTraceName", "") for t in all_traces if t.get("rootTraceName")})
    if root_span and root_span not in root_spans:
        root_span = ""
    filtered_traces = [t for t in all_traces if not root_span or t.get("rootTraceName") == root_span]

    request.otel_page_summary = {"page": "otel_trace", "earliest": earliest}
    return render(request, "dashboard/otel_trace.html", {
        "services": services_result.get("data", []),
        "traces": {**traces_result, "data": filtered_traces},
        "selected_service": service,
        "root_spans": root_spans,
        "selected_root_span": root_span,
        "earliest": earliest,
        "time_ranges": _OTEL_TIME_RANGES,
        "focus_trace_id": focus_trace_id,
        "focus_trace_json": focus_trace_json,
        "tempo_fetched": len(all_traces),
        "tempo_inspected": tempo_metrics.get("inspectedTraces", 0),
        "tempo_shown": len(filtered_traces),
    })


@login_required
@require_http_methods(["GET"])
def otel_trace_detail_view(request):
    trace_id = request.GET.get("trace_id", "")
    if not trace_id:
        return JsonResponse({"success": False, "message": "trace_id required"})
    return JsonResponse(tempo_trace_detail(trace_id))


@login_required
def otel_metrics_overview(request):
    earliest = request.GET.get("earliest", "-1h")
    request.otel_page_summary = {"page": "otel_metrics", "earliest": earliest}
    return render(request, "dashboard/otel_metrics.html", {
        "earliest": earliest,
        "time_ranges": _OTEL_TIME_RANGES,
    })


@login_required
@require_http_methods(["GET"])
def otel_metrics_query_view(request):
    query = request.GET.get("query", "")
    earliest = request.GET.get("earliest", "-1h")
    query_type = request.GET.get("type", "instant")
    if not query:
        return JsonResponse({"success": False, "message": "query required"})
    if query_type == "range":
        return JsonResponse(prom_range_query(query, earliest))
    return JsonResponse(prom_instant_query(query))