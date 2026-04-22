import json
from datetime import date, timedelta

from .models import ClaudeDailyUsage, ClaudeToolCount, ClaudeUsageSnapshot


def collect_claude_dashboard_summary():
    today = date.today()
    trailing_7_start = today - timedelta(days=6)

    rows = list(ClaudeDailyUsage.objects.filter(date__gte=trailing_7_start))
    by_date: dict[str, int] = {}
    for r in rows:
        ds = str(r.date)
        by_date[ds] = max(by_date.get(ds, 0), r.tool_call_count)

    labels = []
    counts = []
    for i in range(7):
        d = trailing_7_start + timedelta(days=i)
        labels.append(d.strftime("%m/%d"))
        counts.append(by_date.get(str(d), 0))

    tool_rows = ClaudeToolCount.objects.filter(
        date__gte=trailing_7_start, date__lte=today
    ).values("tool_name", "count")
    by_tool: dict[str, int] = {}
    for tc in tool_rows:
        by_tool[tc["tool_name"]] = by_tool.get(tc["tool_name"], 0) + tc["count"]

    try:
        snapshot = ClaudeUsageSnapshot.objects.latest()
        weekly_pct = snapshot.weekly_pct
        weekly_resets_at = snapshot.weekly_resets_at
        session_pct = snapshot.session_pct
        session_resets_at = snapshot.session_resets_at
        if weekly_resets_at:
            days_until_reset = (weekly_resets_at.date() - today).days
        else:
            days_until_reset = None
    except ClaudeUsageSnapshot.DoesNotExist:
        weekly_pct = None
        weekly_resets_at = None
        session_pct = None
        session_resets_at = None
        days_until_reset = None

    return {
        "labels_json": json.dumps(labels),
        "counts_json": json.dumps(counts),
        "by_tool_json": json.dumps(by_tool),
        "weekly_pct": weekly_pct,
        "weekly_resets_at": weekly_resets_at,
        "session_pct": session_pct,
        "session_resets_at": session_resets_at,
        "days_until_reset": days_until_reset,
        "total_7d": sum(counts),
    }
