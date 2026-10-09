from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from apps.users.models import User, Role

class AuthTests(APITestCase):
    def setUp(self):
        self.register_url = reverse('auth-register')
        self.login_url = reverse('auth-login')
        self.me_url = reverse('auth-me')
        self.user_password = "SecurePassword123!"

    def test_customer_registration_success(self):
        """Test successful customer registration with JWT tokens returned."""
        payload = {
            "email": "customer@example.com",
            "password": self.user_password,
            "first_name": "Jane",
            "last_name": "Doe",
            "role": "CUSTOMER"
        }
        response = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('tokens', response.data)
        self.assertIn('access', response.data['tokens'])
        self.assertEqual(response.data['user']['email'], "customer@example.com")
        self.assertEqual(response.data['user']['role'], "CUSTOMER")

    def test_provider_registration_success(self):
        """Test successful service provider registration."""
        payload = {
            "email": "provider@example.com",
            "password": self.user_password,
            "role": "PROVIDER"
        }
        response = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['user']['role'], "PROVIDER")

    def test_duplicate_email_registration_fails(self):
        """Test that registering an existing email returns 400 validation error."""
        User.objects.create_user(email="duplicate@example.com", password=self.user_password)
        payload = {
            "email": "duplicate@example.com",
            "password": self.user_password,
            "role": "CUSTOMER"
        }
        response = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_login_success_and_jwt_tokens(self):
        """Test login with valid credentials returns JWT tokens."""
        User.objects.create_user(email="login@example.com", password=self.user_password)
        payload = {
            "email": "login@example.com",
            "password": self.user_password
        }
        response = self.client.post(self.login_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('tokens', response.data)
        self.assertIn('access', response.data['tokens'])
        self.assertIn('refresh', response.data['tokens'])

    def test_login_invalid_credentials_fails(self):
        """Test login with wrong password fails with 400."""
        User.objects.create_user(email="wrong@example.com", password=self.user_password)
        payload = {
            "email": "wrong@example.com",
            "password": "WrongPassword!"
        }
        response = self.client.post(self.login_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_cannot_modify_own_role(self):
        """Test that user cannot escalate privileges/change their role via /api/auth/me/."""
        customer = User.objects.create_user(
            email="victim@example.com",
            password=self.user_password,
            role=Role.CUSTOMER
        )
        self.client.force_authenticate(user=customer)

        # Attempt to upgrade self to ADMIN
        patch_payload = {
            "role": "ADMIN",
            "first_name": "Hacker"
        }
        response = self.client.patch(self.me_url, patch_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify role was NOT updated in DB
        customer.refresh_from_db()
        self.assertEqual(customer.role, Role.CUSTOMER)
        self.assertEqual(customer.first_name, "Hacker")
