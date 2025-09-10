from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from dashboard.services.k8s import collect_k8s_metrics_summary, collect_k8s_metrics_detailed
from dashboard.services.darts import collect_dart_summary
from dashboard.services.synology import collect_synology_metrics_summary
from dashboard.services.network import collect_network_summary

@login_required
def home(request):
    # Collect the data from the services
    dart_avg_scores_501, dart_avg_scores_score_training = collect_dart_summary()
    pods_status, nodes, total_pods, cluster_cpu, cluster_mem = collect_k8s_metrics_summary()
    synology_metrics = collect_synology_metrics_summary()
    network_metrics = collect_network_summary()
    
    context = {
        "dart_avg_scores_501": dart_avg_scores_501,
        "dart_avg_scores_score_training": dart_avg_scores_score_training,
        "pods": pods_status,
        "total_pods": total_pods,
        "nodes": nodes,
        "cluster_cpu_percent": cluster_cpu,
        "cluster_mem_percent": cluster_mem,
        "synology_metrics": synology_metrics,
        "network_metrics": network_metrics
    }

    return render(request, "dashboard/home.html", context)


@login_required
def k8s(request):
    data = collect_k8s_metrics_detailed()
    return render(request, "dashboard/k8s.html", data)