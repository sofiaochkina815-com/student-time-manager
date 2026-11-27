from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, Client
from django.utils import timezone
from .models import Task, TimeEntry, WorkloadSnapshot, WeekPlan
from .snapshots import capture, digest


class WorkloadSnapshotTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('snapshot-owner')
        self.client.force_login(self.user)
        today=timezone.localdate();self.start=today-timedelta(days=today.weekday())
        self.values={'week':self.start,'command_key':uuid4()}
        self.task=Task.objects.create(owner=self.user,title='Original',due_date=self.start,planned_minutes=100)
        TimeEntry.objects.create(task=self.task,date=self.start,minutes=20)
        WeekPlan.objects.create(owner=self.user,week_start=self.start,capacity_minutes=50)

    def test_snapshot_does_not_follow_edits_or_deletion_and_retry_keeps_original(self):
        item=capture(self.user,self.values)
        self.assertEqual((item.payload['required'],item.payload['available']),(80,30))
        Task.objects.filter(pk=self.task.pk).update(title='Changed',planned_minutes=999)
        self.assertEqual(capture(self.user,self.values).pk,item.pk)
        self.task.delete()
        item.refresh_from_db();self.assertEqual(item.payload['rows'][0]['title'],'Original')
        self.assertEqual(item.sha256,digest(item.payload))
        self.assertContains(self.client.get(f'/workload/snapshots/{item.pk}/'),'Original')
        response=self.client.get(f'/workload/snapshots/{item.pk}/?format=json')
        self.assertEqual(response.json()['payload'],item.payload)
        self.assertEqual(response['Cache-Control'],'private, no-store')
        with patch('planner.workload.timezone.localdate',return_value=self.start+timedelta(days=14)):
            self.assertEqual(capture(self.user,self.values).pk,item.pk)

    def test_validation_key_collision_and_limit(self):
        capture(self.user,self.values)
        for changes in [{'week':self.start+timedelta(days=7)},{'command_key':'bad'}]:
            with self.assertRaises(ValidationError):capture(self.user,{**self.values,**changes})
        with patch('planner.snapshots.LIMIT',1):
            with self.assertRaises(ValidationError):capture(self.user,{**self.values,'command_key':uuid4()})
        self.assertEqual(WorkloadSnapshot.objects.count(),1)

    def test_owner_isolation_confirmation_post_csrf_and_digest(self):
        item=capture(self.user,self.values);path=f'/workload/snapshots/{item.pk}/'
        self.assertEqual(self.client.get(path+'delete/').status_code,405)
        self.assertEqual(self.client.post(path+'delete/',{}).status_code,400)
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.user)
        self.assertEqual(strict.post(path+'delete/',{'confirm':item.pk}).status_code,403)
        other=get_user_model().objects.create_user('other-snapshot');self.client.force_login(other)
        self.assertEqual(self.client.get(path).status_code,404)
        self.assertEqual(self.client.post(path+'delete/',{'confirm':item.pk}).status_code,404)
        self.client.force_login(self.user)
        WorkloadSnapshot.objects.filter(pk=item.pk).update(sha256='0'*64)
        self.assertEqual(self.client.get(path+'?format=json').status_code,409)
        self.assertEqual(self.client.post(path+'delete/',{'confirm':item.pk}).status_code,302)
        self.assertFalse(WorkloadSnapshot.objects.exists())

    def test_empty_page_flow_and_disabled_owner(self):
        response=self.client.get('/workload/')
        self.assertContains(response,'Сохранить текущий снимок')
        self.assertContains(self.client.get('/workload/snapshots/'),'Снимков пока нет')
        self.assertEqual(self.client.post('/workload/snapshots/capture/',self.values).status_code,302)
        self.user.is_active=False;self.user.save()
        with self.assertRaises(PermissionDenied):capture(self.user,self.values)

    def test_new_past_snapshot_rejected_without_reconstructing_history(self):
        with self.assertRaises(ValidationError):capture(self.user,{**self.values,'week':self.start-timedelta(days=7)})
        self.assertFalse(WorkloadSnapshot.objects.exists())

    def test_structurally_damaged_snapshot_is_refused_even_with_matching_hash(self):
        from copy import deepcopy
        item=capture(self.user,self.values)
        original=deepcopy(item.payload)
        for change in [{'rows':None},{'required':99999},{'rows':[]},{'start':'bad'},{'actual':True}]:
            payload={**original,**change}
            WorkloadSnapshot.objects.filter(pk=item.pk).update(payload=payload,sha256=digest(payload))
            self.assertEqual(self.client.get(f'/workload/snapshots/{item.pk}/').status_code,409)
            self.assertEqual(self.client.get(f'/workload/snapshots/{item.pk}/?format=json').status_code,409)
        self.assertTrue(WorkloadSnapshot.objects.filter(pk=item.pk).exists())

    def test_csv_uses_frozen_rows_and_protects_formula_text(self):
        import csv,io
        self.task.title='=SUM(1)';self.task.save()
        item=capture(self.user,self.values)
        self.task.title='Changed';self.task.save()
        response=self.client.get(f'/workload/snapshots/{item.pk}/?format=csv')
        rows=list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig')),delimiter=';'))
        self.assertEqual(rows[0]['title'],"'=SUM(1)")
        self.assertEqual(rows[0]['remaining'],'80')
        self.assertEqual(response['Cache-Control'],'private, no-store')
