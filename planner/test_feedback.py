from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import Feedback


class FeedbackTests(TestCase):
    def test_public_feedback_and_cooldown(self):
        user = get_user_model().objects.create_user("feedback-author")
        payload = {"subject": "Идея", "message": "Добавить сценарий", "author": user.pk}
        self.client.post(reverse("feedback"), payload)
        self.client.post(reverse("feedback"), payload)
        self.assertEqual(Feedback.objects.count(), 1)
        self.assertIsNone(Feedback.objects.get().author)

    def test_staff_desk_is_private_and_updates_status(self):
        item = Feedback.objects.create(subject="Закрытая тема", message="Личная заметка")
        student = get_user_model().objects.create_user("feedback-student")
        self.client.force_login(student)
        self.assertEqual(self.client.get(reverse("feedback_desk")).status_code, 302)
        self.client.post(reverse("feedback_desk"), {"pk": item.pk, "status": "closed"})
        item.refresh_from_db();self.assertEqual(item.status, "open")
        admin = get_user_model().objects.create_user("feedback-staff", is_staff=True)
        self.client.force_login(admin)
        self.assertContains(self.client.get(reverse("feedback_desk")), "Закрытая тема")
        self.client.post(reverse("feedback_desk"), {"pk": item.pk, "status": "closed"})
        item.refresh_from_db();self.assertEqual(item.status, "closed")
