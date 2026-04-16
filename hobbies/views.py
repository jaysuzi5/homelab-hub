import urllib.request
import urllib.parse
import json
from django.contrib.auth import get_user_model
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from datetime import date
from .models import Book
from .utils import download_cover
from dashboard.services.darts import collect_dart_summary

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
def book_delete(request, pk):
    book = get_object_or_404(Book, pk=pk, user=request.user)

    if request.method == 'POST':
        book.delete()
        return redirect('reading_list')

    return render(request, 'hobbies/book_confirm_delete.html', {'book': book})
