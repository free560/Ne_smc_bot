"""
apps/accounts/tests/test_accounts.py
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import AuditLog, Role, UserProfile

User = get_user_model()


class UserProfileSignalTests(TestCase):
    def test_profile_created_automatically(self):
        user = User.objects.create_user(username="negos", password="testpass123")
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        self.assertEqual(user.profile.role, Role.TRADER)

    def test_can_trade_property(self):
        user = User.objects.create_user(username="viewer1", password="testpass123")
        user.profile.role = Role.VIEWER
        user.profile.save()
        self.assertFalse(user.profile.can_trade)

        user.profile.role = Role.ADMIN
        user.profile.save()
        self.assertTrue(user.profile.can_trade)


class LoginAuditTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="negos", password="testpass123")
        self.client = Client()

    def test_successful_login_is_audited(self):
        self.client.post(reverse("accounts:login"), {"username": "negos", "password": "testpass123"})
        self.assertTrue(AuditLog.objects.filter(action="LOGIN", user=self.user).exists())

    def test_failed_login_is_audited(self):
        self.client.post(reverse("accounts:login"), {"username": "negos", "password": "wrongpass"})
        self.assertTrue(AuditLog.objects.filter(action="LOGIN_FAILED").exists())
        entry = AuditLog.objects.filter(action="LOGIN_FAILED").first()
        self.assertIsNone(entry.user)

    def test_logout_is_audited(self):
        self.client.login(username="negos", password="testpass123")
        self.client.post(reverse("accounts:logout"))
        self.assertTrue(AuditLog.objects.filter(action="LOGOUT", user=self.user).exists())

    def test_audit_log_view_requires_login(self):
        response = self.client.get(reverse("accounts:audit_log"))
        self.assertEqual(response.status_code, 302)  # redirection vers login

    def test_audit_log_view_accessible_when_logged_in(self):
        self.client.login(username="negos", password="testpass123")
        response = self.client.get(reverse("accounts:audit_log"))
        self.assertEqual(response.status_code, 200)
