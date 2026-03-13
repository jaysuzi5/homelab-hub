from django.contrib import admin
from .models import PortfolioAccount, PortfolioSnapshot


@admin.register(PortfolioAccount)
class PortfolioAccountAdmin(admin.ModelAdmin):
    list_display = ['name', 'account_type', 'institution', 'is_taxable', 'is_active', 'get_latest_balance', 'created_date']
    list_filter = ['account_type', 'is_taxable', 'is_active']
    search_fields = ['name', 'institution']
    ordering = ['account_type', 'name']


@admin.register(PortfolioSnapshot)
class PortfolioSnapshotAdmin(admin.ModelAdmin):
    list_display = ['account', 'snapshot_date', 'balance', 'created_date']
    list_filter = ['account', 'snapshot_date']
    search_fields = ['account__name']
    ordering = ['-snapshot_date', 'account__name']
    date_hierarchy = 'snapshot_date'
