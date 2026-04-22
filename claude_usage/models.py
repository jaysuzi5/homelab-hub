from django.db import models


class ClaudeSession(models.Model):
    session_id = models.CharField(max_length=64, primary_key=True)
    project_path = models.CharField(max_length=512)
    project_name = models.CharField(max_length=255)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_min = models.FloatField(null=True, blank=True)
    model = models.CharField(max_length=64, blank=True)
    tool_call_count = models.IntegerField(default=0)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.project_name} @ {self.started_at:%Y-%m-%d %H:%M}"


class ClaudeDailyUsage(models.Model):
    date = models.DateField()
    model = models.CharField(max_length=64)
    total_tokens = models.BigIntegerField(default=0)
    api_equiv_cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    tool_call_count = models.IntegerField(default=0)
    session_count = models.IntegerField(default=0)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("date", "model")]
        ordering = ["-date", "model"]

    def __str__(self):
        return f"{self.date} {self.model}"


class ClaudeUsageSnapshot(models.Model):
    fetched_at = models.DateTimeField(auto_now_add=True)
    session_pct = models.FloatField(null=True, blank=True)
    session_resets_at = models.DateTimeField(null=True, blank=True)
    weekly_pct = models.FloatField(null=True, blank=True)
    weekly_resets_at = models.DateTimeField(null=True, blank=True)
    extra_usage_enabled = models.BooleanField(default=False)
    extra_usage_credits_used = models.FloatField(default=0)

    class Meta:
        ordering = ["-fetched_at"]
        get_latest_by = "fetched_at"

    def __str__(self):
        return f"Snapshot {self.fetched_at:%Y-%m-%d %H:%M} weekly={self.weekly_pct}%"


class ClaudeToolCount(models.Model):
    date = models.DateField()
    tool_name = models.CharField(max_length=64)
    count = models.IntegerField(default=0)

    class Meta:
        unique_together = [("date", "tool_name")]
        ordering = ["-date", "tool_name"]

    def __str__(self):
        return f"{self.date} {self.tool_name}: {self.count}"


