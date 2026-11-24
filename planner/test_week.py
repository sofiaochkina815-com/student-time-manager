from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import Task, TimeEntry, WeekPlan
from .services import week_summary


class WeekTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("student")
        self.other = get_user_model().objects.create_user("other")
        self.start = date(2026, 11, 16)
        self.client.force_login(self.user)

    def test_plan_and_actual_use_different_dates(self):
        due_later = Task.objects.create(owner=self.user, title="Позже", due_date=self.start+timedelta(days=8), planned_minutes=120)
        due_now = Task.objects.create(owner=self.user, title="На неделе", due_date=self.start, planned_minutes=60)
        TimeEntry.objects.create(task=due_later, date=self.start, minutes=20)
        TimeEntry.objects.create(task=due_now, date=self.start, minutes=30)
        summary = week_summary(self.user, self.start)
        self.assertEqual((summary["planned"], summary["actual"]), (60, 50))
        self.assertEqual((summary["days"][0]["planned"], summary["days"][0]["actual"]), (60, 50))

    def test_capacity_and_foreign_data(self):
        Task.objects.create(owner=self.user, title="Моя", due_date=self.start, planned_minutes=90)
        foreign = Task.objects.create(owner=self.other, title="Чужая", due_date=self.start, planned_minutes=999)
        TimeEntry.objects.create(task=foreign, date=self.start, minutes=200)
        WeekPlan.objects.create(owner=self.user, week_start=self.start, capacity_minutes=60)
        summary = week_summary(self.user, self.start)
        self.assertTrue(summary["over_capacity"])
        self.assertEqual((summary["difference"], summary["actual"]), (-30, 0))

    def test_save_updates_same_owned_week(self):
        url = reverse("weekly_plan")+"?week=2026-11-18"
        self.client.post(url, {"capacity_minutes": 300,"expected_revision":0})
        self.client.post(url, {"capacity_minutes": 400,"expected_revision":1})
        plan = WeekPlan.objects.get()
        self.assertEqual((plan.owner, plan.week_start, plan.capacity_minutes), (self.user, self.start, 400))

    def test_invalid_budget_and_date_do_not_crash(self):
        url = reverse("weekly_plan")+"?week=2026-99-99"
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url, {"capacity_minutes": -1})
        self.assertFalse(WeekPlan.objects.exists())
