import logging
from celery import shared_task
from django.core.mail import send_mail
from apps.payments.models import Payment

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def send_payment_notification_email(self, payment_id: int):
    """
    Asynchronous task simulating sending an email receipt to the customer
    upon successful payment processing.
    """
    try:
        payment = Payment.objects.select_related(
            'subscription__customer',
            'subscription__plan'
        ).get(id=payment_id)

        customer = payment.subscription.customer
        plan = payment.subscription.plan

        subject = f"Payment Confirmation: {plan.name}"
        message = (
            f"Hello {customer.first_name or customer.email},\n\n"
            f"Your payment of {payment.currency} {payment.amount} for '{plan.name}' "
            f"was successful!\n"
            f"Payment Reference: {payment.reference}\n"
            f"Subscription Status: {payment.subscription.status}\n\n"
            f"Thank you for your business!"
        )

        logger.info(
            f"[EMAIL DISPATCH] Successfully simulated email to {customer.email} "
            f"for Payment Ref: {payment.reference} (Amount: {payment.amount})"
        )
        return f"Notification sent to {customer.email}"

    except Payment.DoesNotExist:
        logger.error(f"[EMAIL TASK ERROR] Payment ID {payment_id} does not exist.")
        return "Payment not found"
    except Exception as exc:
        logger.exception(f"[EMAIL TASK RETRY] Failed to send email for Payment {payment_id}: {exc}")
        raise self.retry(exc=exc)
