from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from .file_maintenance import cleanup_blobs
from .models import Task, TaskAttachment, PrivateFileBlob


class BlobMaintenanceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("files-maintenance")

    def blob(self, number, old=True):
        item = PrivateFileBlob.objects.create(name=f"attachments/{self.user.pk}/{number:032x}.txt", content=b"abc", size=3)
        if old: PrivateFileBlob.objects.filter(pk=item.pk).update(created_at=timezone.now()-timedelta(days=8))
        return item

    def test_dry_run_live_and_young_files_are_preserved(self):
        orphan = self.blob(1)
        live = self.blob(2)
        young = self.blob(3, old=False)
        task = Task.objects.create(owner=self.user, title="Материалы")
        TaskAttachment.objects.create(owner=self.user, task=task, file=live.name, original_name="x.txt", size=3, kind="txt", sha256="a"*64)
        self.assertEqual(cleanup_blobs()["eligible"], 1)
        self.assertEqual(PrivateFileBlob.objects.count(), 3)
        self.assertEqual(cleanup_blobs(delete=True)["deleted"], 1)
        self.assertFalse(PrivateFileBlob.objects.filter(pk=orphan.pk).exists())
        self.assertTrue(PrivateFileBlob.objects.filter(pk__in=[live.pk, young.pk]).count()==2)
        self.assertEqual(cleanup_blobs(delete=True)["deleted"], 0)

    def test_recheck_and_unsupported_names_do_not_delete(self):
        item = self.blob(4)
        with patch("planner.file_maintenance.TaskAttachment.objects.filter") as references:
            references.return_value.exists.return_value = True
            self.assertEqual(cleanup_blobs(delete=True)["preserved"], 1)
        self.assertTrue(PrivateFileBlob.objects.filter(pk=item.pk).exists())
        item.name="unrecognized.txt"; item.save(update_fields=["name"])
        self.assertEqual(cleanup_blobs(delete=True)["unknown_names"], 1)
        with self.assertRaises(ValueError): cleanup_blobs(delete=True, older_than_days=0)
