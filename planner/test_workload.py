from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from .models import Task, TimeEntry, WeekPlan
from .workload import workload_snapshot
from django.utils import timezone


class WorkloadTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('workload')
        self.day=timezone.localdate()
        self.start=self.day-timedelta(days=self.day.weekday())

    def test_backlog_current_effort_and_capacity_have_separate_dates(self):
        overdue=Task.objects.create(owner=self.user,title='Old',due_date=self.start-timedelta(days=1),planned_minutes=100)
        TimeEntry.objects.create(task=overdue,date=self.start-timedelta(days=3),minutes=25)
        TimeEntry.objects.create(task=overdue,date=self.start,minutes=20)
        over=Task.objects.create(owner=self.user,title='Over estimate',due_date=self.start,planned_minutes=5)
        TimeEntry.objects.create(task=over,date=self.start,minutes=10)
        Task.objects.create(owner=self.user,title='Done',due_date=self.start,planned_minutes=999,is_done=True)
        Task.objects.create(owner=self.user,title='Later',due_date=self.start+timedelta(days=7),planned_minutes=999)
        Task.objects.create(owner=self.user,title='Undated')
        other=get_user_model().objects.create_user('workload-stranger')
        Task.objects.create(owner=other,title='Foreign',due_date=self.start,planned_minutes=999)
        WeekPlan.objects.create(owner=self.user,week_start=self.start,capacity_minutes=50)
        report=workload_snapshot(self.user,self.start)
        self.assertEqual((report['required'],report['backlog'],report['actual'],report['available'],report['gap']), (55,55,30,20,35))
        self.assertEqual(report['undated'],1)
        self.client.force_login(self.user)
        response=self.client.get('/workload/',{'week':self.start})
        self.assertContains(response,'55 мин')
        self.assertNotContains(response,'Foreign')

    def test_missing_budget_zero_budget_and_past_week(self):
        self.assertIsNone(workload_snapshot(self.user,self.start)['gap'])
        WeekPlan.objects.create(owner=self.user,week_start=self.start,capacity_minutes=0)
        self.assertEqual(workload_snapshot(self.user,self.start)['available'],0)
        with self.assertRaises(ValidationError):workload_snapshot(self.user,self.start-timedelta(days=7))
        with patch('django.db.models.query.QuerySet.count',return_value=2001):
            with self.assertRaises(ValidationError):workload_snapshot(self.user,self.start)
