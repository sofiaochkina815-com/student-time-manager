from uuid import uuid4
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Task, TimeEntry, TimeCommand
from .services import record_time, correct_time


class TimeCommandTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('time-command')
        self.task=Task.objects.create(owner=self.user,title='Work')
        self.values=dict(user=self.user,task_id=self.task.pk,date=timezone.localdate(),minutes=1440,note='',command_key=uuid4())

    def test_retry_at_daily_limit_and_conflicting_payload(self):
        first=record_time(**self.values)
        self.assertEqual(record_time(**self.values).pk,first.pk)
        self.assertEqual(TimeEntry.objects.count(),1)
        self.assertEqual(TimeCommand.objects.count(),1)
        with self.assertRaises(ValidationError):record_time(**{**self.values,'minutes':1})
        self.assertEqual(TimeEntry.objects.get().minutes,1440)

    def test_retry_does_not_revert_correction_or_resurrect_deletion(self):
        first=record_time(**self.values)
        correct_time(user=self.user,entry_id=first.pk,date=timezone.localdate(),minutes=20,note='Corrected')
        self.assertEqual(record_time(**self.values).minutes,20)
        correct_time(user=self.user,entry_id=first.pk,delete=True)
        with self.assertRaises(ValidationError):record_time(**self.values)
        self.assertFalse(TimeEntry.objects.exists())

    def test_form_requires_key_and_post_repeat_keeps_one_record(self):
        self.client.force_login(self.user)
        url=f'/tasks/{self.task.pk}/time/'
        payload={'date':timezone.localdate(),'minutes':7}
        self.assertContains(self.client.post(url,payload),'Обязательное поле')
        self.assertFalse(TimeEntry.objects.exists())
        payload['command_key']=self.client.get(url).context['form']['command_key'].value()
        for _ in range(2):self.assertEqual(self.client.post(url,payload).status_code,302)
        self.assertEqual(TimeEntry.objects.count(),1)
