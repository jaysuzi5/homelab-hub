"""
Management command: sync_claude_usage

Reads ~/.claude/stats-cache.json and ~/.claude/sessions/*.json, then upserts
ClaudeDailyUsage and ClaudeSession records into the database.

Run locally (not in Kubernetes — stats-cache.json lives on the local Mac).
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone as dj_timezone

from claude_usage.models import ClaudeDailyUsage, ClaudeSession
from claude_usage.pricing import compute_blended_rates, cost_for_tokens


STATS_CACHE = Path.home() / ".claude" / "stats-cache.json"
SESSIONS_DIR = Path.home() / ".claude" / "sessions"


class Command(BaseCommand):
    help = "Sync Claude Code usage from stats-cache.json and session files into the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be synced without writing to the database",
        )
        parser.add_argument(
            "--stats-cache",
            default=str(STATS_CACHE),
            help=f"Path to stats-cache.json (default: {STATS_CACHE})",
        )
        parser.add_argument(
            "--sessions-dir",
            default=str(SESSIONS_DIR),
            help=f"Path to sessions directory (default: {SESSIONS_DIR})",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        stats_path = Path(options["stats_cache"])
        sessions_dir = Path(options["sessions_dir"])

        if not stats_path.exists():
            raise CommandError(f"stats-cache.json not found at {stats_path}")

        with open(stats_path) as f:
            stats = json.load(f)

        blended_rates = compute_blended_rates(stats.get("modelUsage", {}))
        self.stdout.write(f"Blended rates computed for {len(blended_rates)} models")

        daily_created, daily_updated = self._sync_daily(stats, blended_rates, dry_run)
        session_created, session_updated = self._sync_sessions(sessions_dir, dry_run)

        self.stdout.write(
            self.style.SUCCESS(
                f"Daily usage: {daily_created} created, {daily_updated} updated | "
                f"Sessions: {session_created} created, {session_updated} updated"
            )
        )

    def _sync_daily(self, stats: dict, blended_rates: dict, dry_run: bool):
        daily_activity: dict[str, dict] = {
            row["date"]: row for row in stats.get("dailyActivity", [])
        }
        daily_tokens: dict[str, dict] = {
            row["date"]: row.get("tokensByModel", {})
            for row in stats.get("dailyModelTokens", [])
        }

        all_dates = set(daily_activity) | set(daily_tokens)
        created = updated = 0

        for date_str in sorted(all_dates):
            activity = daily_activity.get(date_str, {})
            tokens_by_model = daily_tokens.get(date_str, {})

            tool_count = activity.get("toolCallCount", 0)
            sess_count = activity.get("sessionCount", 0)

            if not tokens_by_model:
                # No model data for this date — insert a placeholder row under "unknown"
                tokens_by_model = {"unknown": 0}

            for model_id, total_tokens in tokens_by_model.items():
                cost = cost_for_tokens(model_id, total_tokens, blended_rates)

                if dry_run:
                    self.stdout.write(
                        f"  [dry-run] {date_str} {model_id}: "
                        f"{total_tokens} tokens, ${cost}, {tool_count} tool calls"
                    )
                    continue

                obj, was_created = ClaudeDailyUsage.objects.update_or_create(
                    date=date_str,
                    model=model_id,
                    defaults={
                        "total_tokens": total_tokens,
                        "api_equiv_cost_usd": cost,
                        "tool_call_count": tool_count,
                        "session_count": sess_count,
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        return created, updated

    def _sync_sessions(self, sessions_dir: Path, dry_run: bool):
        created = updated = 0

        if not sessions_dir.exists():
            self.stdout.write(f"Sessions directory not found: {sessions_dir}")
            return created, updated

        for session_file in sessions_dir.glob("*.json"):
            try:
                with open(session_file) as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self.stdout.write(self.style.WARNING(f"Skipping unreadable: {session_file}"))
                continue

            session_id = data.get("sessionId")
            if not session_id:
                continue

            cwd = data.get("cwd", "")
            project_name = Path(cwd).name if cwd else ""
            started_ms = data.get("startedAt", 0)
            started_at = datetime.fromtimestamp(started_ms / 1000, tz=timezone.utc)

            if dry_run:
                self.stdout.write(
                    f"  [dry-run] session {session_id[:8]}... {project_name} @ {started_at:%Y-%m-%d}"
                )
                continue

            obj, was_created = ClaudeSession.objects.update_or_create(
                session_id=session_id,
                defaults={
                    "project_path": cwd,
                    "project_name": project_name,
                    "started_at": started_at,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        return created, updated
