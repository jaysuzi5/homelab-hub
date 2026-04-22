"""
Management command: sync_web_usage

Fetches live usage percentages from claude.ai/api/organizations/{org}/usage
using the session cookie from Chrome. Stores a ClaudeUsageSnapshot record.

Run locally on the Mac — requires Chrome to be installed and logged into claude.ai.
"""

from datetime import datetime
from pathlib import Path

import browser_cookie3
import requests
from django.core.management.base import BaseCommand, CommandError

from claude_usage.models import ClaudeUsageSnapshot
from config.utils import get_config

ORG_ID_KEY = "claude_org_id"
DEFAULT_ORG_ID = "af2bb622-17e0-41a3-8bae-dd1881bc8c22"

# Session key cache — written by stop hook (GUI context), read by LaunchAgent (no Keychain)
SESSION_KEY_CACHE = Path.home() / ".claude" / ".session_key"

HEADERS = {
    "anthropic-client-platform": "web_claude_ai",
    "content-type": "application/json",
    "referer": "https://claude.ai/settings/usage",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36"
    ),
}


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


class Command(BaseCommand):
    help = "Fetch live Claude usage % from claude.ai and store a snapshot"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch and print without writing to the database",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        org_id = get_config(ORG_ID_KEY) or DEFAULT_ORG_ID
        url = f"https://claude.ai/api/organizations/{org_id}/usage"

        session = requests.Session()

        # Try live Chrome cookies first (requires GUI/Keychain — works in terminal/stop hook).
        # Fall back to cached session key file written by a previous stop hook run.
        cookie_source = "chrome"
        try:
            cj = browser_cookie3.chrome(domain_name=".claude.ai")
            session.cookies = cj
            # Persist the decrypted key so the LaunchAgent can use it without Keychain
            for c in cj:
                if c.name == "sessionKey":
                    SESSION_KEY_CACHE.write_text(c.value)
                    SESSION_KEY_CACHE.chmod(0o600)
                    break
        except Exception:
            cookie_source = "cache"
            if not SESSION_KEY_CACHE.exists():
                raise CommandError(
                    "Chrome cookies unavailable and no cached session key found. "
                    "Run sync_web_usage once in a terminal to prime the cache."
                )
            session.cookies.set("sessionKey", SESSION_KEY_CACHE.read_text().strip(), domain=".claude.ai")

        try:
            resp = session.get(url, headers=HEADERS, timeout=10)
        except requests.RequestException as e:
            raise CommandError(f"API request failed: {e}")

        if resp.status_code != 200:
            raise CommandError(f"API returned {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        five_hour = data.get("five_hour") or {}
        seven_day = data.get("seven_day") or {}
        extra = data.get("extra_usage") or {}

        session_pct = five_hour.get("utilization")
        session_resets_at = _parse_dt(five_hour.get("resets_at"))
        weekly_pct = seven_day.get("utilization")
        weekly_resets_at = _parse_dt(seven_day.get("resets_at"))
        extra_enabled = extra.get("is_enabled", False)
        extra_credits = extra.get("used_credits", 0)

        if dry_run:
            self.stdout.write(
                f"  [dry-run] session={session_pct}%  resets={session_resets_at}\n"
                f"  [dry-run] weekly={weekly_pct}%  resets={weekly_resets_at}\n"
                f"  [dry-run] extra_enabled={extra_enabled}  credits_used={extra_credits}"
            )
            return

        ClaudeUsageSnapshot.objects.create(
            session_pct=session_pct,
            session_resets_at=session_resets_at,
            weekly_pct=weekly_pct,
            weekly_resets_at=weekly_resets_at,
            extra_usage_enabled=extra_enabled,
            extra_usage_credits_used=extra_credits,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Snapshot saved [{cookie_source}]: session={session_pct}% | "
                f"weekly={weekly_pct}% resets {weekly_resets_at:%a %b %d %H:%M UTC}"
            )
        )
