from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class RegistrationTests(TestCase):
    def test_registration_logs_in_new_user(self):
        response = self.client.post(reverse("register"), {
            "username": "student",
            "password1": "Study-Window-2048!",
            "password2": "Study-Window-2048!",
        })
        self.assertRedirects(response, reverse("home"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), get_user_model().objects.get(username="student").pk)

    def test_weak_password_is_rejected(self):
        response = self.client.post(reverse("register"), {
            "username": "student", "password1": "123", "password2": "123",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.exists())
