from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import Task


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


class TaskAccessTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user("owner")
        self.other = get_user_model().objects.create_user("other")
        self.task = Task.objects.create(owner=self.owner, title="Подготовить доклад", planned_minutes=90)
        self.client.force_login(self.owner)

    def test_create_sets_owner_from_session(self):
        self.client.post(reverse("task_create"), {"title": "Сдать работу", "planned_minutes": 45, "priority": 3, "owner": self.other.pk})
        self.assertEqual(Task.objects.get(title="Сдать работу").owner, self.owner)

    def test_invalid_estimate_does_not_create_task(self):
        self.client.post(reverse("task_create"), {"title": "Работа", "planned_minutes": 0, "priority": 2})
        self.assertEqual(Task.objects.count(), 1)

    def test_other_user_cannot_read_or_mutate_task(self):
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse("task_list")), self.task.title)
        for action in ["task_edit", "task_delete", "task_toggle"]:
            self.assertEqual(self.client.post(reverse(action, args=[self.task.pk]), {}).status_code, 404)
        self.task.refresh_from_db()
        self.assertFalse(self.task.is_done)

    def test_completion_can_be_reversed(self):
        url = reverse("task_toggle", args=[self.task.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        self.task.refresh_from_db()
        self.assertTrue(self.task.is_done)
        self.assertIsNotNone(self.task.completed_at)
        self.client.post(url)
        self.task.refresh_from_db()
        self.assertFalse(self.task.is_done)
        self.assertIsNone(self.task.completed_at)

    def test_delete_requires_post(self):
        url = reverse("task_delete", args=[self.task.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())
        self.client.post(url)
        self.assertFalse(Task.objects.filter(pk=self.task.pk).exists())

    def test_anonymous_user_is_redirected(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("task_list")).status_code, 302)
