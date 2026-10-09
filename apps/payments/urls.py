from django.urls import path
from apps.payments.views import PaymentWebhookView

urlpatterns = [
    path('webhook/', PaymentWebhookView.as_view(), name='payment-webhook'),
]
