from django.contrib import admin
from .models import WeightEntry, ExerciseEntry

@admin.register(WeightEntry)
class WeightEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'weight')
    list_filter = ('user',)
    ordering = ('-date',)

@admin.register(ExerciseEntry)
class ExerciseEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'time', 'activity', 'duration', 'distance_miles')
    list_filter = ('user', 'activity')
    ordering = ('-date', '-time')
