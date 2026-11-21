import csv
import io
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Task, TimeEntry


class ExportTests(TestCase):
    def test_own_filtered_csv_and_formula_text(self):
        user = get_user_model().objects.create_user("export-student")
        other = get_user_model().objects.create_user("export-other")
        today = timezone.localdate()
        for owner in [user, other]:
            task = Task.objects.create(owner=owner, title="=1+1", due_date=today, planned_minutes=30)
            TimeEntry.objects.create(task=task, date=today, minutes=20, note="@note")
        self.client.force_login(user)
        params = {"start": today, "end": today}
        response = self.client.get(reverse("time_export"), params)
        rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig")), delimiter=";"))
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["task"], rows[0]["minutes"]), ("'=1+1", "20"))
        response = self.client.get(reverse("summary_export"), params)
        rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig")), delimiter=";"))
        self.assertEqual((rows[0]["planned_by_deadline_minutes"], rows[0]["actual_minutes"]), ("30", "20"))
        self.assertEqual(self.client.get(reverse("time_export"), {"start": "bad"}).status_code, 400)
