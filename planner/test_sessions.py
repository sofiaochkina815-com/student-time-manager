from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import StudySession, Task, TimeEntry
from .sessions import save_session, finish_session


class StudySessionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("session-student")
        self.other = get_user_model().objects.create_user("session-other")
        self.task = Task.objects.create(owner=self.user, title="Практика")
        self.start = timezone.now().replace(second=0, microsecond=0)-timedelta(minutes=120)
        self.client.force_login(self.user)

    def create(self, **values):
        data = {"owner": self.user, "task": self.task, "starts_at": self.start, "planned_minutes": 25}
        data.update(values)
        return save_session(self.user, StudySession(**data))

    def test_overlaps_rejected_but_adjacent_sessions_allowed(self):
        self.create()
        for offset in [-10, 10, 24]:
            with self.assertRaises(ValidationError):
                self.create(starts_at=self.start+timedelta(minutes=offset))
        self.create(starts_at=self.start+timedelta(minutes=25))
        self.assertEqual(StudySession.objects.count(), 2)

    def test_foreign_tasks_and_sessions_cannot_be_used(self):
        other_task = Task.objects.create(owner=self.other, title="Чужая")
        with self.assertRaises(ValidationError):
            self.create(task=other_task)
        session = self.create()
        self.client.force_login(self.other)
        for name in ["session_edit", "session_finish", "session_cancel"]:
            self.assertEqual(self.client.post(reverse(name, args=[session.pk]), {}).status_code, 404)
        self.assertNotContains(self.client.get(reverse("session_list")), "Практика")

    def test_finish_records_once_and_keeps_actual_distinct_from_plan(self):
        session = self.create()
        url = reverse("session_finish", args=[session.pk])
        self.assertRedirects(self.client.post(url, {"minutes": 35, "note": "Проверено"}), reverse("session_list"))
        self.client.post(url, {"minutes": 99})
        session.refresh_from_db()
        self.assertEqual(session.status, "completed")
        self.assertEqual((TimeEntry.objects.count(), session.time_entry.minutes, session.planned_minutes), (1, 35, 25))
        self.assertEqual(session.time_entry.date, timezone.localdate(self.start))
        self.assertContains(self.client.get(reverse("session_list"), {"state": "history"}), "Записано: 35")
        self.assertEqual(self.client.post(reverse("session_edit", args=[session.pk]), {}).status_code, 404)

    def test_daily_limit_failure_rolls_back_completion(self):
        session = self.create()
        TimeEntry.objects.create(task=self.task, date=timezone.localdate(self.start), minutes=1430)
        with self.assertRaises(ValidationError):
            finish_session(self.user, session.pk, 20)
        session.refresh_from_db()
        self.assertEqual(session.status, "planned")
        self.assertIsNone(session.time_entry_id)
        self.assertEqual(TimeEntry.objects.count(), 1)

    def test_cancellation_frees_slot_and_does_not_record_time(self):
        session = self.create()
        self.assertEqual(self.client.get(reverse("session_cancel", args=[session.pk])).status_code, 405)
        self.client.post(reverse("session_cancel", args=[session.pk]))
        self.create()
        with self.assertRaises(ValidationError):
            finish_session(self.user, session.pk, 10)
        self.assertFalse(TimeEntry.objects.exists())

    def test_future_session_cannot_be_completed(self):
        session = self.create(starts_at=timezone.now()+timedelta(days=1))
        with self.assertRaises(ValidationError):
            finish_session(self.user, session.pk, 10)
        self.assertFalse(TimeEntry.objects.exists())

    def test_form_flow_and_task_history_protection(self):
        response = self.client.post(reverse("session_create"), {"task": self.task.pk,
            "starts_at": timezone.localtime(self.start).strftime("%Y-%m-%dT%H:%M"), "planned_minutes": 30})
        self.assertRedirects(response, reverse("session_list"))
        self.assertEqual(StudySession.objects.get().planned_minutes, 30)
        self.client.post(reverse("task_delete", args=[self.task.pk]))
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())
        self.assertContains(self.client.get(reverse("session_list")), "Практика")
