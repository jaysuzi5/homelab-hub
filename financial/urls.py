from django.urls import path
from . import views

urlpatterns = [
    path('', views.retirement, name='retirement_dashboard'),
    path('portfolio/', views.portfolio_overview, name='portfolio_overview'),
    path('accounts/', views.account_list, name='account_list'),
    path('accounts/create/', views.account_create, name='account_create'),
    path('accounts/<int:pk>/edit/', views.account_edit, name='account_edit'),
    path('accounts/<int:pk>/delete/', views.account_delete, name='account_delete'),
    path('accounts/<int:pk>/snapshots/', views.account_snapshots, name='account_snapshots'),
    path('snapshots/create/', views.snapshot_create, name='snapshot_create'),
    path('snapshots/<int:pk>/edit/', views.snapshot_edit, name='snapshot_edit'),
    path('snapshots/<int:pk>/delete/', views.snapshot_delete, name='snapshot_delete'),
    path('electricity/', views.electricity_usage_list, name='electricity_usage_list'),
    path('electricity/create/', views.electricity_usage_create, name='electricity_usage_create'),
    path('electricity/<int:pk>/edit/', views.electricity_usage_edit, name='electricity_usage_edit'),
    path('electricity/<int:pk>/delete/', views.electricity_usage_delete, name='electricity_usage_delete'),
    path('networth/', views.networth_list, name='networth_list'),
    path('networth/create/', views.networth_create, name='networth_create'),
    path('networth/<int:pk>/edit/', views.networth_edit, name='networth_edit'),
    path('networth/<int:pk>/delete/', views.networth_delete, name='networth_delete'),
]
