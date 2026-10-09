from django.contrib import admin
from apps.subscriptions.models import Subscription

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'plan', 'status', 'start_date', 'end_date', 'created_at')
    list_filter = ('status', 'created_at', 'end_date')
    search_fields = ('customer__email', 'plan__name', 'plan__provider__email')
    ordering = ('-created_at',)
    list_select_related = ('customer', 'plan', 'plan__provider')
