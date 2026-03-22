import json
from datetime import date, timedelta
from collections import defaultdict
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import WeightEntry, ExerciseEntry, ACTIVITY_CHOICES, YARDS_PER_MILE

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
        return redirect('weight_list')

    entries = list(WeightEntry.objects.filter(user=request.user).order_by('-date'))

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

    latest = entries[0] if entries else None
    lowest = min(entries, key=lambda e: e.weight) if entries else None
    highest = max(entries, key=lambda e: e.weight) if entries else None

    return render(request, 'health/weight.html', {
        'entries_with_change': entries_with_change,
        'chart_data': chart_data,
        'today': date.today().isoformat(),
        'latest': latest,
        'lowest': lowest,
        'highest': highest,
        'total_entries': len(entries),
    })


@login_required
def weight_delete(request, pk):
    entry = get_object_or_404(WeightEntry, pk=pk, user=request.user)
    if request.method == 'POST':
        entry.delete()
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
