import logging
from celery import shared_task
from django.utils import timezone
from apps.subscriptions.models import Subscription, SubscriptionStatus

logger = logging.getLogger(__name__)

@shared_task
def check_and_expire_subscriptions():
    """
    Scheduled background task executed periodically via Celery Beat.
    Identifies ACTIVE subscriptions whose end_date has passed and updates them to EXPIRED.
    Uses bulk update to avoid loading thousands of objects into memory.
    """
    now = timezone.now()
    expired_qs = Subscription.objects.filter(
        status=SubscriptionStatus.ACTIVE,
        end_date__lte=now
    )
    count = expired_qs.count()

    if count > 0:
        updated_count = expired_qs.update(
            status=SubscriptionStatus.EXPIRED,
            updated_at=now
        )
        logger.info(f"[EXPIRY TASK] Marked {updated_count} subscriptions as EXPIRED at {now.isoformat()}.")
        return f"Expired {updated_count} subscriptions."

    logger.debug("[EXPIRY TASK] No expired subscriptions found.")
    return "0 subscriptions expired."
