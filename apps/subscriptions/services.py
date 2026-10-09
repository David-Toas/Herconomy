import logging
from django.db import transaction, IntegrityError
from rest_framework.exceptions import ValidationError, PermissionDenied
from apps.plans.models import Plan
from apps.subscriptions.models import Subscription, SubscriptionStatus
from apps.payments.models import Payment, PaymentStatus

logger = logging.getLogger(__name__)

class SubscriptionConflictError(ValidationError):
    status_code = 409
    default_detail = "An active or pending subscription for this plan already exists."

def create_subscription_with_payment(customer, plan_id: int) -> dict:
    """
    Atomically creates a subscription in PENDING status and generates an associated Payment record.
    
    Concurrency Defenses:
    1. Uses transaction.atomic() to ensure both records are created together or not at all.
    2. Uses select_for_update() on the Plan row to lock it while reading its active state,
       preventing race conditions where a provider deactivates a plan during checkout.
    3. Leverages PostgreSQL partial UniqueConstraint to prevent duplicate ACTIVE/PENDING subscriptions
       even under simultaneous concurrent requests.
    """
    with transaction.atomic():
        # 1. Row-level lock on Plan
        try:
            plan = Plan.objects.select_for_update().get(id=plan_id)
        except Plan.DoesNotExist:
            raise ValidationError({"plan_id": "Plan does not exist."})

        # 2. Inactive plan check
        if not plan.is_active:
            raise ValidationError({"plan_id": "Cannot subscribe to an inactive plan."})

        # 3. Application-level check
        existing_sub = Subscription.objects.filter(
            customer=customer,
            plan=plan,
            status__in=[SubscriptionStatus.ACTIVE, SubscriptionStatus.PENDING]
        ).exists()

        if existing_sub:
            raise SubscriptionConflictError(
                "You already have an active or pending subscription to this plan."
            )

        # 4. Create Subscription in PENDING status
        try:
            subscription = Subscription.objects.create(
                customer=customer,
                plan=plan,
                status=SubscriptionStatus.PENDING
            )
        except IntegrityError:
            # Caught if a concurrent transaction committed milliseconds prior
            raise SubscriptionConflictError(
                "Concurrent request detected: subscription already exists."
            )

        # 5. Create Payment record in PENDING status
        payment = Payment.objects.create(
            subscription=subscription,
            amount=plan.price,
            currency='USD',
            status=PaymentStatus.PENDING
        )

        logger.info(
            f"Created PENDING subscription #{subscription.id} and Payment {payment.reference} "
            f"for customer {customer.email}"
        )

        return {
            "subscription_id": subscription.id,
            "payment_reference": payment.reference,
            "status": subscription.status,
            "amount": str(payment.amount),
            "currency": payment.currency,
        }


def cancel_subscription(subscription: Subscription, user) -> Subscription:
    """
    Cancels an active or pending subscription.
    Ensures only the customer who owns the subscription (or admin) can cancel.
    """
    with transaction.atomic():
        sub = Subscription.objects.select_for_update().get(id=subscription.id)

        if sub.customer != user and not (user.is_staff or user.role == 'ADMIN'):
            raise PermissionDenied("You do not have permission to cancel this subscription.")

        if sub.status == SubscriptionStatus.CANCELLED:
            return sub

        sub.status = SubscriptionStatus.CANCELLED
        sub.save(update_fields=['status', 'updated_at'])
        logger.info(f"Subscription #{sub.id} cancelled by user {user.email}")
        return sub
