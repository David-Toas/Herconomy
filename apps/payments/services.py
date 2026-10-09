import logging
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError, NotFound
from apps.payments.models import Payment, PaymentStatus
from apps.subscriptions.models import Subscription, SubscriptionStatus
from apps.plans.models import BillingInterval
from apps.payments.tasks import send_payment_notification_email

logger = logging.getLogger(__name__)

class PaymentProcessingResult:
    ALREADY_PROCESSED = "already_processed"
    PROCESSED = "processed"
    FAILED = "failed"

def process_payment_webhook(payload: dict) -> dict:
    """
    Processes incoming payment webhook events with strict concurrency control and idempotency.

    Key Guarantees:
    1. Row-level Lock: Uses select_for_update() on the Payment record to serialize concurrent webhooks.
    2. Idempotency: If the payment is already SUCCESS, returns immediately with 200 OK
       without re-calculating dates or dispatching duplicate notification emails.
    3. Amount Verification: Verifies that the payload amount matches the payment amount exactly.
    4. Transaction Safety: Updates Payment and Subscription atomically.
    5. Post-Commit Dispatch: Enqueues the email notification using transaction.on_commit(),
       ensuring the task is only dispatched if the database transaction successfully commits.
    """
    event = payload.get('event')
    reference = payload.get('reference')
    provider_reference = payload.get('provider_reference')
    raw_amount = payload.get('amount')

    if not event or not reference or raw_amount is None:
        raise ValidationError("Missing required webhook fields: event, reference, or amount.")

    try:
        amount = Decimal(str(raw_amount))
    except Exception:
        raise ValidationError("Invalid amount format in webhook payload.")

    with transaction.atomic():
        # Lock the payment row to prevent race conditions across parallel workers
        try:
            payment = Payment.objects.select_for_update().select_related(
                'subscription', 'subscription__plan'
            ).get(reference=reference)
        except Payment.DoesNotExist:
            raise NotFound(f"Payment with reference '{reference}' not found.")

        # IDEMPOTENCY CHECK
        if payment.status == PaymentStatus.SUCCESS:
            logger.info(f"[WEBHOOK IDEMPOTENT] Payment {reference} is already SUCCESS. Skipping side effects.")
            return {
                "status": PaymentProcessingResult.ALREADY_PROCESSED,
                "message": "Payment has already been successfully processed.",
                "reference": payment.reference,
            }

        # Verify amount matches registered charge
        if payment.amount != amount:
            logger.error(f"[WEBHOOK ERROR] Amount mismatch for {reference}. Expected {payment.amount}, received {amount}")
            raise ValidationError(
                f"Amount mismatch: Expected {payment.amount}, received {amount}."
            )

        if event == 'payment.success':
            # Update Payment Record
            payment.status = PaymentStatus.SUCCESS
            payment.provider_reference = provider_reference or payment.provider_reference
            payment.save(update_fields=['status', 'provider_reference', 'updated_at'])

            # Activate Subscription and set validity dates
            sub = payment.subscription
            now = timezone.now()
            sub.status = SubscriptionStatus.ACTIVE
            sub.start_date = now

            if sub.plan.billing_interval == BillingInterval.MONTHLY:
                sub.end_date = now + relativedelta(months=1)
            else:
                sub.end_date = now + relativedelta(years=1)

            sub.next_billing_date = sub.end_date
            sub.save(update_fields=['status', 'start_date', 'end_date', 'next_billing_date', 'updated_at'])

            logger.info(
                f"[WEBHOOK SUCCESS] Payment {reference} confirmed. Subscription #{sub.id} "
                f"activated until {sub.end_date.isoformat()}."
            )

            # CRITICAL: Asynchronous notification dispatched only after DB commit
            transaction.on_commit(
                lambda: send_payment_notification_email.delay(payment.id)
            )

            return {
                "status": PaymentProcessingResult.PROCESSED,
                "message": "Payment succeeded and subscription activated.",
                "reference": payment.reference,
            }

        elif event == 'payment.failed':
            payment.status = PaymentStatus.FAILED
            payment.provider_reference = provider_reference or payment.provider_reference
            payment.save(update_fields=['status', 'provider_reference', 'updated_at'])

            logger.warning(f"[WEBHOOK FAILED] Payment {reference} marked as FAILED.")
            return {
                "status": PaymentProcessingResult.FAILED,
                "message": "Payment marked as failed.",
                "reference": payment.reference,
            }

        else:
            raise ValidationError(f"Unsupported event type: '{event}'.")
