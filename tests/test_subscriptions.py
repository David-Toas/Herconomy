from decimal import Decimal
from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from apps.users.models import User, Role
from apps.plans.models import Plan, BillingInterval
from apps.subscriptions.models import Subscription, SubscriptionStatus
from apps.subscriptions.tasks import check_and_expire_subscriptions

class SubscriptionTests(APITestCase):
    def setUp(self):
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
        self.other_customer = User.objects.create_user(
            email="other@example.com",
            password="Password123!",
            role=Role.CUSTOMER
        )
        self.plan = Plan.objects.create(
            provider=self.provider,
            name="Monthly Gold",
            price=Decimal("49.99"),
            billing_interval=BillingInterval.MONTHLY,
            is_active=True
        )
        self.subscriptions_url = reverse('subscription-list')

    def test_successful_subscription_creation_in_pending_state(self):
        """Test subscribing creates PENDING subscription and returns unique payment reference."""
        self.client.force_authenticate(user=self.customer)
        response = self.client.post(self.subscriptions_url, {"plan_id": self.plan.id}, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('subscription_id', response.data)
        self.assertIn('payment_reference', response.data)
        self.assertEqual(response.data['status'], 'PENDING')
        self.assertTrue(response.data['payment_reference'].startswith('PAY-'))

        sub = Subscription.objects.get(id=response.data['subscription_id'])
        self.assertEqual(sub.status, SubscriptionStatus.PENDING)
        self.assertEqual(sub.customer, self.customer)
        self.assertEqual(sub.plan, self.plan)

    def test_inactive_plan_cannot_receive_subscriptions(self):
        """Test that attempting to subscribe to an inactive plan fails."""
        self.plan.is_active = False
        self.plan.save()

        self.client.force_authenticate(user=self.customer)
        response = self.client.post(self.subscriptions_url, {"plan_id": self.plan.id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_active_or_pending_subscription_blocked(self):
        """Test that customer cannot create two pending/active subscriptions to the same plan."""
        self.client.force_authenticate(user=self.customer)
        # First subscription succeeds
        resp1 = self.client.post(self.subscriptions_url, {"plan_id": self.plan.id}, format='json')
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)

        # Second attempt must be rejected with 409 Conflict
        resp2 = self.client.post(self.subscriptions_url, {"plan_id": self.plan.id}, format='json')
        self.assertEqual(resp2.status_code, status.HTTP_409_CONFLICT)

    def test_customer_can_cancel_subscription(self):
        """Test that a customer can cancel their active/pending subscription."""
        sub = Subscription.objects.create(
            customer=self.customer,
            plan=self.plan,
            status=SubscriptionStatus.ACTIVE
        )
        cancel_url = reverse('subscription-cancel', kwargs={'pk': sub.id})

        self.client.force_authenticate(user=self.customer)
        response = self.client.post(cancel_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        sub.refresh_from_db()
        self.assertEqual(sub.status, SubscriptionStatus.CANCELLED)

    def test_other_customer_cannot_cancel_subscription(self):
        """Test that a user cannot cancel another user's subscription."""
        sub = Subscription.objects.create(
            customer=self.customer,
            plan=self.plan,
            status=SubscriptionStatus.ACTIVE
        )
        cancel_url = reverse('subscription-cancel', kwargs={'pk': sub.id})

        self.client.force_authenticate(user=self.other_customer)
        response = self.client.post(cancel_url)
        # Should return 404 because get_queryset isolates customer subscriptions
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_subscription_expiry_task(self):
        """Test the Celery periodic task that identifies expired subscriptions."""
        now = timezone.now()
        # Create an expired subscription (end_date in the past)
        expired_sub = Subscription.objects.create(
            customer=self.customer,
            plan=self.plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now - timedelta(days=32),
            end_date=now - timedelta(days=2)
        )
        # Create an active subscription (end_date in the future)
        active_sub = Subscription.objects.create(
            customer=self.other_customer,
            plan=self.plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now,
            end_date=now + timedelta(days=28)
        )

        # Run periodic task
        result = check_and_expire_subscriptions()

        expired_sub.refresh_from_db()
        active_sub.refresh_from_db()

        self.assertEqual(expired_sub.status, SubscriptionStatus.EXPIRED)
        self.assertEqual(active_sub.status, SubscriptionStatus.ACTIVE)
        self.assertIn("Expired 1 subscriptions", result)
