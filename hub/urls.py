from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from dashboard.views import home, k8s, energy, networking, todo_tasks, todo_task_complete, otel_overview, otel_endpoint_detail, otel_transaction_detail, otel_logging_overview, otel_logging_transactions, otel_trace_overview, otel_trace_detail_view, otel_metrics_overview, otel_metrics_query_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("k8s", k8s, name="k8s"),
    path("energy/", energy, name="energy"),
    path("networking/", networking, name="networking"),
    path("accounts/", include("allauth.urls")),
    path('financial/', include('financial.urls')),
    path('hobbies/', include('hobbies.urls')),
    path('health/', include('health.urls')),
    path('claude-usage/', include('claude_usage.urls')),
    path('otel/', otel_overview, name='otel_overview'),
    path('otel/logging/', otel_logging_overview, name='otel_logging_overview'),
    path('otel/logging/transactions/', otel_logging_transactions, name='otel_logging_transactions'),
    path('otel/trace/', otel_trace_overview, name='otel_trace_overview'),
    path('otel/trace/detail/', otel_trace_detail_view, name='otel_trace_detail'),
    path('otel/metrics/', otel_metrics_overview, name='otel_metrics_overview'),
    path('otel/metrics/query/', otel_metrics_query_view, name='otel_metrics_query'),
    path('otel/endpoint-detail/', otel_endpoint_detail, name='otel_endpoint_detail'),
    path('otel/transaction-detail/', otel_transaction_detail, name='otel_transaction_detail'),
    path('todo/tasks/', todo_tasks, name='todo_tasks'),
    path('todo/tasks/<int:task_id>/complete/', todo_task_complete, name='todo_task_complete'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
