import asyncio
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import render
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.auth.decorators import login_required
from dashboard.services.k8s import collect_k8s_metrics_summary, collect_k8s_metrics_detailed
from dashboard.services.darts import collect_dart_summary
from dashboard.services.synology import collect_synology_summary
from dashboard.services.network import collect_network_summary, collect_network_monthly_summary
from dashboard.services.emporia import collect_emporia_summary, collect_emporia_daily_summary, collect_emporia_monthly_summary, collect_emporia_monthly_category_summary
from dashboard.services.enphase import collect_enhase_summary
from dashboard.services.splunk import splunk_collector_summary
from dashboard.services.weather import collect_weather_summary
from datetime import datetime

@login_required
async def home(request):
    async def wrap(func):
        return func()  # call sync function inside small coroutine
    (
        (dart_avg_scores_501, dart_avg_scores_score_training),
        (pods_status, nodes, total_pods, cluster_cpu, cluster_mem),
        synology_metrics,
        network_metrics,
        emporia_metrics,
        emporia_daily_summary,
        enhase_summary,
        splunk_summary,
        weather_summary,
    ) = await asyncio.gather(
        wrap(collect_dart_summary),
        wrap(collect_k8s_metrics_summary),
        wrap(collect_synology_summary),
        wrap(collect_network_summary),
        wrap(collect_emporia_summary),
        wrap(collect_emporia_daily_summary),
        wrap(collect_enhase_summary),
        wrap(splunk_collector_summary),
        wrap(collect_weather_summary),
    )

    context = {
        "dart_avg_scores_501": dart_avg_scores_501,
        "dart_avg_scores_score_training": dart_avg_scores_score_training,
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
    }
    return render(request, "dashboard/home.html", context)

@login_required
def k8s(request):
    data = collect_k8s_metrics_detailed()
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

    print(f"[VIEW DEBUG] Network monthly metrics count: {len(network_monthly_metrics)}")
    print(f"[VIEW DEBUG] Network monthly metrics sample: {network_monthly_metrics[:2] if network_monthly_metrics else 'Empty'}")

    context = {
        'selected_month': selected_month,
        'selected_year': selected_year,
        'network_metrics': network_metrics,
        'network_monthly_metrics': json.dumps(network_monthly_metrics, cls=DjangoJSONEncoder),
    }

    return render(request, "dashboard/networking.html", context)