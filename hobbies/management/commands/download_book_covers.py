from django.core.management.base import BaseCommand
from hobbies.models import Book
from hobbies.utils import download_cover


class Command(BaseCommand):
    help = "Download and cache cover images locally for all books that have a cover_url but no local copy."

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Re-download covers even if a local copy already exists.',
        )

    def handle(self, *args, **options):
        force = options['force']
        books = Book.objects.filter(cover_url__gt='')
        if not force:
            books = books.filter(cover_local='')

        total = books.count()
        self.stdout.write(f"Found {total} book(s) to process.")

        success = 0
        for book in books:
            self.stdout.write(f"  Downloading cover for: {book.title} … ", ending='')
            path = download_cover(book.cover_url, book.pk)
            if path:
                book.cover_local = path
                book.save(update_fields=['cover_local'])
                self.stdout.write(self.style.SUCCESS('OK'))
                success += 1
            else:
                self.stdout.write(self.style.WARNING('FAILED'))

        self.stdout.write(self.style.SUCCESS(f"\nDone: {success}/{total} covers downloaded."))
