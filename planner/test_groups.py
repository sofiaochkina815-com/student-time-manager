from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from .groups import curator_summary
from .models import StudyGroup, GroupMembership, Task, TimeEntry


class StudyGroupTests(TestCase):
    def setUp(self):
        self.curator = get_user_model().objects.create_user("curator")
        self.student = get_user_model().objects.create_user("student")
        self.outsider = get_user_model().objects.create_user("outsider")
        self.group = StudyGroup.objects.create(owner=self.curator, name="БИ-21")
        self.client.force_login(self.student)
        self.join = reverse("group_join")

    def test_join_is_idempotent_and_does_not_change_consent(self):
        self.client.post(self.join, {"code": self.group.invite_code, "student": self.outsider.pk})
        self.client.post(self.join, {"code": self.group.invite_code, "share_summary": "on"})
        item = GroupMembership.objects.get()
        self.assertEqual(item.student, self.student)
        self.assertFalse(item.share_summary)
        self.assertEqual(self.client.get(self.join).status_code, 405)

    def test_summaries_require_consent_and_never_include_task_text(self):
        self.client.post(self.join, {"code": self.group.invite_code})
        task = Task.objects.create(owner=self.student, title="HiddenTask", description="SecretNote")
        TimeEntry.objects.create(task=task, minutes=42)
        self.assertIsNone(curator_summary(self.curator, self.group)[0]["minutes"])
        self.client.post(reverse("group_consent", args=[self.group.pk]), {"share_summary": "on"})
        row = curator_summary(self.curator, self.group)[0]
        self.assertEqual((row["minutes"], row["tasks"]["total"]), (42, 1))
        self.client.force_login(self.curator)
        response = self.client.get(reverse("group_detail", args=[self.group.pk]))
        self.assertNotContains(response, "HiddenTask")
        self.assertNotContains(response, "SecretNote")
        self.client.force_login(self.student)
        self.client.post(reverse("group_consent", args=[self.group.pk]), {})
        self.assertIsNone(curator_summary(self.curator, self.group)[0]["minutes"])

    def test_group_invite_and_aggregate_permissions_are_separate(self):
        self.client.post(self.join, {"code": self.group.invite_code})
        detail = reverse("group_detail", args=[self.group.pk])
        self.assertNotContains(self.client.get(detail), self.group.invite_code)
        with self.assertRaises(PermissionDenied):
            curator_summary(self.student, self.group)
        self.assertEqual(self.client.post(reverse("group_rotate_code", args=[self.group.pk])).status_code, 404)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.assertEqual(self.client.post(reverse("group_consent", args=[self.group.pk]), {}).status_code, 404)

    def test_rotate_and_leave_revoke_access(self):
        old_code = self.group.invite_code
        self.client.force_login(self.curator)
        self.client.post(reverse("group_rotate_code", args=[self.group.pk]))
        self.group.refresh_from_db()
        self.assertNotEqual(old_code, self.group.invite_code)
        self.client.force_login(self.student)
        self.client.post(self.join, {"code": old_code})
        self.assertFalse(GroupMembership.objects.exists())
        self.client.post(self.join, {"code": self.group.invite_code})
        self.client.post(reverse("group_leave", args=[self.group.pk]))
        self.assertFalse(GroupMembership.objects.exists())
        self.assertEqual(self.client.get(reverse("group_detail", args=[self.group.pk])).status_code, 404)

    def test_creator_and_lists_are_scoped_to_current_user(self):
        self.client.post(reverse("group_create"), {"name": "Моя группа", "owner": self.curator.pk})
        self.assertEqual(StudyGroup.objects.get(name="Моя группа").owner, self.student)
        self.assertNotContains(self.client.get(reverse("group_list")), "БИ-21")
