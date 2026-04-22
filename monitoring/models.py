from django.db import models


class MonitoredHost(models.Model):
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=255, help_text="IP address or hostname")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.address})"


class HostPingResult(models.Model):
    host = models.ForeignKey(MonitoredHost, on_delete=models.CASCADE, related_name='ping_results')
    checked_at = models.DateTimeField()
    is_up = models.BooleanField()
    latency_ms = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ['-checked_at']
        indexes = [models.Index(fields=['host', '-checked_at'])]

    def __str__(self):
        status = "UP" if self.is_up else "DOWN"
        return f"{self.host.name} {status} @ {self.checked_at:%Y-%m-%d %H:%M}"
