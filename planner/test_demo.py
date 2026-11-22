from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from .demo import seed_demo
from .models import DemoDataset, Task, TimeEntry


class DemoTests(TestCase):
    def test_reproducible_isolated_idempotent_scenario(self):
        user=get_user_model().objects.create_user('demo')
        other=get_user_model().objects.create_user('other')
        marker,created=seed_demo(user)
        self.assertTrue(created)
        self.assertEqual(Task.objects.filter(owner=user).count(),14)
        self.assertEqual(TimeEntry.objects.filter(task__owner=user).count(),14)
        self.assertEqual(Task.objects.filter(owner=other).count(),0)
        self.assertFalse(seed_demo(user)[1])
        self.assertEqual(TimeEntry.objects.count(),14)
        self.assertEqual(DemoDataset.objects.count(),1)

    def test_refuses_existing_account_without_partial_write(self):
        user=get_user_model().objects.create_user('existing')
        Task.objects.create(owner=user,title='Личная задача')
        with self.assertRaises(ValidationError):seed_demo(user)
        self.assertEqual(Task.objects.count(),1)
        self.assertFalse(DemoDataset.objects.exists())
