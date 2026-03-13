from django.contrib import admin
from .models import Book


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'date_read', 'pages')
    list_filter = ('date_read',)
    search_fields = ('title', 'author')
    ordering = ('-date_read',)
