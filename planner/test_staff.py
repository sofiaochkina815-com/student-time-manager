from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Task, TimeEntry, StudyGroup


class StaffTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.admin = users.objects.create_user("admin-cabinet", is_staff=True)
        self.student = users.objects.create_user("student-cabinet")

    def test_all_admin_pages_require_staff_and_render_for_staff(self):
        paths = [reverse(name) for name in ["staff_dashboard", "staff_users", "staff_groups", "staff_time", "feedback_desk"]]
        paths += [reverse("staff_catalog", args=[kind]) for kind in ["subjects", "categories"]]
        self.client.force_login(self.student)
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 302)
        self.client.force_login(self.admin)
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 200)

    def test_account_and_invitation_moderation_cannot_disable_admin(self):
        group = StudyGroup.objects.create(owner=self.student, name="Моя группа")
        old_code = group.invite_code
        self.client.force_login(self.admin)
        self.client.post(reverse("staff_user_toggle", args=[self.admin.pk]))
        self.admin.refresh_from_db();self.assertTrue(self.admin.is_active)
        self.client.post(reverse("staff_user_toggle", args=[self.student.pk]))
        self.student.refresh_from_db();self.assertFalse(self.student.is_active)
        self.client.post(reverse("staff_group_revoke", args=[group.pk]))
        group.refresh_from_db();self.assertNotEqual(old_code, group.invite_code)

    def test_time_audit_detects_invalid_legacy_aggregate_without_editing_it(self):
        task = Task.objects.create(owner=self.student, title="Тест контроля")
        TimeEntry.objects.create(task=task, minutes=1000)
        TimeEntry.objects.create(task=task, minutes=500)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("staff_time"), {"start": timezone.localdate(), "end": timezone.localdate()})
        self.assertContains(response, "Требует проверки")
        self.assertEqual(response.context["page"][0]["minutes"], 1500)
