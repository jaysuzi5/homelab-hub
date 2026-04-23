import urllib.request
import urllib.parse
import json
from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .models import Book, GuitarSession, GUITAR_CATEGORY_CHOICES, GUITAR_SKILL_FIELDS
from .utils import download_cover
from dashboard.services.darts import collect_dart_summary


def _fmt_duration(minutes):
    if not minutes:
        return '—'
    h, m = divmod(int(minutes), 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


def _week_start(d):
    return d - timedelta(days=d.weekday())


def _week_label(ws):
    return f"{ws.strftime('%b %d')} – {(ws + timedelta(days=6)).strftime('%b %d, %Y')}"


def _week_summary(user, ws):
    we = ws + timedelta(days=6)
    qs = GuitarSession.objects.filter(user=user, date__gte=ws, date__lte=we)
    total = qs.aggregate(t=Sum('duration'))['t'] or 0
    by_cat = []
    for val, label in GUITAR_CATEGORY_CHOICES:
        mins = qs.filter(category=val).aggregate(t=Sum('duration'))['t'] or 0
        if mins:
            by_cat.append({'label': label, 'minutes': mins, 'fmt': _fmt_duration(mins)})
    return {'total': total, 'total_fmt': _fmt_duration(total), 'by_category': by_cat}


def _parse_session_post(request):
    entry_date = request.POST.get('date', '').strip()
    entry_time = request.POST.get('time', '').strip()
    category = request.POST.get('category', '').strip()
    duration_raw = request.POST.get('duration', '').strip()
    description = request.POST.get('description', '').strip()
    skills = {field: field in request.POST for field, _ in GUITAR_SKILL_FIELDS}
    duration = int(duration_raw)
    if duration <= 0:
        raise ValueError
    return entry_date, entry_time, category, duration, description, skills

User = get_user_model()


@login_required
def reading_list(request):
    reader_name = request.GET.get('reader', '').strip()
    if reader_name:
        reader = get_object_or_404(User, username=reader_name)
    else:
        reader = request.user

    books = Book.objects.filter(user=reader)
    total_books = books.count()
    total_pages = sum(b.pages for b in books if b.pages)
    current_year = date.today().year
    books_this_year = books.filter(date_read__year=current_year).count()

    other_readers = (
        User.objects
        .filter(books__isnull=False)
        .exclude(pk=reader.pk)
        .distinct()
    )

    context = {
        'books': books,
        'total_books': total_books,
        'total_pages': total_pages,
        'books_this_year': books_this_year,
        'current_year': current_year,
        'reader': reader,
        'is_own_list': reader == request.user,
        'other_readers': other_readers,
    }
    return render(request, 'hobbies/reading_list.html', context)


@login_required
def book_detail(request, pk):
    book = get_object_or_404(Book, pk=pk)
    is_owner = book.user == request.user

    if request.method == 'POST' and is_owner:
        rating_raw = request.POST.get('rating', '').strip()
        book.rating = int(rating_raw) if rating_raw.isdigit() and 0 <= int(rating_raw) <= 5 else None
        book.comment = request.POST.get('comment', '').strip()
        book.summary = request.POST.get('summary', '').strip()
        new_cover_url = request.POST.get('cover_url', '').strip()
        update_fields = ['rating', 'comment', 'summary', 'cover_url', 'cover_local']
        if new_cover_url != book.cover_url:
            book.cover_url = new_cover_url
            book.cover_local = download_cover(new_cover_url, book.pk) if new_cover_url else ''
        book.save(update_fields=update_fields)
        return redirect('reading_list')

    return render(request, 'hobbies/book_detail.html', {'book': book, 'is_owner': is_owner, 'star_range': range(1, 6)})


@login_required
def book_add(request):
    if request.method == 'POST':
        date_read = request.POST.get('date_read')
        title = request.POST.get('title', '').strip()
        author = request.POST.get('author', '').strip()
        pages_raw = request.POST.get('pages', '').strip()
        cover_url = request.POST.get('cover_url', '').strip()
        open_library_key = request.POST.get('open_library_key', '').strip()
        summary = request.POST.get('summary', '').strip()

        pages = int(pages_raw) if pages_raw.isdigit() else None
        rating_raw = request.POST.get('rating', '').strip()
        rating = int(rating_raw) if rating_raw.isdigit() and 0 <= int(rating_raw) <= 5 else None
        comment = request.POST.get('comment', '').strip()

        book = Book.objects.create(
            user=request.user,
            date_read=date_read,
            title=title,
            author=author,
            pages=pages,
            cover_url=cover_url,
            open_library_key=open_library_key,
            summary=summary,
            rating=rating,
            comment=comment,
        )
        if cover_url:
            local = download_cover(cover_url, book.pk)
            if local:
                book.cover_local = local
                book.save(update_fields=['cover_local'])
        return redirect('reading_list')

    return render(request, 'hobbies/book_add.html', {'today': date.today().isoformat()})


@login_required
@require_GET
def book_search(request):
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'results': []})

    encoded = urllib.parse.quote(query)
    url = (
        f"https://openlibrary.org/search.json"
        f"?q={encoded}&fields=key,title,author_name,number_of_pages_median,cover_i&limit=10"
    )

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'HomeLab-Hub/1.0'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return JsonResponse({'results': [], 'error': 'Search failed'})

    results = []
    for doc in data.get('docs', []):
        cover_i = doc.get('cover_i')
        cover_url = f"https://covers.openlibrary.org/b/id/{cover_i}-M.jpg" if cover_i else ''
        results.append({
            'key': doc.get('key', ''),
            'title': doc.get('title', ''),
            'author': ', '.join(doc.get('author_name', [])),
            'pages': doc.get('number_of_pages_median'),
            'cover_url': cover_url,
        })

    return JsonResponse({'results': results})


