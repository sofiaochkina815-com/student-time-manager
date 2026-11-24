from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone
from .models import WeekPlan
from .week_planning import save_week_plan


class WeekPlanningTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('budget-version')
        today=timezone.localdate();self.start=today-timedelta(days=today.weekday())

    def test_two_new_tabs_and_later_stale_edit(self):
        plan=save_week_plan(self.user,self.start,0,120)
        with self.assertRaises(ValidationError):save_week_plan(self.user,self.start,0,900)
        save_week_plan(self.user,self.start,plan.revision,180)
        with self.assertRaises(ValidationError):save_week_plan(self.user,self.start,plan.revision,600)
        plan.refresh_from_db();self.assertEqual((plan.capacity_minutes,plan.revision),(180,2))

    def test_validation_and_disabled_user(self):
        for capacity in [-1,10081]:
            with self.assertRaises(ValidationError):save_week_plan(self.user,self.start,0,capacity)
        with self.assertRaises(ValidationError):save_week_plan(self.user,self.start+timedelta(days=1),0,60)
        self.user.is_active=False;self.user.save()
        with self.assertRaises(PermissionDenied):save_week_plan(self.user,self.start,0,60)
        self.assertFalse(WeekPlan.objects.exists())

    def test_http_requires_revision_and_is_private(self):
        self.client.force_login(self.user)
        url='/week/?week='+self.start.isoformat()
        self.assertContains(self.client.post(url,{'capacity_minutes':60}),'expected_revision')
        self.assertFalse(WeekPlan.objects.exists())
        self.assertEqual(self.client.post(url,{'capacity_minutes':60,'expected_revision':0}).status_code,302)
        other=get_user_model().objects.create_user('other-budget')
        self.client.force_login(other)
        self.assertEqual(self.client.post(url,{'capacity_minutes':10,'expected_revision':0}).status_code,302)
        self.assertEqual(WeekPlan.objects.get(owner=self.user).capacity_minutes,60)
