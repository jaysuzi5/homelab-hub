import asyncio
import json
import time
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import render
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.auth.decorators import login_required
from dashboard.services.k8s import collect_k8s_metrics_summary, collect_k8s_metrics_detailed
from dashboard.services.darts import collect_dart_summary
from dashboard.services.synology import collect_synology_metrics_summary
from dashboard.services.network import collect_network_summary
from dashboard.services.emporia import collect_emporia_summary, collect_emporia_daily_summary
from dashboard.services.enphase import collect_enhase_summary
from dashboard.services.splunk import collect_collector_summary
from dashboard.services.weather import collect_weather_summary

@login_required
async def home(request):
    async def timed_call(name, func):
        start = time.perf_counter()
        # Run sync function in a thread so it doesn’t block the event loop
        result = await asyncio.to_thread(func)
        elapsed = time.perf_counter() - start
        print(f"{name} took {elapsed:.2f} seconds")
        return result

    (
        (dart_avg_scores_501, dart_avg_scores_score_training),
        (pods_status, nodes, total_pods, cluster_cpu, cluster_mem),
        synology_metrics,
        network_metrics,
        emporia_metrics,
        emporia_daily_summary,
        enhase_summary,
        collector_summary,
        weather_summary,
    ) = await asyncio.gather(
        timed_call("collect_dart_summary", collect_dart_summary),
        timed_call("collect_k8s_metrics_summary", collect_k8s_metrics_summary),
        timed_call("collect_synology_metrics_summary", collect_synology_metrics_summary),
        timed_call("collect_network_summary", collect_network_summary),
        timed_call("collect_emporia_summary", collect_emporia_summary),
        timed_call("collect_emporia_daily_summary", collect_emporia_daily_summary),
        timed_call("collect_enhase_summary", collect_enhase_summary),
        timed_call("collect_collector_summary", collect_collector_summary),
        timed_call("collect_weather_summary", collect_weather_summary),
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
        "collector_summary": collector_summary,
        "weather_summary": weather_summary,
    }
    return render(request, "dashboard/home.html", context)

@login_required
def k8s(request):
    data = collect_k8s_metrics_detailed()
    return render(request, "dashboard/k8s.html", data)