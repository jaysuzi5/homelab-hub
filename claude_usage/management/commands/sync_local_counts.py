"""
Management command: sync_local_counts

Reads ~/.claude/usage-counts/sessions.jsonl and events.jsonl produced by the
PostToolUse + Stop hooks, and upserts ClaudeSession and ClaudeDailyUsage records.

This is the forward-looking data source that replaces stats-cache.json for
sessions after the stats-cache stopped being updated.
"""
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand

from claude_usage.models import ClaudeDailyUsage, ClaudeSession, ClaudeToolCount

SESSIONS_FILE = Path.home() / ".claude/usage-counts/sessions.jsonl"
EVENTS_FILE = Path.home() / ".claude/usage-counts/events.jsonl"

# Model key used for hook-derived daily rows (no token data available)
HOOK_MODEL = "(local)"


class Command(BaseCommand):
    help = "Sync local hook-based session and tool call counts into the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be synced without writing to the database",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        sess_created, sess_updated = self._sync_sessions(dry_run)
        day_created, day_updated, tool_created, tool_updated = self._sync_daily_from_events(dry_run)

        self.stdout.write(
            self.style.SUCCESS(
                f"Sessions: {sess_created} created, {sess_updated} updated | "
                f"Daily (local): {day_created} created, {day_updated} updated | "
                f"Tool counts: {tool_created} created, {tool_updated} updated"
            )
        )

    def _sync_sessions(self, dry_run: bool):
        created = updated = 0

        if not SESSIONS_FILE.exists():
            return created, updated

        for line in SESSIONS_FILE.read_text().splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            session_id = rec.get("session_id", "").strip()
            if not session_id:
                continue

            started_at = _parse_dt(rec.get("started_at"))
            ended_at = _parse_dt(rec.get("ended_at"))

            if dry_run:
                self.stdout.write(
                    f"  [dry-run] session {session_id[:8]}... "
                    f"{rec.get('project_name')} "
                    f"duration={rec.get('duration_min')}min "
                    f"tools={rec.get('tool_calls')}"
                )
                continue

            obj, was_created = ClaudeSession.objects.update_or_create(
                session_id=session_id,
                defaults={
                    "project_path": rec.get("project_path", ""),
                    "project_name": rec.get("project_name", ""),
                    "started_at": started_at or _now(),
                    "ended_at": ended_at,
                    "duration_min": rec.get("duration_min"),
                    "tool_call_count": rec.get("tool_calls", 0),
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        return created, updated

    def _sync_daily_from_events(self, dry_run: bool):
        created = updated = tool_created = tool_updated = 0

        if not EVENTS_FILE.exists():
            return created, updated, tool_created, tool_updated

        by_date: dict[str, dict] = defaultdict(lambda: {"tool_calls": 0, "sessions": set()})
        by_date_tool: dict[tuple, int] = {}  # (date_str, tool_name) → count

        for line in EVENTS_FILE.read_text().splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            ts_ms = event.get("ts", 0)
            if not ts_ms:
                continue

            day = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).date().isoformat()
            tool = event.get("tool", "unknown")
            by_date[day]["tool_calls"] += 1
            sid = event.get("session_id", "")
            if sid:
                by_date[day]["sessions"].add(sid)
            key = (day, tool)
            by_date_tool[key] = by_date_tool.get(key, 0) + 1

        for date_str, agg in sorted(by_date.items()):
            tool_calls = agg["tool_calls"]
            session_count = len(agg["sessions"])

            if dry_run:
                self.stdout.write(
                    f"  [dry-run] {date_str} (local): {tool_calls} tool calls, "
                    f"{session_count} sessions"
                )
                continue

            obj, was_created = ClaudeDailyUsage.objects.update_or_create(
                date=date_str,
                model=HOOK_MODEL,
                defaults={
                    "total_tokens": 0,
                    "api_equiv_cost_usd": 0,
                    "tool_call_count": tool_calls,
                    "session_count": session_count,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        for (date_str, tool_name), count in sorted(by_date_tool.items()):
            if dry_run:
                self.stdout.write(f"  [dry-run] {date_str} {tool_name}: {count}")
                continue
            obj, was_created = ClaudeToolCount.objects.update_or_create(
                date=date_str,
                tool_name=tool_name,
                defaults={"count": count},
            )
            if was_created:
                tool_created += 1
            else:
                tool_updated += 1

        return created, updated, tool_created, tool_updated


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _now() -> datetime:
    return datetime.now(timezone.utc)
