from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Task, Subject


class FilterTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("student")
        self.client.force_login(self.user)

    def test_search_and_subject_filter(self):
        subject = Subject.objects.create(owner=self.user, name="Экономика")
        wanted = Task.objects.create(owner=self.user, title="Доклад", description="Денежные потоки", subject=subject)
        Task.objects.create(owner=self.user, title="Практика")
        response = self.client.get(reverse("task_list"), {"q": "потоки", "subject": subject.pk})
        self.assertEqual(list(response.context["tasks"]), [wanted])
        self.assertIn("q=", response.context["state_links"]["done"])

    def test_foreign_subject_is_not_a_valid_filter(self):
        other = get_user_model().objects.create_user("other")
        subject = Subject.objects.create(owner=other, name="Чужая")
        response = self.client.get(reverse("task_list"), {"subject": subject.pk})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["filters"].errors)
        self.assertFalse(response.context["tasks"].exists())

    def test_deadline_order_places_undated_tasks_last(self):
        no_date = Task.objects.create(owner=self.user, title="Без даты")
        later = Task.objects.create(owner=self.user, title="Позже", due_date=timezone.localdate()+timedelta(days=3))
        soon = Task.objects.create(owner=self.user, title="Сегодня", due_date=timezone.localdate())
        response = self.client.get(reverse("task_list"), {"sort": "deadline"})
        self.assertEqual(list(response.context["tasks"]), [soon, later, no_date])

    def test_pagination_keeps_summary_and_stable_result(self):
        for n in range(25):
            Task.objects.create(owner=self.user, title=f"Задача {n}", planned_minutes=10)
        first = self.client.get(reverse("task_list"))
        second = self.client.get(reverse("task_list"), {"page": 2})
        self.assertEqual(len(first.context["tasks"]), 20)
        self.assertEqual(len(second.context["tasks"]), 5)
        self.assertEqual(first.context["planned_minutes"], 250)
        self.assertFalse({t.pk for t in first.context["tasks"]} & {t.pk for t in second.context["tasks"]})
