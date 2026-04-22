from django.contrib import admin
from .models import MonitoredHost, HostPingResult


@admin.register(MonitoredHost)
class MonitoredHostAdmin(admin.ModelAdmin):
    list_display = ['name', 'address', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'address']


@admin.register(HostPingResult)
class HostPingResultAdmin(admin.ModelAdmin):
    list_display = ['host', 'checked_at', 'is_up', 'latency_ms']
    list_filter = ['host', 'is_up']
    ordering = ['-checked_at']
    date_hierarchy = 'checked_at'
