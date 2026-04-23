from django.contrib import admin
from .models import Book, GuitarSession


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'date_read', 'pages')
    list_filter = ('date_read',)
    search_fields = ('title', 'author')
    ordering = ('-date_read',)


@admin.register(GuitarSession)
class GuitarSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'time', 'category', 'duration', 'description')
    list_filter = ('category', 'skill_lead', 'skill_chords', 'skill_finger_picking', 'skill_strumming', 'skill_scales')
    search_fields = ('description',)
    ordering = ('-date', '-time')
    date_hierarchy = 'date'
