import asyncio
import json
import requests as http_requests
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.auth.decorators import login_required
from dashboard.services.k8s import collect_k8s_metrics_summary, collect_k8s_metrics_detailed
from dashboard.services.synology import collect_synology_summary
from dashboard.services.network import collect_network_summary, collect_network_monthly_summary
from dashboard.services.emporia import collect_emporia_summary, collect_emporia_daily_summary, collect_emporia_monthly_summary, collect_emporia_monthly_category_summary
from dashboard.services.enphase import collect_enhase_summary
from dashboard.services.splunk import splunk_collector_summary, otel_response_summary, otel_service_status_summary, otel_endpoint_summary, otel_transaction_list, otel_recent_transactions, otel_summary, otel_filtered_transactions
from dashboard.services.weather import collect_weather_summary
from claude_usage.services import collect_claude_dashboard_summary
from monitoring.services import collect_host_status
from config.utils import get_config
from asgiref.sync import sync_to_async
from datetime import datetime

_TODO_BASE = 'https://todo.jaycurtis.org/api/v1'
_TODO_LIST_ID = 3

def _todo_headers():
    token = get_config('TODO_API_TOKEN', '')
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

@login_required
async def home(request):
    async def wrap(func):
        return func()  # call sync function inside small coroutine
    (
        (pods_status, nodes, total_pods, cluster_cpu, cluster_mem),
        synology_metrics,
        network_metrics,
        emporia_metrics,
        emporia_daily_summary,
        enhase_summary,
        splunk_summary,
        weather_summary,
        claude_summary,
        host_status,
    ) = await asyncio.gather(
        wrap(collect_k8s_metrics_summary),
        wrap(collect_synology_summary),
        wrap(collect_network_summary),
        wrap(collect_emporia_summary),
        wrap(collect_emporia_daily_summary),
        wrap(collect_enhase_summary),
        wrap(splunk_collector_summary),
        wrap(collect_weather_summary),
        sync_to_async(collect_claude_dashboard_summary)(),
        sync_to_async(collect_host_status)(),
    )

    context = {
        "pods": pods_status,
        "total_pods": total_pods,
        "nodes": nodes,
        "cluster_cpu_percent": cluster_cpu,
        "cluster_mem_percent": cluster_mem,
        "synology_metrics": synology_metrics,
        "network_metrics": network_metrics,
        "emporia_metrics": json.dumps(emporia_metrics, cls=DjangoJSONEncoder),
        "enphase_metrics": enhase_summary,
        "emporia_daily_summary": emporia_daily_summary,
        "splunk_summary": splunk_summary,
        "weather_summary": weather_summary,
        "claude_summary": claude_summary,
        "host_status": host_status,
    }
    request.otel_page_summary = {
        "page": "home",
        "total_pods": total_pods,
        "nodes": len(nodes) if nodes else 0,
        "cluster_cpu_percent": cluster_cpu,
        "cluster_mem_percent": cluster_mem,
        "online": network_metrics.get("online") if network_metrics else False,
    }
    return render(request, "dashboard/home.html", context)

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
def otel2_overview(request):
    earliest = request.GET.get("earliest", "-1h")
    result = otel_summary(earliest)
    request.otel_page_summary = {"page": "otel2", "earliest": earliest,
                                  "row_count": len(result.get("data", [])), "success": result.get("success")}
    return render(request, "dashboard/otel2.html", {
        "result": result,
        "earliest": earliest,
        "time_ranges": _OTEL_TIME_RANGES,
    })


@login_required
@require_http_methods(["GET"])
def otel2_transactions(request):
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