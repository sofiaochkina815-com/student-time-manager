from datetime import date, datetime, timezone as dt_timezone
import re
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from .calendar_export import calendar_bytes
from .models import Task, StudySession


class CalendarExportTests(TestCase):
    def test_utc_all_day_folding_escaping_and_private_scope(self):
        user=get_user_model().objects.create_user('ics')
        foreign=get_user_model().objects.create_user('foreign-ics')
        title='Кириллица, точка; '+('длинная строка '*15)+'\r\nBEGIN:VEVENT'
        task=Task.objects.create(owner=user,title=title,due_date=date(2026,11,30))
        Task.objects.create(owner=foreign,title='Чужое событие',due_date=date(2026,11,30))
        StudySession.objects.create(owner=user,task=task,starts_at=datetime(2026,11,30,19,30,tzinfo=dt_timezone.utc),planned_minutes=60,status='cancelled')
        with timezone.override('Asia/Tbilisi'):
            result=calendar_bytes(user,date(2026,11,1))
        lines=result.split(b'\r\n')
        self.assertTrue(all(len(line)<=75 for line in lines))
        for line in lines:line.decode('utf-8')
        unfolded=result.replace(b'\r\n ',b'').decode()
        self.assertEqual(unfolded.count('\r\nBEGIN:VEVENT\r\n'),2)
        self.assertIn('DTSTART;VALUE=DATE:20261130\r\nDTEND;VALUE=DATE:20261201',unfolded)
        self.assertIn('DTSTART:20261130T193000Z\r\nDTEND:20261130T203000Z',unfolded)
        self.assertIn('Кириллица\\, точка\\;',unfolded)
        self.assertIn('\\nBEGIN:VEVENT',unfolded)
        self.assertIn('STATUS:CANCELLED',unfolded)
        self.assertNotIn('Чужое событие',unfolded)
        self.client.force_login(user)
        response=self.client.get('/calendar/export.ics',{'month':'2026-11'})
        self.assertEqual(response.status_code,200);self.assertEqual(response['Cache-Control'],'private, no-store')
        next_result=response.content.replace(b'\r\n ',b'').decode()
        self.assertEqual(re.findall('UID:(.*)',unfolded),re.findall('UID:(.*)',next_result))
        self.assertEqual(self.client.get('/calendar/export.ics',{'month':'bad'}).status_code,400)

    def test_limit_returns_no_partial_calendar(self):
        user=get_user_model().objects.create_user('ics-limit')
        Task.objects.bulk_create([Task(owner=user,title=f'Задача{i}',due_date=date(2026,11,1)) for i in range(3)])
        self.client.force_login(user)
        with patch('planner.calendar_export.LIMIT',2):
            response=self.client.get('/calendar/export.ics',{'month':'2026-11'})
        self.assertEqual(response.status_code,400);self.assertNotIn(b'BEGIN:VCALENDAR',response.content)