@login_required
@require_GET
def book_works(request):
    """Proxy Open Library Works API to fetch a book's description/summary."""
    key = request.GET.get('key', '').strip()
    if not key or not key.startswith('/works/'):
        return JsonResponse({'summary': ''})

    url = f"https://openlibrary.org{key}.json"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'HomeLab-Hub/1.0'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return JsonResponse({'summary': ''})

    description = data.get('description', '')
    if isinstance(description, dict):
        description = description.get('value', '')

    return JsonResponse({'summary': description[:2000]})


@login_required
def darts(request):
    dart_avg_scores_501, dart_avg_scores_score_training = collect_dart_summary()
    context = {
        'dart_avg_scores_501': dart_avg_scores_501,
        'dart_avg_scores_score_training': dart_avg_scores_score_training,
    }
    return render(request, 'hobbies/darts.html', context)


@login_required
def guitar(request):
    today = date.today()

    if request.method == 'POST':
        try:
            d, t, cat, dur, desc, skills = _parse_session_post(request)
            GuitarSession.objects.create(
                user=request.user, date=d, time=t, category=cat,
                duration=dur, description=desc, **skills,
            )
        except (ValueError, TypeError):
            messages.error(request, 'Please check your inputs and try again.')
        return redirect('guitar')

    current_ws = _week_start(today)
    past_ws = current_ws - timedelta(weeks=1)

    all_qs = GuitarSession.objects.filter(user=request.user)
    total_all = all_qs.aggregate(t=Sum('duration'))['t'] or 0

    by_category = []
    for val, label in GUITAR_CATEGORY_CHOICES:
        mins = all_qs.filter(category=val).aggregate(t=Sum('duration'))['t'] or 0
        count = all_qs.filter(category=val).count()
        if count:
            by_category.append({'label': label, 'minutes': mins, 'fmt': _fmt_duration(mins), 'count': count})

    by_skill = []
    for field, label in GUITAR_SKILL_FIELDS:
        mins = all_qs.filter(**{field: True}).aggregate(t=Sum('duration'))['t'] or 0
        count = all_qs.filter(**{field: True}).count()
        if count:
            by_skill.append({'label': label, 'minutes': mins, 'fmt': _fmt_duration(mins), 'count': count})

    today_sessions = all_qs.filter(date=today)
    today_total = today_sessions.aggregate(t=Sum('duration'))['t'] or 0

    # Daily chart — last 14 days (2 queries total for both charts)
    day_start = today - timedelta(days=13)
    week_start_26 = current_ws - timedelta(weeks=25)

    range_qs = (
        GuitarSession.objects
        .filter(user=request.user, date__gte=week_start_26)
        .values('date')
        .annotate(total=Sum('duration'))
    )
    date_totals = {row['date']: row['total'] for row in range_qs}

    daily_chart = json.dumps([
        {'label': (today - timedelta(days=13 - i)).strftime('%b %d'),
         'minutes': date_totals.get(today - timedelta(days=13 - i), 0)}
        for i in range(14)
    ])

    weekly_dict = {}
    for d, mins in date_totals.items():
        ws = _week_start(d)
        weekly_dict[ws] = weekly_dict.get(ws, 0) + mins

    weekly_chart = json.dumps([
        {'label': (current_ws - timedelta(weeks=25 - i)).strftime('%b %d'),
         'minutes': weekly_dict.get(current_ws - timedelta(weeks=25 - i), 0)}
        for i in range(26)
    ])

    return render(request, 'hobbies/guitar.html', {
        'today': today.isoformat(),
        'now_time': today.strftime('%H:%M'),
        'category_choices': GUITAR_CATEGORY_CHOICES,
        'skill_fields': GUITAR_SKILL_FIELDS,
        'today_sessions': today_sessions,
        'today_total_fmt': _fmt_duration(today_total),
        'this_week': _week_summary(request.user, current_ws),
        'last_week': _week_summary(request.user, past_ws),
        'current_week_label': _week_label(current_ws),
        'past_week_label': _week_label(past_ws),
        'total_all_fmt': _fmt_duration(total_all),
        'by_category': by_category,
        'by_skill': by_skill,
        'daily_chart': daily_chart,
        'weekly_chart': weekly_chart,
    })


