import json
from datetime import date, timedelta
from collections import defaultdict
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import (WeightEntry, WeightGoal, WeightChartPrefs, ExerciseEntry, StepEntry, StepPrefs,
                     ACTIVITY_CHOICES, YARDS_PER_MILE, DEFAULT_STEPS_PER_MILE)

STEP_GOAL = 50000
WEEKS_PER_PAGE = 52

ACTIVITIES = [a[0] for a in ACTIVITY_CHOICES]
ACTIVITY_LABELS = dict(ACTIVITY_CHOICES)


# ── helpers ───────────────────────────────────────────────────────────────────

def fmt_duration(minutes):
    if not minutes:
        return '—'
    h, m = divmod(int(minutes), 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


def get_week_start(d):
    """Return Monday of the week containing date d."""
    return d - timedelta(days=d.weekday())


def week_label(ws):
    return f"{ws.strftime('%b %d')} – {(ws + timedelta(days=6)).strftime('%b %d, %Y')}"


def build_week_data(entries):
    """
    Given an iterable of ExerciseEntry objects, return a dict keyed by week_start date.
    Each value has per-activity and total aggregates plus pre-formatted strings.
    """
    weeks = {}
    for entry in entries:
        ws = get_week_start(entry.date)
        if ws not in weeks:
            weeks[ws] = {
                'week_start': ws,
                'week_end': ws + timedelta(days=6),
                'label': week_label(ws),
                'activities': {a: {'duration': 0, 'distance': 0.0, 'count': 0} for a in ACTIVITIES},
                'total': {'duration': 0, 'distance': 0.0, 'count': 0},
            }
        act = entry.activity
        weeks[ws]['activities'][act]['duration'] += entry.duration
        weeks[ws]['activities'][act]['distance'] += float(entry.distance_miles)
        weeks[ws]['activities'][act]['count'] += 1
        weeks[ws]['total']['duration'] += entry.duration
        weeks[ws]['total']['distance'] += float(entry.distance_miles)
        weeks[ws]['total']['count'] += 1

    # Add formatted strings
    for ws, data in weeks.items():
        t = data['total']
        t['duration_fmt'] = fmt_duration(t['duration'])
        t['distance_fmt'] = f"{t['distance']:.1f}"
        for a in ACTIVITIES:
            d = data['activities'][a]
            d['duration_fmt'] = fmt_duration(d['duration']) if d['count'] else '—'
            d['distance_fmt'] = f"{d['distance']:.1f}" if d['count'] else '—'

    return weeks


# ── weight views ──────────────────────────────────────────────────────────────

@login_required
def weight_list(request):
    if request.method == 'POST':
        entry_date = request.POST.get('date', '').strip()
        weight_raw = request.POST.get('weight', '').strip()
        try:
            weight_val = float(weight_raw)
            if weight_val <= 0:
                raise ValueError
            WeightEntry.objects.update_or_create(
                user=request.user,
                date=entry_date,
                defaults={'weight': weight_val},
            )
        except (ValueError, TypeError):
            messages.error(request, 'Please enter a valid weight.')
        # Preserve chart range params on redirect
        params = request.POST.get('_range_params', '')
        return redirect(f"/health/weight/?{params}" if params else '/health/weight/')

    entries = list(WeightEntry.objects.filter(user=request.user).order_by('-date'))
    goals = list(WeightGoal.objects.filter(user=request.user).order_by('target_date'))

    # Saved chart start preference
    try:
        prefs = WeightChartPrefs.objects.get(user=request.user)
        saved_start = prefs.chart_start_date
    except WeightChartPrefs.DoesNotExist:
        saved_start = None

    # GET params override saved prefs / defaults
    start_str = request.GET.get('start', '').strip()
    end_str = request.GET.get('end', '').strip()

    if not start_str:
        if saved_start:
            start_str = saved_start.isoformat()
        elif entries:
            start_str = str(entries[-1].date)  # oldest (list is -date order)
        else:
            start_str = date.today().isoformat()

    if not end_str:
        if goals:
            end_str = str(goals[-1].target_date)
        elif entries:
            end_str = str(entries[0].date)  # newest
        else:
            end_str = date.today().isoformat()

    entries_with_change = []
    for i, entry in enumerate(entries):
        if i + 1 < len(entries):
            change = float(entry.weight) - float(entries[i + 1].weight)
        else:
            change = None
        entries_with_change.append({'entry': entry, 'change': change})

    chart_data = json.dumps([
        {'date': str(e.date), 'weight': float(e.weight)}
        for e in reversed(entries)
    ])

    goals_data = json.dumps([
        {'date': str(g.target_date), 'weight': float(g.target_weight), 'label': g.label}
        for g in goals
    ])

    latest = entries[0] if entries else None
    lowest = min(entries, key=lambda e: e.weight) if entries else None
    highest = max(entries, key=lambda e: e.weight) if entries else None

    weight_loss = float(highest.weight) - float(latest.weight) if entries else None
    if entries and len(entries) > 1:
        oldest = entries[-1]
        avg_loss_per_week = (float(oldest.weight) - float(latest.weight)) / (len(entries) - 1)
    else:
        avg_loss_per_week = None

    return render(request, 'health/weight.html', {
        'entries_with_change': entries_with_change,
        'chart_data': chart_data,
        'goals_data': goals_data,
        'goals': goals,
        'chart_start': start_str,
        'chart_end': end_str,
        'today': date.today().isoformat(),
        'latest': latest,
        'lowest': lowest,
        'highest': highest,
        'weight_loss': weight_loss,
        'avg_loss_per_week': avg_loss_per_week,
        'total_entries': len(entries),
    })


@login_required
def weight_delete(request, pk):
    entry = get_object_or_404(WeightEntry, pk=pk, user=request.user)
    if request.method == 'POST':
        entry.delete()
    return redirect('weight_list')


@login_required
def weight_goal_add(request):
    if request.method == 'POST':
        target_date = request.POST.get('target_date', '').strip()
        weight_raw = request.POST.get('target_weight', '').strip()
        label = request.POST.get('label', '').strip()
        try:
            weight_val = float(weight_raw)
            if weight_val <= 0:
                raise ValueError
            WeightGoal.objects.update_or_create(
                user=request.user,
                target_date=target_date,
                defaults={'target_weight': weight_val, 'label': label},
            )
        except (ValueError, TypeError):
            messages.error(request, 'Please enter a valid goal weight.')
    params = request.POST.get('_range_params', '')
    return redirect(f"/health/weight/?{params}" if params else '/health/weight/')


@login_required
def weight_goal_delete(request, pk):
    goal = get_object_or_404(WeightGoal, pk=pk, user=request.user)
    if request.method == 'POST':
        goal.delete()
    params = request.POST.get('_range_params', '')
    return redirect(f"/health/weight/?{params}" if params else '/health/weight/')


@login_required
def weight_chart_prefs_save(request):
    if request.method == 'POST':
        start_str = request.POST.get('start', '').strip()
        end_str = request.POST.get('end', '').strip()
        if start_str:
            try:
                start_date = date.fromisoformat(start_str)
                WeightChartPrefs.objects.update_or_create(
                    user=request.user,
                    defaults={'chart_start_date': start_date},
                )
            except ValueError:
                pass
        params = []
        if start_str:
            params.append(f"start={start_str}")
        if end_str:
            params.append(f"end={end_str}")
        qs = '&'.join(params)
        return redirect(f"/health/weight/?{qs}" if qs else '/health/weight/')
    return redirect('weight_list')


# ── exercise views ────────────────────────────────────────────────────────────

@login_required
def exercise(request):
    today = date.today()

    # Add entry
    if request.method == 'POST':
        entry_date = request.POST.get('date', '').strip()
        entry_time = request.POST.get('time', '').strip()
        activity = request.POST.get('activity', '').strip()
        duration_raw = request.POST.get('duration', '').strip()
        distance_raw = request.POST.get('distance', '').strip()
        try:
            duration_val = int(duration_raw)
            distance_val = float(distance_raw)
            if duration_val <= 0 or distance_val <= 0:
                raise ValueError
            if activity == 'swim':
                yards = int(round(distance_val))
                miles = round(yards / YARDS_PER_MILE, 1)
            else:
                yards = None
                miles = round(distance_val, 1)
            ExerciseEntry.objects.create(
                user=request.user,
                date=entry_date,
                time=entry_time,
                activity=activity,
                duration=duration_val,
                distance_miles=miles,
                distance_yards=yards,
            )
        except (ValueError, TypeError):
            messages.error(request, 'Please check your inputs and try again.')
        return redirect('exercise')

    # Selected week for detail panel
    week_str = request.GET.get('week', '')
    selected_week = None
    week_entries = []
    if week_str:
        try:
            selected_week = date.fromisoformat(week_str)
            week_end = selected_week + timedelta(days=6)
            week_entries = list(
                ExerciseEntry.objects.filter(
                    user=request.user,
                    date__gte=selected_week,
                    date__lte=week_end,
                ).order_by('date', 'time')
            )
        except ValueError:
            selected_week = None

    all_entries = list(ExerciseEntry.objects.filter(user=request.user).order_by('date', 'time'))
    weeks = build_week_data(all_entries)

    # Current and past week summaries
    current_ws = get_week_start(today)
    past_ws = current_ws - timedelta(weeks=1)
    current_week = weeks.get(current_ws)
    past_week = weeks.get(past_ws)

    # Weekly summary sorted newest first
    sorted_weeks = sorted(weeks.values(), key=lambda w: w['week_start'], reverse=True)

    # Chart data (oldest to newest)
    chart_data = json.dumps([
        {
            'label': w['label'],
            'distance': float(w['total']['distance']),
            'hours': round(w['total']['duration'] / 60, 2),
        }
        for w in sorted(weeks.values(), key=lambda w: w['week_start'])
    ])

    return render(request, 'health/exercise.html', {
        'today': today.isoformat(),
        'now_time': today.strftime('%H:%M'),
        'activity_choices': ACTIVITY_CHOICES,
        'activity_labels': ACTIVITY_LABELS,
        'activities': ACTIVITIES,
        'current_week': current_week,
        'past_week': past_week,
        'current_week_label': week_label(current_ws),
        'past_week_label': week_label(past_ws),
        'sorted_weeks': sorted_weeks,
        'chart_data': chart_data,
        'selected_week': selected_week,
        'selected_week_label': week_label(selected_week) if selected_week else '',
        'week_entries': week_entries,
    })


@login_required
def exercise_delete(request, pk):
    entry = get_object_or_404(ExerciseEntry, pk=pk, user=request.user)
    week_str = request.GET.get('week', '')
    if request.method == 'POST':
        entry.delete()
    if week_str:
        return redirect(f"{request.build_absolute_uri('/health/exercise/')}?week={week_str}")
    return redirect('exercise')


@login_required
def exercise_edit(request, pk):
    entry = get_object_or_404(ExerciseEntry, pk=pk, user=request.user)
    week_str = request.GET.get('week', '')

    if request.method == 'POST':
        entry_date = request.POST.get('date', '').strip()
        entry_time = request.POST.get('time', '').strip()
        activity = request.POST.get('activity', '').strip()
        duration_raw = request.POST.get('duration', '').strip()
        distance_raw = request.POST.get('distance', '').strip()
        try:
            duration_val = int(duration_raw)
            distance_val = float(distance_raw)
            if duration_val <= 0 or distance_val <= 0:
                raise ValueError
            if activity == 'swim':
                yards = int(round(distance_val))
                miles = round(yards / YARDS_PER_MILE, 1)
            else:
                yards = None
                miles = round(distance_val, 1)
            entry.date = entry_date
            entry.time = entry_time
            entry.activity = activity
            entry.duration = duration_val
            entry.distance_miles = miles
            entry.distance_yards = yards
            entry.save()
            if week_str:
                return redirect(f"/health/exercise/?week={week_str}")
            return redirect('exercise')
        except (ValueError, TypeError):
            messages.error(request, 'Please check your inputs and try again.')

    # Pre-fill distance with raw yards for swim, miles otherwise
    display_distance = entry.distance_yards if entry.activity == 'swim' and entry.distance_yards else entry.distance_miles

    return render(request, 'health/exercise_edit.html', {
        'entry': entry,
        'activity_choices': ACTIVITY_CHOICES,
        'display_distance': display_distance,
        'week_str': week_str,
    })


# ── steps views ─────────────────────────────────────────────────────────────

def week_start_sunday(d):
    """Return the Sunday that starts the week containing date d."""
    return d - timedelta(days=(d.weekday() + 1) % 7)


def steps_week_label(ws):
    return f"{ws.strftime('%b %d')} – {(ws + timedelta(days=6)).strftime('%b %d, %Y')}"


def steps_per_mile_for(user):
    prefs = StepPrefs.objects.filter(user=user).first()
    return prefs.steps_per_mile if prefs else DEFAULT_STEPS_PER_MILE


def steps_to_miles(steps, spm):
    return round(steps / spm, 2) if spm else 0


@login_required
def steps_prefs_save(request):
    """Update the steps-per-mile conversion used for mileage display."""
    if request.method == 'POST':
        raw = request.POST.get('steps_per_mile', '').strip()
        try:
            spm = int(raw)
            if spm < 1:
                raise ValueError
            StepPrefs.objects.update_or_create(
                user=request.user,
                defaults={'steps_per_mile': spm},
            )
        except (ValueError, TypeError):
            messages.error(request, 'Please enter a valid steps-per-mile value.')
    page = request.POST.get('_page', '').strip()
    return redirect(f"/health/steps/?page={page}" if page else '/health/steps/')


@login_required
def steps_save(request):
    """Upsert a single day's step count. Used by the entry form and per-day edits."""
    if request.method == 'POST':
        entry_date = request.POST.get('date', '').strip()
        steps_raw = request.POST.get('steps', '').strip()
        try:
            steps_val = int(steps_raw)
            if steps_val < 0:
                raise ValueError
            if not entry_date:
                raise ValueError
            StepEntry.objects.update_or_create(
                user=request.user,
                date=entry_date,
                defaults={'steps': steps_val},
            )
        except (ValueError, TypeError):
            messages.error(request, 'Please enter a valid step count.')
    page = request.POST.get('_page', '').strip()
    return redirect(f"/health/steps/?page={page}" if page else '/health/steps/')


@login_required
def steps_list(request):
    entries = list(StepEntry.objects.filter(user=request.user))
    steps_by_date = {e.date: e.steps for e in entries}
    today = date.today()
    spm = steps_per_mile_for(request.user)

    cur_ws = week_start_sunday(today)
    cur_total = sum(s for d, s in steps_by_date.items() if cur_ws <= d <= cur_ws + timedelta(days=6))
    cur_pct = min(100, round(cur_total / STEP_GOAL * 100)) if STEP_GOAL else 0

    all_total = sum(steps_by_date.values())

    first_ws = week_start_sunday(min(steps_by_date)) if steps_by_date else cur_ws

    weeks = []
    ws = cur_ws
    while ws >= first_ws:
        we = ws + timedelta(days=6)
        days = []
        recorded = []
        for i in range(7):
            d = ws + timedelta(days=i)
            s = steps_by_date.get(d)
            days.append({'date': d.isoformat(), 'label': d.strftime('%a %b %d'), 'steps': s,
                         'miles': steps_to_miles(s, spm) if s is not None else None})
            if s is not None:
                recorded.append((d, s))
        total = sum(s for _, s in recorded)
        low = min(recorded, key=lambda x: x[1]) if recorded else None
        high = max(recorded, key=lambda x: x[1]) if recorded else None
        weeks.append({
            'week_start': ws.isoformat(),
            'label': steps_week_label(ws),
            'total': total,
            'miles': steps_to_miles(total, spm),
            'pct': min(100, round(total / STEP_GOAL * 100)) if STEP_GOAL else 0,
            'low_steps': low[1] if low else None,
            'low_date': low[0].strftime('%a %b %d') if low else None,
            'high_steps': high[1] if high else None,
            'high_date': high[0].strftime('%a %b %d') if high else None,
            'days': days,
        })
        ws -= timedelta(days=7)

    try:
        page = max(1, int(request.GET.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    total_pages = max(1, (len(weeks) + WEEKS_PER_PAGE - 1) // WEEKS_PER_PAGE)
    page = min(page, total_pages)
    start = (page - 1) * WEEKS_PER_PAGE
    page_weeks = weeks[start:start + WEEKS_PER_PAGE]

    # Chart: oldest→newest across the current page
    chart_weeks = list(reversed(page_weeks))
    chart_data = [{'label': w['label'], 'total': w['total']} for w in chart_weeks]

    return render(request, 'health/steps.html', {
        'today': today.isoformat(),
        'goal': STEP_GOAL,
        'steps_per_mile': spm,
        'goal_miles': steps_to_miles(STEP_GOAL, spm),
        'cur_total': cur_total,
        'cur_miles': steps_to_miles(cur_total, spm),
        'all_total': all_total,
        'all_miles': steps_to_miles(all_total, spm),
        'cur_pct': cur_pct,
        'cur_remaining': max(0, STEP_GOAL - cur_total),
        'cur_label': steps_week_label(cur_ws),
        'page_weeks': page_weeks,
        'weeks_json': json.dumps(page_weeks),
        'chart_data': json.dumps(chart_data),
        'page': page,
        'total_pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_page': page - 1,
        'next_page': page + 1,
    })
