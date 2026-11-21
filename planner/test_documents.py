import io
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfReader
from .analytics import study_report
from .documents import build_study_pdf
from .models import Task, TimeEntry


class DocumentTests(TestCase):
    def test_pdf_uses_current_user_and_cyrillic_text(self):
        user = get_user_model().objects.create_user("pdf-user")
        other = get_user_model().objects.create_user("pdf-other")
        today = timezone.localdate()
        for owner, minutes in [(user, 25), (other, 999)]:
            task = Task.objects.create(owner=owner, title="Задача", due_date=today, planned_minutes=60)
            TimeEntry.objects.create(task=task, date=today, minutes=minutes)
        self.client.force_login(user)
        response = self.client.get(reverse("study_pdf"), {"start": today, "end": today})
        self.assertEqual(response["Content-Type"], "application/pdf")
        text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(response.content)).pages)
        self.assertIn("Фактические записи: 25 мин", text)
        self.assertNotIn("999", text)
        self.assertIn("Очкина София Леонидовна", text)
        self.assertEqual(self.client.get(reverse("study_pdf"), {"start": "bad"}).status_code, 400)

    def test_long_report_repeats_table_header_and_page_footer(self):
        user = get_user_model().objects.create_user("pdf-long")
        end = timezone.localdate()
        contents = build_study_pdf(user, study_report(user, end-timedelta(days=92), end))
        reader = PdfReader(io.BytesIO(contents))
        self.assertGreaterEqual(len(reader.pages), 3)
        self.assertIn("Дата", reader.pages[1].extract_text())
        for number, page in enumerate(reader.pages, 1):
            self.assertIn(f"Страница {number}", page.extract_text())
