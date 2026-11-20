from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from .models import Subject, TaskCategory, Task


class ReferenceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("student")
        self.other = get_user_model().objects.create_user("other")
        self.client.force_login(self.user)

    def test_owner_and_unique_name(self):
        url = reverse("reference_create", args=["subjects"])
        self.client.post(url, {"name": "Экономика", "owner": self.other.pk})
        self.assertEqual(Subject.objects.get().owner, self.user)
        self.assertContains(self.client.post(url, {"name": "Экономика"}), "уже используется")
        self.assertEqual(Subject.objects.count(), 1)

    def test_foreign_references_rejected_in_tasks_and_catalog(self):
        subject = Subject.objects.create(owner=self.other, name="Чужая дисциплина")
        self.client.post(reverse("task_create"), {"title": "Доклад", "priority": 2, "planned_minutes": 60, "subject": subject.pk})
        self.assertFalse(Task.objects.exists())
        self.assertEqual(self.client.post(reverse("reference_delete", args=["subjects", subject.pk]), {}).status_code, 404)
        with self.assertRaises(ValidationError):
            Task(owner=self.user, subject=subject, title="Доклад").full_clean()

    def test_reference_deletion_preserves_task(self):
        category = TaskCategory.objects.create(owner=self.user, name="Практика")
        task = Task.objects.create(owner=self.user, category=category, title="Задача")
        url = reverse("reference_delete", args=["categories", category.pk])
        self.client.get(url)
        self.assertTrue(TaskCategory.objects.exists())
        self.client.post(url)
        task.refresh_from_db()
        self.assertIsNone(task.category_id)

    def test_valid_task_relations_persist(self):
        subject = Subject.objects.create(owner=self.user, name="Экономика")
        category = TaskCategory.objects.create(owner=self.user, name="Доклад")
        self.client.post(reverse("task_create"), {"title": "Сдать доклад", "planned_minutes": 60, "priority": 2, "subject": subject.pk, "category": category.pk})
        task = Task.objects.get()
        self.assertEqual((task.subject_id, task.category_id), (subject.pk, category.pk))
