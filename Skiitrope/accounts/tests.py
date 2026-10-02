from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class UserModelTests(TestCase):
    def test_create_user_with_email(self):
        user = User.objects.create_user(email="rider@example.com", password="snowday123")
        self.assertEqual(user.email, "rider@example.com")
        self.assertTrue(user.check_password("snowday123"))
        self.assertFalse(user.is_staff)
        self.assertTrue(user.is_active)

    def test_email_unique(self):
        User.objects.create_user(email="rider@example.com", password="snowday123")
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            User.objects.create_user(email="rider@example.com", password="other-pass-1")

    def test_create_superuser(self):
        admin = User.objects.create_superuser(email="boss@example.com", password="snowday123")
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_full_name(self):
        user = User.objects.create_user(
            email="ava@example.com",
            password="snowday123",
            first_name="Ava",
            last_name="Rider",
        )
        self.assertEqual(user.get_full_name(), "Ava Rider")


class AuthPageTests(TestCase):
    def test_login_page_renders(self):
        response = self.client.get(reverse("account_login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Google")

    def test_signup_page_renders(self):
        response = self.client.get(reverse("account_signup"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Google")
