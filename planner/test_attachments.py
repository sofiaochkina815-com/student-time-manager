import tempfile
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import Task, TaskAttachment


class AttachmentTests(TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.folder.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable);self.addCleanup(self.folder.cleanup)
        self.user = get_user_model().objects.create_user("file-owner")
        self.other = get_user_model().objects.create_user("file-other")
        self.task = Task.objects.create(owner=self.user, title="Задача с файлами")
        self.client.force_login(self.user)

    def test_upload_is_private_and_download_delete_are_authorized(self):
        self.client.post(reverse("attachment_list", args=[self.task.pk]), {"file": SimpleUploadedFile("notes.txt", "Конспект".encode())})
        item = TaskAttachment.objects.get()
        path = Path(item.file.path)
        self.assertTrue(path.exists())
        response = self.client.get(reverse("attachment_download", args=[item.pk]))
        self.assertEqual(b"".join(response.streaming_content), "Конспект".encode());response.close()
        self.client.force_login(self.other)
        for route in ["attachment_download", "attachment_delete"]:
            self.assertEqual(self.client.get(reverse(route, args=[item.pk])).status_code, 404)
        self.client.force_login(self.user)
        self.client.get(reverse("attachment_delete", args=[item.pk]))
        self.assertTrue(path.exists())
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("attachment_delete", args=[item.pk]))
        self.assertFalse(path.exists())

    def test_wrong_formats_and_duplicates_do_not_create_extra_files(self):
        url = reverse("attachment_list", args=[self.task.pk])
        for name, payload in [("script.html", b"<script>"), ("bad.pdf", b"not pdf"), ("binary.txt", b"\x00data")]:
            self.client.post(url, {"file": SimpleUploadedFile(name, payload)})
        self.assertFalse(TaskAttachment.objects.exists())
        for _ in range(2):
            self.client.post(url, {"file": SimpleUploadedFile("good.txt", b"notes")})
        self.assertEqual(TaskAttachment.objects.count(), 1)
