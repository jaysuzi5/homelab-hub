import json
from calendar import monthrange
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Min, Sum
from django.shortcuts import render

from .models import ClaudeDailyUsage, ClaudeSession, ClaudeToolCount, ClaudeUsageSnapshot
from .predictor import predict



@login_required
def overview(request):
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    trailing_14_start = today - timedelta(days=13)

    rows_14 = list(ClaudeDailyUsage.objects.filter(date__gte=trailing_14_start))

    prediction = predict(rows_14)

    weekly_cost = sum(
        float(r.api_equiv_cost_usd) for r in rows_14 if r.date >= week_start
    )

    # Rolling 14-day — by-day counts (deduplicated)
    trailing_by_day: dict[str, int] = {}
    for r in rows_14:
        ds = str(r.date)
        trailing_by_day[ds] = max(trailing_by_day.get(ds, 0), r.tool_call_count)

    # Rolling 14-day — by-tool counts
    week_tool_rows = ClaudeToolCount.objects.filter(
        date__gte=trailing_14_start, date__lte=today
    ).values("tool_name", "count")
    week_by_tool: dict[str, int] = {}
    for tc in week_tool_rows:
        week_by_tool[tc["tool_name"]] = week_by_tool.get(tc["tool_name"], 0) + tc["count"]

    # Day labels and per-day counts for the 14-day chart
    week_day_labels = []
    week_day_counts = []
    for i in range(14):
        d = trailing_14_start + timedelta(days=i)
        week_day_labels.append(d.strftime("%m/%d"))
        week_day_counts.append(trailing_by_day.get(str(d), 0))

    # Today — per-tool breakdown
    today_tool_rows = ClaudeToolCount.objects.filter(date=today).values("tool_name", "count")
    today_by_tool: dict[str, int] = {tc["tool_name"]: tc["count"] for tc in today_tool_rows}
    today_count = sum(today_by_tool.values()) if today_by_tool else max(
        (r.tool_call_count for r in rows_14 if r.date == today), default=0
    )

    try:
        latest_snapshot = ClaudeUsageSnapshot.objects.latest()
        days_until_reset = (
            (latest_snapshot.weekly_resets_at.date() - today).days
            if latest_snapshot and latest_snapshot.weekly_resets_at else None
        )
    except ClaudeUsageSnapshot.DoesNotExist:
        latest_snapshot = None
        days_until_reset = None

    return render(request, "claude_usage/overview.html", {
        "prediction": prediction,
        "weekly_cost": round(weekly_cost, 2),
        "trailing_start_str": trailing_14_start.strftime("%b %d"),
        "trailing_end_str": today.strftime("%b %d"),
        "week_day_labels_json": json.dumps(week_day_labels),
        "week_day_counts_json": json.dumps(week_day_counts),
        "week_by_tool_json": json.dumps(week_by_tool),
        "today_by_tool_json": json.dumps(today_by_tool),
        "today_count": today_count,
        "today_str": str(today),
        "snapshot": latest_snapshot,
        "days_until_reset": days_until_reset,
    })


