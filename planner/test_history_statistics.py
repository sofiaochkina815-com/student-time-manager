from datetime import timedelta,datetime,time
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from .models import Task,TaskStateEvent
from .research import compare_periods


class HistoryStatisticsTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('history-stats')
        self.today=timezone.localdate()
        self.values={'before_start':self.today-timedelta(days=3),'before_end':self.today-timedelta(days=2),
                     'after_start':self.today-timedelta(days=1),'after_end':self.today}
        self.task=Task.objects.create(owner=self.user,title='Work')

    def event(self,day,done=True,hour=12,owner=None):
        return TaskStateEvent.objects.create(owner=owner or self.user,task=self.task,title='Snapshot',
            previous_done=not done,is_done=done,planned_minutes=25,revision=1,
            recorded_at=timezone.make_aware(datetime.combine(day,time(hour))))

    def test_partial_history_is_not_zero_or_a_comparable_delta(self):
        report=compare_periods(self.user,**self.values)['history']
        self.assertIsNone(report['periods'][0]['completions'])
        self.event(self.today,True)
        report=compare_periods(self.user,**self.values)['history']
        self.assertEqual([p['coverage'] for p in report['periods']],['before','partial'])
        self.assertEqual(report['periods'][1]['completions'],1)
        self.assertFalse(report['comparable']);self.assertIsNone(report['deltas']['completions'])

    def test_full_windows_count_transitions_after_task_deletion_and_ignore_foreign(self):
        self.event(self.today-timedelta(days=5))
        self.event(self.values['before_start'])
        self.event(self.values['after_start'])
        self.event(self.values['after_start'],False)
        self.event(self.today)
        other=get_user_model().objects.create_user('foreign-history-stats')
        self.event(self.today,owner=other)
        self.task.delete()
        report=compare_periods(self.user,**self.values)['history']
        self.assertTrue(report['comparable'])
        self.assertEqual(report['deltas'],{'completions':1,'reopenings':1})
        self.assertEqual(report['periods'][0]['reopenings'],0)

    def test_local_midnight_boundary_and_invalid_json_export(self):
        with timezone.override('Asia/Tbilisi'):
            self.event(self.today-timedelta(days=5))
            event=self.event(self.values['after_start'],hour=0)
            self.assertEqual(event.recorded_at.utcoffset(),timedelta(hours=4))
            report=compare_periods(self.user,**self.values)['history']
            self.assertEqual(report['periods'][1]['completions'],1)
            self.assertEqual(report['periods'][0]['completions'],0)
        self.client.force_login(self.user)
        response=self.client.get('/research/',{**self.values,'format':'json','after_end':'bad'})
        self.assertEqual(response.status_code,400);self.assertIn('errors',response.json())
        response=self.client.get('/research/',{**self.values,'format':'json'})
        self.assertEqual(response.json()['schema_version'],2)
        self.assertEqual(response['Cache-Control'],'private, no-store')
