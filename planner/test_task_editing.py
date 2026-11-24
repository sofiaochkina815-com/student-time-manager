from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from .models import Task
from .task_editing import save_task,EDITABLE_TASK_FIELDS
from .task_history import set_task_state


class TaskEditingTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('versioned-task')
        self.task=Task.objects.create(owner=self.user,title='Original')
        self.client.force_login(self.user);self.url=f'/tasks/{self.task.pk}/edit/'

    def payload(self,title):
        return {'title':title,'priority':2,'planned_minutes':60,
                'expected_updated_at':self.client.get(self.url).context['form']['expected_updated_at'].value()}

    def test_second_open_form_cannot_erase_newer_edit(self):
        first=self.payload('First change');stale={**first,'title':'Stale overwrite'}
        self.assertEqual(self.client.post(self.url,first).status_code,302)
        self.assertContains(self.client.post(self.url,stale),'уже изменилась')
        self.task.refresh_from_db();self.assertEqual(self.task.title,'First change')

    def test_completion_invalidates_old_editor_and_remains_completed(self):
        old=self.payload('Edit before status change')
        set_task_state(self.user,self.task.pk,True,0)
        self.assertContains(self.client.post(self.url,old),'уже изменилась')
        self.task.refresh_from_db();self.assertTrue(self.task.is_done);self.assertEqual(self.task.title,'Original')
        self.assertEqual(self.client.post(self.url,self.payload('Updated after reload')).status_code,302)
        self.task.refresh_from_db();self.assertEqual(self.task.title,'Updated after reload');self.assertTrue(self.task.is_done)

    def test_missing_version_and_extra_service_fields_are_rejected(self):
        self.assertContains(self.client.post(self.url,{'title':'Unversioned','priority':2,'planned_minutes':60}),'уже изменилась')
        values={key:getattr(self.task,key) for key in EDITABLE_TASK_FIELDS}
        with self.assertRaises(ValidationError):save_task(self.user,{**values,'is_done':True},self.task.pk,self.task.updated_at)
        self.task.refresh_from_db();self.assertEqual(self.task.title,'Original')
