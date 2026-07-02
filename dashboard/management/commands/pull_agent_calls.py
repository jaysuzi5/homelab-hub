import logging
import urllib3
import requests
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime
from dashboard.models import AgentCall
from config.utils import get_config

_log = logging.getLogger(__name__)

SOURCE = "money-tracker"


class Command(BaseCommand):
    help = "Pull agent call logs from the money-tracker app into AgentCall (read-only)."

    def handle(self, *args, **options):
        base_url = get_config("MONEY_TRACKER_AGENT_URL")
        token = get_config("MONEY_TRACKER_AGENT_TOKEN")
        if not base_url or not token:
            self.stderr.write("MONEY_TRACKER_AGENT_URL / MONEY_TRACKER_AGENT_TOKEN not configured")
            return

        params = {"limit": 500}
        latest = (
            AgentCall.objects.filter(source=SOURCE)
            .order_by("-created_at")
            .values_list("created_at", flat=True)
            .first()
        )
        if latest:
            params["since"] = latest.isoformat()

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        try:
            resp = requests.get(
                base_url,
                headers={"Authorization": f"Bearer {token}"},
                params=params,
                timeout=30,
                verify=False,
            )
            resp.raise_for_status()
            calls = resp.json().get("calls", [])
        except Exception as exc:
            _log.exception("pull_agent_calls: request failed")
            self.stderr.write(f"request failed: {exc}")
            return

        added = 0
        for call in calls:
            rid = call.get("id")
            if rid is None:
                continue
            created_at = parse_datetime(call.get("created_at") or "")
            _, created = AgentCall.objects.update_or_create(
                source=SOURCE,
                source_id=rid,
                defaults={
                    "question": call.get("question") or "",
                    "reply": call.get("reply") or "",
                    "error": call.get("error") or "",
                    "rounds": call.get("rounds") or 0,
                    "tool_calls": call.get("tool_calls") or [],
                    "duration_ms": call.get("duration_ms") or 0,
                },
            )
            # created_at has auto_now_add=True; bypass it with a direct update.
            if created_at:
                AgentCall.objects.filter(source=SOURCE, source_id=rid).update(created_at=created_at)
            if created:
                added += 1

        self.stdout.write(f"pull_agent_calls: {len(calls)} fetched, {added} added ({SOURCE})")
        _log.info("pull_agent_calls: %s fetched, %s added", len(calls), added)
