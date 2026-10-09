import uuid
from django.db import models
from apps.subscriptions.models import Subscription

class PaymentStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    SUCCESS = 'SUCCESS', 'Success'
    FAILED = 'FAILED', 'Failed'

def generate_payment_reference():
    """Generates unique payment reference, e.g., PAY-8F92A1B7C3D4"""
    return f"PAY-{uuid.uuid4().hex[:16].upper()}"

class Payment(models.Model):
    """Payment record associated with a subscription attempt."""
    reference = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        default=generate_payment_reference
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='payments',
        db_index=True
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True
    )
    provider_reference = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['subscription', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"{self.reference} - {self.amount} {self.currency} [{self.status}]"
