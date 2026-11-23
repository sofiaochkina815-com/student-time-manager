from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone
from .models import Task, TimeEntry, StudySession
from .services import correct_time, record_time


class CorrectionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("correction")
        self.task = Task.objects.create(owner=self.user, title="Учёба")
        self.today = timezone.localdate()
        self.entry = record_time(user=self.user, task_id=self.task.pk, date=self.today, minutes=1000)

    def test_limit_excludes_old_value_and_checks_destination_day(self):
        correct_time(user=self.user, entry_id=self.entry.pk, date=self.today, minutes=1440)
        previous = self.today-timedelta(days=1)
        record_time(user=self.user, task_id=self.task.pk, date=previous, minutes=1000)
        with self.assertRaises(ValidationError): correct_time(user=self.user, entry_id=self.entry.pk, date=previous, minutes=441)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.minutes, 1440)
        correct_time(user=self.user, entry_id=self.entry.pk, date=previous, minutes=440)
        self.entry.refresh_from_db(); self.assertEqual(self.entry.date, previous)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(f"/time/{self.entry.pk}/delete/").status_code, 200)
        self.assertTrue(TimeEntry.objects.filter(pk=self.entry.pk).exists())
        self.assertEqual(self.client.post(f"/time/{self.entry.pk}/delete/").status_code, 302)
        self.assertFalse(TimeEntry.objects.filter(pk=self.entry.pk).exists())

    def test_foreign_future_and_completed_session_are_protected(self):
        other = get_user_model().objects.create_user("other-correction")
        with self.assertRaises(PermissionDenied): correct_time(user=other, entry_id=self.entry.pk, delete=True)
        with self.assertRaises(ValidationError): correct_time(user=self.user, entry_id=self.entry.pk, date=self.today+timedelta(days=1), minutes=1)
        StudySession.objects.create(owner=self.user, task=self.task, starts_at=timezone.now()-timedelta(hours=1),
            status="completed", time_entry=self.entry, completed_at=timezone.now())
        for change in [{"delete": True}, {"date": self.today, "minutes": 1}]:
            with self.assertRaises(ValidationError): correct_time(user=self.user, entry_id=self.entry.pk, **change)
        self.client.force_login(other)
        self.assertEqual(self.client.get(f"/time/{self.entry.pk}/edit/").status_code, 404)
