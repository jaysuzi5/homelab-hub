from django.db import models


class AgentCall(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    source = models.CharField(max_length=64, default="homelab-hub", db_index=True)
    source_id = models.IntegerField(null=True, blank=True)
    question = models.TextField()
    reply = models.TextField(blank=True, default="")
    error = models.TextField(blank=True, default="")
    rounds = models.IntegerField(default=0)
    tool_calls = models.JSONField(default=list)
    duration_ms = models.IntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "source_id"],
                name="uniq_agentcall_source_sourceid",
            ),
        ]

    def __str__(self):
        return f"AgentCall({self.created_at:%Y-%m-%d %H:%M}) {self.question[:40]!r}"
