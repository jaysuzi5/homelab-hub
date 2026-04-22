import platform
import re
import subprocess
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from monitoring.models import HostPingResult, MonitoredHost

IS_MACOS = platform.system() == "Darwin"
PING_BIN = "/sbin/ping" if IS_MACOS else "/bin/ping"


class Command(BaseCommand):
    help = "Ping all active monitored hosts and store results"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show results without writing to DB')
        parser.add_argument('--timeout', type=int, default=2, help='Ping wait timeout in seconds (default: 2)')
        parser.add_argument('--count', type=int, default=3, help='Number of ping packets (default: 3)')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        timeout = options['timeout']
        count = options['count']

        hosts = list(MonitoredHost.objects.filter(is_active=True))
        if not hosts:
            self.stdout.write(self.style.WARNING("No active hosts configured."))
            return

        now = timezone.now()
        saved = 0

        for host in hosts:
            is_up, latency_ms = self._ping(host.address, count, timeout)
            status_label = self.style.SUCCESS("UP") if is_up else self.style.ERROR("DOWN")
            latency_str = f"{latency_ms:.1f} ms" if latency_ms is not None else "N/A"
            self.stdout.write(f"  {host.name} ({host.address}): {status_label}  {latency_str}")

            if dry_run:
                continue

            HostPingResult.objects.create(
                host=host,
                checked_at=now,
                is_up=is_up,
                latency_ms=latency_ms,
            )
            saved += 1

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f"Saved {saved} ping results."))
            self._prune_old_results()

    def _ping(self, address, count, timeout):
        try:
            # macOS: -W is milliseconds; Linux: -W is seconds
            w_arg = str(timeout * 1000) if IS_MACOS else str(timeout)
            result = subprocess.run(
                [PING_BIN, '-c', str(count), '-W', w_arg, address],
                capture_output=True,
                text=True,
                timeout=timeout * count + 5,
            )
            if result.returncode == 0:
                # macOS: "round-trip min/avg/max/stddev = X/Y/Z/W ms"
                # Linux:  "rtt min/avg/max/mdev = X/Y/Z/W ms"
                match = re.search(
                    r'(?:rtt|round-trip) min/avg/max/(?:mdev|stddev) = [\d.]+/([\d.nan]+)/',
                    result.stdout,
                )
                if match and match.group(1) not in ('nan', ''):
                    latency = float(match.group(1))
                else:
                    latency = None
                return True, latency
            return False, None
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False, None

    def _prune_old_results(self):
        cutoff = timezone.now() - timedelta(days=7)
        deleted, _ = HostPingResult.objects.filter(checked_at__lt=cutoff).delete()
        if deleted:
            self.stdout.write(f"Pruned {deleted} results older than 7 days.")
