import ipaddress
from datetime import timedelta

from django.utils import timezone


def _sort_key(entry):
    # DOWN (is_up=False) and no-data (is_up=None) sort before UP
    up_order = 0 if not entry['is_up'] else 1
    try:
        ip_order = ipaddress.ip_address(entry['address'])
    except ValueError:
        ip_order = ipaddress.ip_address('0.0.0.0')
    return (up_order, ip_order)


def collect_host_status():
    try:
        from monitoring.models import MonitoredHost

        stale_cutoff = timezone.now() - timedelta(minutes=15)
        hosts = MonitoredHost.objects.filter(is_active=True).prefetch_related('ping_results')
        result = []

        for host in hosts:
            latest = host.ping_results.first()
            if latest:
                result.append({
                    'name': host.name,
                    'address': host.address,
                    'is_up': latest.is_up,
                    'latency_ms': latest.latency_ms,
                    'checked_at': latest.checked_at,
                    'stale': latest.checked_at < stale_cutoff,
                })
            else:
                result.append({
                    'name': host.name,
                    'address': host.address,
                    'is_up': None,
                    'latency_ms': None,
                    'checked_at': None,
                    'stale': True,
                })

        result.sort(key=_sort_key)
        return result
    except Exception as e:
        print(f"Error fetching host status: {e}")
        return []
