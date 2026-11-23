from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from .models import Task, TimeEntry
from .research import compare_periods


class ComparisonTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("research")
        today = timezone.localdate()
        self.values = dict(before_start=today-timedelta(days=13), before_end=today-timedelta(days=7),
            after_start=today-timedelta(days=6), after_end=today)

    def test_equal_windows_exact_change_and_privacy(self):
        task = Task.objects.create(owner=self.user, title="Моя задача")
        TimeEntry.objects.create(task=task, date=self.values["before_start"], minutes=30)
        TimeEntry.objects.create(task=task, date=self.values["after_end"], minutes=45)
        other = get_user_model().objects.create_user("foreign")
        TimeEntry.objects.create(task=Task.objects.create(owner=other, title="Секрет"), date=self.values["after_end"], minutes=999)
        report = compare_periods(self.user, **self.values)
        self.assertEqual(report["rows"][0]["relative_percent"], Decimal(50))
        self.assertEqual(report["rows"][0]["delta"], 15)
        self.assertEqual(report["periods"][1]["active_days"], 1)
        self.client.force_login(self.user)
        response = self.client.get("/research/", {**self.values, "format": "json"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["rows"][0]["after"], 45)
        self.assertNotIn("Секрет", response.content.decode())
        self.assertContains(self.client.get("/research/", self.values), "не измеряют качество знаний")

    def test_empty_denominator_overlap_length_and_future(self):
        self.assertIsNone(compare_periods(self.user, **self.values)["rows"][0]["relative_percent"])
        for change in [{"after_start": self.values["before_end"]},
                       {"after_end": self.values["after_end"]+timedelta(days=1)},
                       {"before_start": self.values["before_start"]-timedelta(days=1)}]:
            with self.assertRaises(ValidationError): compare_periods(self.user, **{**self.values, **change})
        self.assertEqual(self.client.get("/research/").status_code, 302)
