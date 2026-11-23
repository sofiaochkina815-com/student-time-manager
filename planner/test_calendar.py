from datetime import date, datetime, timezone as dt_timezone
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from .calendar_view import month_data, MonthForm
from .models import Task, StudySession, TimeEntry


class CalendarTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('calendar')
        self.other=get_user_model().objects.create_user('foreign-calendar')

    def test_month_boundary_midnight_and_private_facts(self):
        task=Task.objects.create(owner=self.user,title='Моя задача',due_date=date(2026,11,30))
        # UTC20:30 ->00:30 Тбилиси 1декабря; начало23:30 30ноября.
        session=StudySession.objects.create(owner=self.user,task=task,starts_at=datetime(2026,11,30,19,30,tzinfo=dt_timezone.utc),planned_minutes=60)
        TimeEntry.objects.create(task=task,date=date(2026,11,30),minutes=17)
        other_task=Task.objects.create(owner=self.other,title='Чужая задача',due_date=date(2026,11,30))
        TimeEntry.objects.create(task=other_task,date=date(2026,11,30),minutes=123)
        with timezone.override('Asia/Tbilisi'):
            november=month_data(self.user,date(2026,11,1));december=month_data(self.user,date(2026,12,1))
        days=lambda result:{day['date']:day for week in result['weeks'] for day in week if day}
        last=days(november)[date(2026,11,30)];first=days(december)[date(2026,12,1)]
        self.assertEqual(last['tasks'],[task]);self.assertEqual(last['actual_minutes'],17)
        self.assertEqual(last['sessions'][0]['minutes'],30);self.assertEqual(first['sessions'][0]['minutes'],30)
        self.assertEqual(first['tasks'],[])
        self.client.force_login(self.user)
        response=self.client.get('/calendar/',{'month':'2026-11'})
        self.assertContains(response,'Моя задача');self.assertNotContains(response,'Чужая задача')
        self.assertEqual(self.client.get('/calendar/',{'month':'invalid'}).status_code,200)

    def test_date_limits_and_no_week_padding_as_data(self):
        self.assertFalse(MonthForm({'month':'1899-12'}).is_valid())
        self.assertFalse(MonthForm({'month':'2101-01'}).is_valid())
        result=month_data(self.user,date(2028,2,1))
        self.assertEqual(sum(day is not None for week in result['weeks'] for day in week),29)
        self.assertEqual(result['next'],date(2028,3,1))
