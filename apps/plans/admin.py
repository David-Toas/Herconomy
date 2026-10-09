from django.contrib import admin
from apps.plans.models import Plan

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'provider', 'price', 'billing_interval', 'is_active', 'created_at')
    list_filter = ('billing_interval', 'is_active', 'created_at')
    search_fields = ('name', 'description', 'provider__email')
    ordering = ('-created_at',)
    list_select_related = ('provider',)
