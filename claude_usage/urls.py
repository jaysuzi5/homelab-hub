from django.urls import path
from . import views

urlpatterns = [
    path("", views.overview, name="claude_usage_overview"),
    path("history/", views.history, name="claude_usage_history"),
    path("by-project/", views.by_project, name="claude_usage_by_project"),
]
