from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import StudyGoal, Subject, Task, TimeEntry
from .services import goal_progress


class GoalTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("goal-student")
        self.other = get_user_model().objects.create_user("goal-other")
        self.client.force_login(self.user)
        self.today = timezone.localdate()
        self.subject = Subject.objects.create(owner=self.user, name="Математика")
        self.goal = StudyGoal.objects.create(owner=self.user, title="Подготовка", subject=self.subject,
            starts_on=self.today-timedelta(days=2), ends_on=self.today, target_minutes=60)

    def test_progress_counts_only_own_subject_and_period(self):
        task = Task.objects.create(owner=self.user, title="Своя", subject=self.subject)
        outside = Task.objects.create(owner=self.user, title="Без дисциплины")
        foreign = Task.objects.create(owner=self.other, title="Чужая")
        for item, date, minutes in [(task, self.today, 35), (task, self.today-timedelta(days=3), 100),
                                   (outside, self.today, 200), (foreign, self.today, 300)]:
            TimeEntry.objects.create(task=item, date=date, minutes=minutes)
        row = goal_progress(self.user, self.goal)
        self.assertEqual((row["actual"], row["remaining"], row["percentage"]), (35, 25, 58))
        self.assertFalse(row["overdue"])
        self.assertTrue(goal_progress(self.user, self.goal, self.today+timedelta(days=1))["overdue"])
        TimeEntry.objects.create(task=task, date=self.today, minutes=30)
        row = goal_progress(self.user, self.goal)
        self.assertEqual((row["actual"], row["percentage"], row["reached"]), (65, 100, True))

    def test_invalid_subject_and_dates_are_rejected(self):
        subject = Subject.objects.create(owner=self.other, name="Чужая")
        payload = {"title": "Новая", "subject": subject.pk, "starts_on": self.today,
            "ends_on": self.today, "target_minutes": 10}
        self.client.post(reverse("goal_create"), payload)
        self.assertEqual(StudyGoal.objects.count(), 1)
        self.goal.subject = subject
        with self.assertRaises(ValidationError):
            self.goal.full_clean()
        for values in [{"starts_on": self.today, "ends_on": self.today-timedelta(days=1)},
                       {"starts_on": self.today, "ends_on": self.today+timedelta(days=500)}]:
            payload.update(values, subject="")
            self.client.post(reverse("goal_create"), payload)
        self.assertEqual(StudyGoal.objects.count(), 1)

    def test_edit_archive_and_delete_are_private(self):
        self.client.force_login(self.other)
        for action in ["goal_edit", "goal_delete"]:
            self.assertEqual(self.client.post(reverse(action, args=[self.goal.pk]), {}).status_code, 404)
        self.assertNotContains(self.client.get(reverse("goal_list")), self.goal.title)
        self.client.force_login(self.user)
        self.client.post(reverse("goal_edit", args=[self.goal.pk]), {"title": "Подготовка", "subject": self.subject.pk,
            "starts_on": self.goal.starts_on, "ends_on": self.goal.ends_on, "target_minutes": 90, "is_archived": "on"})
        self.assertNotContains(self.client.get(reverse("goal_list")), "Подготовка")
        self.assertContains(self.client.get(reverse("goal_list"), {"archive": "1"}), "Подготовка")
        self.client.get(reverse("goal_delete", args=[self.goal.pk]))
        self.assertTrue(StudyGoal.objects.exists())
        self.client.post(reverse("goal_delete", args=[self.goal.pk]))
        self.assertFalse(StudyGoal.objects.exists())

    def test_subject_removal_does_not_silently_broaden_goal(self):
        self.client.post(reverse("reference_delete", args=["subjects", self.subject.pk]))
        self.assertTrue(Subject.objects.filter(pk=self.subject.pk).exists())
        self.goal.refresh_from_db()
        self.assertEqual(self.goal.subject, self.subject)
