"""
Weekly burn rate predictor for Claude Pro plan usage.

Primary metric: tool call count (tracked via PostToolUse hook).
Alert levels: green / yellow / red based on % of personal_weekly_peak consumed.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from config.utils import get_config

PEAK_KEY = "claude_personal_weekly_peak"
YELLOW_KEY = "claude_alert_yellow_pct"
RED_KEY = "claude_alert_red_pct"

DEFAULT_PEAK = 3000
DEFAULT_YELLOW = 60
DEFAULT_RED = 80


@dataclass
class UsagePrediction:
    week_start: date
    tool_calls_this_week: int
    today_tools: int
    projected_today_tools: int
    projected_week_tools: int
    personal_weekly_peak: int
    pct_of_peak_used: float
    alert_level: str          # "green" | "yellow" | "red"
    projected_days_until_limit: float | None
    days_until_week_reset: int


def _get_peak() -> int:
    val = get_config(PEAK_KEY)
    try:
        return int(val)
    except (TypeError, ValueError):
        return DEFAULT_PEAK


def _get_threshold(key: str, default: int) -> int:
    val = get_config(key)
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def predict(daily_rows) -> UsagePrediction:
    """
    Compute a usage prediction from a queryset/list of ClaudeDailyUsage rows.

    `daily_rows` should cover at minimum the trailing 7 days. Multiple rows per
    date (one per model) are deduplicated by taking the max tool_call_count per date.
    """
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday

    by_date: dict[date, int] = {}
    for row in daily_rows:
        d = row.date
        by_date[d] = max(by_date.get(d, 0), row.tool_call_count)

    tools_past = sum(
        by_date.get(today - timedelta(days=delta), 0)
        for delta in range(1, 7)
    )

    today_tools = by_date.get(today, 0)

    now_utc = datetime.now(timezone.utc)
    hours_elapsed = now_utc.hour + now_utc.minute / 60 + 1  # +1 to avoid /0 at midnight
    velocity = today_tools / hours_elapsed
    projected_today = int(velocity * 24)

    tool_calls_this_week = tools_past + today_tools
    projected_week = tools_past + projected_today

    peak = _get_peak()
    pct = round((projected_week / peak) * 100, 1) if peak > 0 else 0.0

    yellow_threshold = _get_threshold(YELLOW_KEY, DEFAULT_YELLOW)
    red_threshold = _get_threshold(RED_KEY, DEFAULT_RED)

    if pct >= red_threshold:
        alert_level = "red"
    elif pct >= yellow_threshold:
        alert_level = "yellow"
    else:
        alert_level = "green"

    remaining = peak - projected_week
    if velocity > 0 and remaining > 0:
        projected_days = round(remaining / (velocity * 24), 1)
    elif remaining <= 0:
        projected_days = 0.0
    else:
        projected_days = None

    days_until_reset = (7 - today.weekday()) % 7 or 7

    return UsagePrediction(
        week_start=week_start,
        tool_calls_this_week=tool_calls_this_week,
        today_tools=today_tools,
        projected_today_tools=projected_today,
        projected_week_tools=projected_week,
        personal_weekly_peak=peak,
        pct_of_peak_used=pct,
        alert_level=alert_level,
        projected_days_until_limit=projected_days,
        days_until_week_reset=days_until_reset,
    )
