from django.db import models
from django.conf import settings
from apps.plans.models import Plan

class SubscriptionStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    ACTIVE = 'ACTIVE', 'Active'
    PAST_DUE = 'PAST_DUE', 'Past Due'
    CANCELLED = 'CANCELLED', 'Cancelled'
    EXPIRED = 'EXPIRED', 'Expired'

class Subscription(models.Model):
    """Customer subscription to a provider's plan."""
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscriptions',
        db_index=True
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name='subscriptions',
        db_index=True
    )
    status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.PENDING,
        db_index=True
    )
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True, db_index=True)
    next_billing_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            # Concurrency & integrity guard: Prevents two active or pending subscriptions to the same plan
            models.UniqueConstraint(
                fields=['customer', 'plan'],
                condition=models.Q(status__in=['ACTIVE', 'PENDING']),
                name='unique_active_or_pending_sub_per_customer_plan'
            )
        ]
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['status', 'end_date']),
            models.Index(fields=['plan', 'status']),
        ]

    def __str__(self):
        return f"Subscription #{self.id} - {self.customer.email} -> {self.plan.name} [{self.status}]"

    @property
    def is_active(self):
        return self.status == SubscriptionStatus.ACTIVE