@login_required
def history(request):
    today = date.today()
    week_start_current = today - timedelta(days=today.weekday())
    history_start = week_start_current - timedelta(weeks=7)

    # Per-date tool call counts (max across model rows to avoid duplication)
    rows = list(ClaudeDailyUsage.objects.filter(date__gte=history_start))
    by_date_tools: dict[date, int] = {}
    for r in rows:
        by_date_tools[r.date] = max(by_date_tools.get(r.date, 0), r.tool_call_count)

    # 8 week labels and totals
    week_starts = [week_start_current - timedelta(weeks=i) for i in range(7, -1, -1)]
    week_labels = [ws.strftime("%b %d") for ws in week_starts]
    week_totals = [
        sum(by_date_tools.get(ws + timedelta(days=d), 0) for d in range(7))
        for ws in week_starts
    ]

    # Drill-down: build from DB (by_day from ClaudeDailyUsage, by_tool from ClaudeToolCount)
    drilldown: dict[int, dict] = {}

    # by_day — one entry per date in the 8-week window
    for d_date, count in by_date_tools.items():
        for idx, ws in enumerate(week_starts):
            if ws <= d_date <= ws + timedelta(days=6):
                dd = drilldown.setdefault(idx, {"by_day": {}, "by_tool": {}})
                dd["by_day"][str(d_date)] = count
                break

    # by_tool — from ClaudeToolCount
    tool_rows = ClaudeToolCount.objects.filter(date__gte=history_start).values("date", "tool_name", "count")
    for tc in tool_rows:
        for idx, ws in enumerate(week_starts):
            if ws <= tc["date"] <= ws + timedelta(days=6):
                dd = drilldown.setdefault(idx, {"by_day": {}, "by_tool": {}})
                dd["by_tool"][tc["tool_name"]] = dd["by_tool"].get(tc["tool_name"], 0) + tc["count"]
                break

    # Daily detail for calendar click: all-time per-day per-tool breakdown
    all_tool_rows = ClaudeToolCount.objects.all().values("date", "tool_name", "count")
    daily_tools: dict[str, dict] = {}
    for tc in all_tool_rows:
        ds = str(tc["date"])
        if ds not in daily_tools:
            daily_tools[ds] = {"count": 0, "by_tool": {}}
        daily_tools[ds]["by_tool"][tc["tool_name"]] = tc["count"]
        daily_tools[ds]["count"] += tc["count"]

    # Calendar heatmap using tool_call_count across all history
    all_rows = list(ClaudeDailyUsage.objects.all())
    all_by_date: dict[date, int] = {}
    for r in all_rows:
        all_by_date[r.date] = max(all_by_date.get(r.date, 0), r.tool_call_count)

    max_tools = max(all_by_date.values(), default=1) or 1
    min_date = min(all_by_date.keys(), default=today)

    # Build months as weeks-as-rows (calendar style)
    heatmap_months = []
    cur = min_date.replace(day=1)
    end_month = today.replace(day=1)
    while cur <= end_month:
        days_in_month = monthrange(cur.year, cur.month)[1]
        days = []
        for day_num in range(1, days_in_month + 1):
            d = cur.replace(day=day_num)
            count = all_by_date.get(d, 0)
            intensity = min(4, int(count / max_tools * 4) + 1) if count > 0 else 0
            days.append({"date": str(d), "count": count, "intensity": intensity})

        first_weekday = cur.weekday()  # 0=Mon
        cells = [None] * first_weekday + days
        remainder = len(cells) % 7
        if remainder:
            cells += [None] * (7 - remainder)
        # Each chunk of 7 is a week-row (Mon–Sun)
        weeks_grid = [cells[i:i + 7] for i in range(0, len(cells), 7)]

        heatmap_months.append({
            "label": cur.strftime("%b %Y"),
            "weeks": weeks_grid,
        })
        cur = cur.replace(
            month=cur.month % 12 + 1,
            year=cur.year + (1 if cur.month == 12 else 0),
        )

    today_count = all_by_date.get(today, 0)

    return render(request, "claude_usage/history.html", {
        "weekly_chart_json": json.dumps({
            "labels": week_labels,
            "tools": week_totals,
            "week_starts": [str(ws) for ws in week_starts],
        }),
        "drilldown_json": json.dumps(drilldown),
        "daily_tools_json": json.dumps(daily_tools),
        "heatmap_months": heatmap_months,
        "max_tools": max_tools,
        "today_str": str(today),
        "today_count": today_count,
    })


@login_required
def by_project(request):
    sessions = list(
        ClaudeSession.objects.values("project_name", "project_path")
        .annotate(
            session_count=Count("session_id"),
            first_seen=Min("started_at"),
            last_seen=Max("started_at"),
        )
        .order_by("-session_count")
    )
    return render(request, "claude_usage/by_project.html", {"sessions": sessions})


