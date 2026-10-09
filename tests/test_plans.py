from decimal import Decimal
from django.urls import reverse
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase
from apps.users.models import User, Role
from apps.plans.models import Plan, BillingInterval

class PlanTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.plans_url = reverse('plan-list')
        self.provider1 = User.objects.create_user(
            email="provider1@example.com",
            password="Password123!",
            role=Role.PROVIDER
        )
        self.provider2 = User.objects.create_user(
            email="provider2@example.com",
            password="Password123!",
            role=Role.PROVIDER
        )
        self.customer = User.objects.create_user(
            email="customer@example.com",
            password="Password123!",
            role=Role.CUSTOMER
        )

    def test_provider_creates_plan_success(self):
        """Test that an authenticated provider can create a plan."""
        self.client.force_authenticate(user=self.provider1)
        payload = {
            "name": "Pro Monthly Plan",
            "description": "Full access to features",
            "price": "29.99",
            "billing_interval": "MONTHLY"
        }
        response = self.client.post(self.plans_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], "Pro Monthly Plan")
        self.assertEqual(Decimal(response.data['price']), Decimal("29.99"))
        self.assertEqual(response.data['provider_id'], self.provider1.id)

    def test_customer_cannot_create_plan(self):
        """Test that a customer is forbidden from creating plans."""
        self.client.force_authenticate(user=self.customer)
        payload = {
            "name": "Customer Created Plan",
            "price": "10.00",
            "billing_interval": "MONTHLY"
        }
        response = self.client.post(self.plans_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_provider_cannot_modify_other_providers_plan(self):
        """Test that provider 2 cannot edit provider 1's plan."""
        plan1 = Plan.objects.create(
            provider=self.provider1,
            name="Provider 1 Original",
            price=Decimal("50.00"),
            billing_interval=BillingInterval.MONTHLY
        )
        detail_url = reverse('plan-detail', kwargs={'pk': plan1.id})

        self.client.force_authenticate(user=self.provider2)
        patch_payload = {"name": "Malicious Hijack"}
        response = self.client.patch(detail_url, patch_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        plan1.refresh_from_db()
        self.assertEqual(plan1.name, "Provider 1 Original")

    def test_owner_provider_can_modify_own_plan(self):
        """Test that provider 1 can successfully update their own plan."""
        plan1 = Plan.objects.create(
            provider=self.provider1,
            name="Old Name",
            price=Decimal("50.00"),
            billing_interval=BillingInterval.MONTHLY
        )
        detail_url = reverse('plan-detail', kwargs={'pk': plan1.id})

        self.client.force_authenticate(user=self.provider1)
        patch_payload = {"name": "Updated Name"}
        response = self.client.patch(detail_url, patch_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], "Updated Name")

    def test_plans_caching_and_invalidation(self):
        """Test public plan list caching and invalidation on update."""
        self.client.force_authenticate(user=self.customer)
        plan = Plan.objects.create(
            provider=self.provider1,
            name="Cached Plan",
            price=Decimal("19.99"),
            billing_interval=BillingInterval.MONTHLY
        )

        # First request populates cache
        resp1 = self.client.get(self.plans_url)
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp1.data['results']), 1)

        # Provider updates the plan
        self.client.force_authenticate(user=self.provider1)
        detail_url = reverse('plan-detail', kwargs={'pk': plan.id})
        self.client.patch(detail_url, {"name": "New Cached Name"}, format='json')

        # Customer reads again and gets fresh invalidated data
        self.client.force_authenticate(user=self.customer)
        resp2 = self.client.get(self.plans_url)
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data['results'][0]['name'], "New Cached Name")
