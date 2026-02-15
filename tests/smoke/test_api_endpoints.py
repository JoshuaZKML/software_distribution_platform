# FILE: tests/smoke/test_api_endpoints.py
from django.urls import reverse, NoReverseMatch
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from tests.factories import UserFactory, SoftwareFactory

User = get_user_model()


class SmokeTests(APITestCase):
    def setUp(self):
        # Create a regular user for API tests
        self.user = UserFactory()
        
        # Create a super admin user for health check tests (requires is_staff=True and role=SUPER_ADMIN)
        password = "testpass123"
        self.super_admin = User.objects.create_user(
            email="superadmin@example.com",
            password=password,
            is_staff=True,
            is_verified=True,
            role=User.Role.SUPER_ADMIN
        )
        self.super_admin_password = password
        
        self.software = SoftwareFactory()
        self.client.force_authenticate(user=self.user)

    def test_health_check(self):
        """Health check JSON endpoint should be accessible by super admins and return 200."""
        # Login as super admin with actual credentials (force_authenticate doesn't work with @staff_member_required)
        self.client.logout()
        self.client.login(email="superadmin@example.com", password="testpass123")
        
        response = self.client.get('/health/json/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('status', response.json())
        self.assertIn('components', response.json())

    def test_user_list(self):
        """If the user list endpoint exists, it should return 200."""
        try:
            url = reverse('user-list')
        except NoReverseMatch:
            self.skipTest("URL 'user-list' not configured")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        if response.data:
            self.assertIn('results', response.data)  # if paginated

    def test_software_list(self):
        """If the software list endpoint exists, it should return 200."""
        try:
            url = reverse('software-list')
        except NoReverseMatch:
            self.skipTest("URL 'software-list' not configured")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_software_detail(self):
        """If the software detail endpoint exists, it should return 200."""
        try:
            url = reverse('software-detail', args=[self.software.id])
        except NoReverseMatch:
            self.skipTest("URL 'software-detail' not configured")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.software.id))

    def test_unauthenticated_access(self):
        """Authenticated-only endpoints should reject unauthenticated requests."""
        self.client.force_authenticate(user=None)
        try:
            url = reverse('software-list')
        except NoReverseMatch:
            self.skipTest("URL 'software-list' not configured")
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])