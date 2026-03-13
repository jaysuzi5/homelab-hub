import urllib.request
import urllib.parse
import json
from django.contrib.auth import get_user_model
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from datetime import date
from .models import Book

User = get_user_model()


@login_required
def reading_list(request):
    # Allow viewing another user's list via ?reader=username
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

    # Build list of other readers to link to
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
def book_add(request):
    if request.method == 'POST':
        date_read = request.POST.get('date_read')
        title = request.POST.get('title', '').strip()
        author = request.POST.get('author', '').strip()
        pages_raw = request.POST.get('pages', '').strip()
        cover_url = request.POST.get('cover_url', '').strip()
        open_library_key = request.POST.get('open_library_key', '').strip()

        pages = int(pages_raw) if pages_raw.isdigit() else None

        Book.objects.create(
            user=request.user,
            date_read=date_read,
            title=title,
            author=author,
            pages=pages,
            cover_url=cover_url,
            open_library_key=open_library_key,
        )
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
def book_delete(request, pk):
    # Only allow deleting your own books
    book = get_object_or_404(Book, pk=pk, user=request.user)

    if request.method == 'POST':
        book.delete()
        return redirect('reading_list')

    return render(request, 'hobbies/book_confirm_delete.html', {'book': book})
