from django.contrib import admin
from .models import HubConfig

@admin.register(HubConfig)
class HubConfigAdmin(admin.ModelAdmin):
    list_display = ("key", "value")
    search_fields = ("key",)
