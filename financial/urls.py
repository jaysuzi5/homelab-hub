from django.urls import path
from . import views

urlpatterns = [
    path('', views.retirement, name='retirement_dashboard'),
]
