import hashlib
import tempfile
from pathlib import Path
from django.core.management import call_command
from django.core.files.storage import FileSystemStorage
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import TransactionTestCase, override_settings
from .models import Task, TaskAttachment, PrivateFileBlob
from .storage import DatabasePrivateStorage


@override_settings(STORAGES={"default":{"BACKEND":"planner.storage.DatabasePrivateStorage"},"staticfiles":{"BACKEND":"django.contrib.staticfiles.storage.StaticFilesStorage"}})
class DatabaseStorageTests(TransactionTestCase):
    def test_upload_survives_new_storage_instance_and_remains_private(self):
        user=get_user_model().objects.create_user('blob-owner')
        other=get_user_model().objects.create_user('blob-other')
        task=Task.objects.create(owner=user,title='Private materials')
        self.client.force_login(user)
        self.assertEqual(self.client.post(f'/tasks/{task.pk}/files/',{'file':SimpleUploadedFile('notes.txt',b'private content')}).status_code,302)
        item=TaskAttachment.objects.get()
        self.assertEqual(DatabasePrivateStorage().open(item.file.name).read(),b'private content')
        self.assertEqual(PrivateFileBlob.objects.count(),1)
        self.client.force_login(other)
        self.assertEqual(self.client.get(f'/files/{item.pk}/download/').status_code,404)
        self.client.force_login(user)
        response=self.client.get(f'/files/{item.pk}/download/')
        self.assertEqual(b''.join(response.streaming_content),b'private content');response.close()
        self.client.post(f'/files/{item.pk}/delete/')
        self.assertFalse(PrivateFileBlob.objects.exists())

    def test_blob_rolls_back_with_transaction_and_has_no_public_url(self):
        storage=DatabasePrivateStorage()
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                storage.save('private.txt',ContentFile(b'content'))
                raise RuntimeError('rollback')
        self.assertFalse(PrivateFileBlob.objects.exists())
        with self.assertRaises(NotImplementedError):storage.url('private.txt')
        with self.assertRaises(FileNotFoundError):storage.open('missing.txt')

    def test_copy_existing_local_file_is_checked_and_idempotent(self):
        user=get_user_model().objects.create_user('migrate-owner')
        task=Task.objects.create(owner=user,title='Legacy materials')
        with tempfile.TemporaryDirectory() as folder, override_settings(MEDIA_ROOT=folder):
            payload=b'legacy content'
            name=FileSystemStorage(location=folder).save('attachments/legacy.txt',ContentFile(payload))
            TaskAttachment.objects.create(owner=user,task=task,file=name,original_name='legacy.txt',size=len(payload),sha256=hashlib.sha256(payload).hexdigest(),kind='txt')
            call_command('copy_private_files_to_database',verbosity=0)
            call_command('copy_private_files_to_database',verbosity=0)
            self.assertEqual(PrivateFileBlob.objects.count(),1)
            self.assertEqual(DatabasePrivateStorage().open(name).read(),payload)
            self.assertTrue((Path(folder)/name).exists())
