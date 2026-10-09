from decimal import Decimal
from unittest.mock import patch
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from apps.users.models import User, Role
from apps.plans.models import Plan, BillingInterval
from apps.subscriptions.models import Subscription, SubscriptionStatus
from apps.payments.models import Payment, PaymentStatus

class PaymentWebhookTests(APITestCase):
    def setUp(self):
        self.webhook_url = reverse('payment-webhook')
        self.provider = User.objects.create_user(
            email="provider@example.com",
            password="Password123!",
            role=Role.PROVIDER
        )
        self.customer = User.objects.create_user(
            email="customer@example.com",
            password="Password123!",
            role=Role.CUSTOMER
        )
        self.plan = Plan.objects.create(
            provider=self.provider,
            name="Monthly Plan",
            price=Decimal("15000.00"),
            billing_interval=BillingInterval.MONTHLY
        )
        self.subscription = Subscription.objects.create(
            customer=self.customer,
            plan=self.plan,
            status=SubscriptionStatus.PENDING
        )
        self.payment = Payment.objects.create(
            subscription=self.subscription,
            amount=Decimal("15000.00"),
            currency='USD',
            status=PaymentStatus.PENDING
        )

    @patch('apps.payments.services.send_payment_notification_email.delay')
    def test_successful_webhook_activates_subscription_and_queues_email(self, mock_email_delay):
        """Test that payment.success webhook activates subscription and queues async email."""
        payload = {
            "event": "payment.success",
            "reference": self.payment.reference,
            "provider_reference": "STRIPE-123456",
            "amount": "15000.00"
        }
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.webhook_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'processed')

        self.payment.refresh_from_db()
        self.subscription.refresh_from_db()

        # Payment status updated
        self.assertEqual(self.payment.status, PaymentStatus.SUCCESS)
        self.assertEqual(self.payment.provider_reference, "STRIPE-123456")

        # Subscription status updated & dates computed
        self.assertEqual(self.subscription.status, SubscriptionStatus.ACTIVE)
        self.assertIsNotNone(self.subscription.start_date)
        self.assertIsNotNone(self.subscription.end_date)
        self.assertEqual(self.subscription.next_billing_date, self.subscription.end_date)

        # Celery email task queued with payment id
        mock_email_delay.assert_called_once_with(self.payment.id)

    @patch('apps.payments.services.send_payment_notification_email.delay')
    def test_webhook_idempotency_prevents_duplicate_side_effects(self, mock_email_delay):
        """
        Critical Test: Sending the exact same successful webhook twice must return HTTP 200,
        leave subscription active, and NOT re-trigger the Celery notification task.
        """
        payload = {
            "event": "payment.success",
            "reference": self.payment.reference,
            "provider_reference": "STRIPE-123456",
            "amount": "15000.00"
        }
        # First call: processes payment
        with self.captureOnCommitCallbacks(execute=True):
            resp1 = self.client.post(self.webhook_url, payload, format='json')

        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        self.assertEqual(resp1.data['status'], 'processed')
        mock_email_delay.assert_called_once()

        self.subscription.refresh_from_db()
        original_end_date = self.subscription.end_date

        # Second call: must be recognized as already processed (idempotent)
        with self.captureOnCommitCallbacks(execute=True):
            resp2 = self.client.post(self.webhook_url, payload, format='json')

        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data['status'], 'already_processed')

        # Assert no duplicate email queued
        mock_email_delay.assert_called_once()

        # Dates should remain untouched
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.end_date, original_end_date)

    def test_failed_webhook_marks_payment_failed(self):
        """Test payment.failed webhook sets payment status to FAILED."""
        payload = {
            "event": "payment.failed",
            "reference": self.payment.reference,
            "provider_reference": "STRIPE-FAILED-99",
            "amount": "15000.00"
        }
        response = self.client.post(self.webhook_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'failed')

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentStatus.FAILED)

        self.subscription.refresh_from_db()
        self.assertNotEqual(self.subscription.status, SubscriptionStatus.ACTIVE)

    def test_invalid_payment_reference_returns_404(self):
        """Test webhook with non-existent reference returns 404."""
        payload = {
            "event": "payment.success",
            "reference": "PAY-NONEXISTENT-9999",
            "amount": "15000.00"
        }
        response = self.client.post(self.webhook_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_amount_mismatch_returns_400(self):
        """Test webhook with wrong amount returns 400 validation error."""
        payload = {
            "event": "payment.success",
            "reference": self.payment.reference,
            "amount": "100.00"  # Mismatch: should be 15000.00
        }
        response = self.client.post(self.webhook_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Amount mismatch", str(response.data))
