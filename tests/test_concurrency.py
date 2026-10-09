from decimal import Decimal
from unittest.mock import patch
import concurrent.futures
from django.test import TransactionTestCase
from apps.users.models import User, Role
from apps.plans.models import Plan, BillingInterval
from apps.subscriptions.models import Subscription, SubscriptionStatus
from apps.subscriptions.services import create_subscription_with_payment
from apps.payments.models import Payment, PaymentStatus
from apps.payments.services import process_payment_webhook

class ConcurrencyAndIntegrityTests(TransactionTestCase):
    """
    Tests proving concurrency defense using TransactionTestCase and ThreadPoolExecutor.
    Verifies that simultaneous worker threads cannot violate uniqueness constraints
    or cause double-crediting.
    """
    def setUp(self):
        self.provider = User.objects.create_user(
            email="concurrency_provider@example.com",
            password="Password123!",
            role=Role.PROVIDER
        )
        self.customer = User.objects.create_user(
            email="concurrency_customer@example.com",
            password="Password123!",
            role=Role.CUSTOMER
        )
        self.plan = Plan.objects.create(
            provider=self.provider,
            name="Concurrent High Demand Plan",
            price=Decimal("100.00"),
            billing_interval=BillingInterval.MONTHLY,
            is_active=True
        )

    def test_concurrent_subscription_creation_prevented(self):
        """
        Two worker threads simultaneously attempt to subscribe the same customer
        to the exact same plan.
        
        Expected outcome:
        - Exactly 1 succeeds.
        - Exactly 1 fails with SubscriptionConflictError.
        - Exactly 1 Subscription record exists in the DB.
        """
        def attempt_subscription():
            try:
                return {"success": True, "result": create_subscription_with_payment(self.customer, self.plan.id)}
            except Exception as e:
                return {"success": False, "error": str(e)}

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(attempt_subscription)
            future2 = executor.submit(attempt_subscription)
            results = [future1.result(), future2.result()]

        successes = [r for r in results if r["success"]]
        failures = [r for r in results if not r["success"]]

        self.assertEqual(len(successes), 1, "Exactly one subscription creation must succeed.")
        self.assertEqual(len(failures), 1, "The second concurrent attempt must fail.")

        # Verify database integrity: only 1 subscription exists for this customer and plan
        sub_count = Subscription.objects.filter(customer=self.customer, plan=self.plan).count()
        self.assertEqual(sub_count, 1, "Database must never contain duplicate subscriptions.")

    @patch('apps.payments.services.send_payment_notification_email.delay')
    def test_concurrent_webhook_processing_race_condition_safe(self, mock_email_delay):
        """
        Two parallel worker threads attempt to process the identical payment webhook simultaneously.
        
        Expected outcome:
        - Both threads complete without deadlock or database integrity violation.
        - The payment is marked SUCCESS.
        - The subscription is marked ACTIVE.
        - Email notification is triggered exactly once.
        """
        sub = Subscription.objects.create(
            customer=self.customer,
            plan=self.plan,
            status=SubscriptionStatus.PENDING
        )
        payment = Payment.objects.create(
            subscription=sub,
            amount=Decimal("100.00"),
            currency='USD',
            status=PaymentStatus.PENDING
        )

        payload = {
            "event": "payment.success",
            "reference": payment.reference,
            "provider_reference": "CONCURRENT-STRIPE-1",
            "amount": "100.00"
        }

        def trigger_webhook():
            try:
                return {"success": True, "data": process_payment_webhook(payload)}
            except Exception as e:
                return {"success": False, "error": str(e)}

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(trigger_webhook)
            future2 = executor.submit(trigger_webhook)
            results = [future1.result(), future2.result()]

        successful_results = [r["data"] for r in results if r["success"]]
        self.assertGreaterEqual(len(successful_results), 1, "At least one thread must successfully process the webhook.")
        self.assertTrue(any(r["status"] == "processed" for r in successful_results))
        
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.SUCCESS)

        sub.refresh_from_db()
        self.assertEqual(sub.status, SubscriptionStatus.ACTIVE)

        # Email task must have been queued at most once
        self.assertEqual(mock_email_delay.call_count, 1)
