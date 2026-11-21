from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .analytics import study_report
from .models import Task, TimeEntry


class AnalyticsTests(TestCase):
    def test_dates_owner_and_estimation_error(self):
        user = get_user_model().objects.create_user("report-student")
        other = get_user_model().objects.create_user("report-other")
        today = timezone.localdate()
        task = Task.objects.create(owner=user, title="Доклад", due_date=today, planned_minutes=60, is_done=True)
        later = Task.objects.create(owner=user, title="Позже", due_date=today+timedelta(days=10), planned_minutes=120)
        foreign = Task.objects.create(owner=other, title="Чужая", due_date=today, planned_minutes=999)
        for item, minutes in [(task, 40), (later, 20), (foreign, 500)]:
            TimeEntry.objects.create(task=item, date=today, minutes=minutes)
        report = study_report(user, today, today)
        self.assertEqual((report["planned"], report["actual"], report["task_count"]), (60, 60, 1))
        self.assertEqual(report["mae"], Decimal("20"))
        self.assertEqual(report["estimate_count"], 1)

    def test_invalid_period_and_empty_page(self):
        user = get_user_model().objects.create_user("empty-student")
        self.client.force_login(user)
        self.assertContains(self.client.get(reverse("analytics")), "Учебное время в цифрах")
        for params in [{"start": "bad"}, {"start": "2026-11-20", "end": "2026-11-01"}, {"start": "2020-01-01", "end": "2026-01-01"}]:
            response = self.client.get(reverse("analytics"), params)
            self.assertTrue(response.context["form"].errors)
            self.assertIsNone(response.context["report"])