@login_required
def guitar_history(request):
    selected_category = request.GET.get('category', '')
    selected_skill = request.GET.get('skill', '')

    qs = GuitarSession.objects.filter(user=request.user)
    if selected_category:
        qs = qs.filter(category=selected_category)
    if selected_skill and any(selected_skill == f for f, _ in GUITAR_SKILL_FIELDS):
        qs = qs.filter(**{selected_skill: True})

    total_mins = qs.aggregate(t=Sum('duration'))['t'] or 0

    return render(request, 'hobbies/guitar_history.html', {
        'sessions': qs,
        'category_choices': GUITAR_CATEGORY_CHOICES,
        'skill_fields': GUITAR_SKILL_FIELDS,
        'selected_category': selected_category,
        'selected_skill': selected_skill,
        'total_fmt': _fmt_duration(total_mins),
        'total_count': qs.count(),
    })


@login_required
def guitar_edit(request, pk):
    entry = get_object_or_404(GuitarSession, pk=pk, user=request.user)

    if request.method == 'POST':
        try:
            d, t, cat, dur, desc, skills = _parse_session_post(request)
            entry.date = d
            entry.time = t
            entry.category = cat
            entry.duration = dur
            entry.description = desc
            for field, checked in skills.items():
                setattr(entry, field, checked)
            entry.save()
            return redirect('guitar_history')
        except (ValueError, TypeError):
            messages.error(request, 'Please check your inputs and try again.')

    skill_fields_with_state = [
        (field, label, getattr(entry, field)) for field, label in GUITAR_SKILL_FIELDS
    ]
    return render(request, 'hobbies/guitar_edit.html', {
        'entry': entry,
        'category_choices': GUITAR_CATEGORY_CHOICES,
        'skill_fields_with_state': skill_fields_with_state,
    })


@login_required
def guitar_delete(request, pk):
    entry = get_object_or_404(GuitarSession, pk=pk, user=request.user)
    if request.method == 'POST':
        entry.delete()
    return redirect('guitar_history')


@login_required
def book_delete(request, pk):
    book = get_object_or_404(Book, pk=pk, user=request.user)

    if request.method == 'POST':
        book.delete()
        return redirect('reading_list')

    return render(request, 'hobbies/book_confirm_delete.html', {'book': book})
