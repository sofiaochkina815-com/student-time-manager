from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from .models import Task, TaskStateEvent
from .task_history import set_task_state


class TaskHistoryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('history')
        self.task = Task.objects.create(owner=self.user, title='Original', planned_minutes=25)
        self.client.force_login(self.user)

    def test_duplicate_and_stale_requests_do_not_toggle(self):
        task, changed = set_task_state(self.user, self.task.pk, True, 0)
        first = task.completed_at
        self.assertTrue(changed)
        self.assertFalse(set_task_state(self.user, self.task.pk, True, 0)[1])
        self.assertEqual(TaskStateEvent.objects.count(), 1)
        self.assertEqual(Task.objects.get().completed_at, first)
        set_task_state(self.user, self.task.pk, False, 1)
        with self.assertRaises(ValidationError):
            set_task_state(self.user, self.task.pk, True, 0)
        self.assertFalse(Task.objects.get().is_done)
        self.assertEqual(list(TaskStateEvent.objects.order_by('revision').values_list('is_done', flat=True)), [True, False])

    def test_snapshot_survives_edit_delete_and_is_private(self):
        set_task_state(self.user, self.task.pk, True, 0)
        self.task.title='New';self.task.save(update_fields=['title'])
        self.task.delete()
        self.assertContains(self.client.get(reverse('task_history')), 'Original')
        self.assertContains(self.client.get(reverse('task_history')), 'Задача удалена')
        other = get_user_model().objects.create_user('stranger')
        self.client.force_login(other)
        self.assertNotContains(self.client.get(reverse('task_history')), 'Original')

    def test_failure_cannot_leave_status_without_event(self):
        with patch('planner.task_history.TaskStateEvent.objects.create', side_effect=RuntimeError('unavailable')):
            with self.assertRaises(RuntimeError):
                set_task_state(self.user, self.task.pk, True, 0)
        self.task.refresh_from_db()
        self.assertFalse(self.task.is_done)
        self.assertEqual(self.task.status_revision, 0)

    def test_edit_form_does_not_overwrite_completion(self):
        set_task_state(self.user, self.task.pk, True, 0)
        url=reverse('task_edit', args=[self.task.pk])
        version=self.client.get(url).context['form']['expected_updated_at'].value()
        self.assertEqual(self.client.post(url, {'title': 'Edited', 'priority': 2, 'planned_minutes': 40, 'expected_updated_at':version}).status_code,302)
        self.task.refresh_from_db()
        self.assertTrue(self.task.is_done)
        self.assertEqual(self.task.status_revision, 1)
