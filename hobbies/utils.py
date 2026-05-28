import os
import urllib.request
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


def download_cover(cover_url: str, book_id: int) -> str:
    if not cover_url:
        return ''

    url_path = cover_url.split('?')[0].rstrip('/')
    ext = os.path.splitext(url_path)[1].lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
        ext = '.jpg'

    storage_path = f"book_covers/{book_id}{ext}"

    try:
        req = urllib.request.Request(cover_url, headers={'User-Agent': 'HomelabHub/1.0 (jaysuzi5@gmail.com)'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        if default_storage.exists(storage_path):
            default_storage.delete(storage_path)
        default_storage.save(storage_path, ContentFile(data))
        return storage_path
    except Exception:
        return ''
