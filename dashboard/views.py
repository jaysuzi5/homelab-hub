import asyncio
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import render
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.auth.decorators import login_required
from dashboard.services.k8s import collect_k8s_metrics_summary, collect_k8s_metrics_detailed
from dashboard.services.darts import collect_dart_summary
from dashboard.services.synology import collect_synology_summary
from dashboard.services.network import collect_network_summary
from dashboard.services.emporia import collect_emporia_summary, collect_emporia_daily_summary
from dashboard.services.enphase import collect_enhase_summary
from dashboard.services.splunk import splunk_collector_summary
from dashboard.services.weather import collect_weather_summary

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