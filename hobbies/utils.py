import os
import urllib.request
from django.conf import settings


def download_cover(cover_url: str, book_id: int) -> str:
    """
    Download a book cover from cover_url, save it locally under
    MEDIA_ROOT/book_covers/<book_id>.<ext>, and return the relative
    path (suitable for storing in Book.cover_local).

    Returns an empty string on failure.
    """
    if not cover_url:
        return ''

    covers_dir = os.path.join(settings.MEDIA_ROOT, 'book_covers')
    os.makedirs(covers_dir, exist_ok=True)

    # Determine extension from URL (default jpg)
    url_path = cover_url.split('?')[0].rstrip('/')
    ext = os.path.splitext(url_path)[1].lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
        ext = '.jpg'

    filename = f"{book_id}{ext}"
    local_path = os.path.join(covers_dir, filename)
    relative_path = f"book_covers/{filename}"

    try:
        req = urllib.request.Request(
            cover_url,
            headers={'User-Agent': 'HomeLab-Hub/1.0'},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        with open(local_path, 'wb') as f:
            f.write(data)
        return relative_path
    except Exception:
        return ''
