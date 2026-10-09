from django.contrib import admin
from apps.payments.models import Payment

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('reference', 'subscription', 'amount', 'currency', 'status', 'provider_reference', 'created_at')
    list_filter = ('status', 'currency', 'created_at')
    search_fields = ('reference', 'provider_reference', 'subscription__customer__email')
    ordering = ('-created_at',)
    list_select_related = ('subscription', 'subscription__customer')
