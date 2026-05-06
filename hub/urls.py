from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from dashboard.views import home, k8s, energy, networking, todo_tasks, todo_task_complete, otel_overview, otel_endpoint_detail, otel_transaction_detail, otel2_overview

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
    path('otel2/', otel2_overview, name='otel2_overview'),
    path('otel/endpoint-detail/', otel_endpoint_detail, name='otel_endpoint_detail'),
    path('otel/transaction-detail/', otel_transaction_detail, name='otel_transaction_detail'),
    path('todo/tasks/', todo_tasks, name='todo_tasks'),
    path('todo/tasks/<int:task_id>/complete/', todo_task_complete, name='todo_task_complete'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
