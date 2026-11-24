import csv,io
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from .models import Subject,Task,TimeEntry
from .subject_analysis import subject_report


class SubjectAnalysisTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('subject-analytics')
        self.day=timezone.localdate();self.client.force_login(self.user)
        self.subject=Subject.objects.create(owner=self.user,name='=Subject')

    def test_facts_and_deadlines_are_separate_and_null_group_can_be_opened(self):
        task=Task.objects.create(owner=self.user,title='Later',subject=self.subject,planned_minutes=90,due_date=self.day+timedelta(days=1))
        TimeEntry.objects.create(task=task,date=self.day,minutes=20)
        Task.objects.create(owner=self.user,title='Due now',subject=self.subject,planned_minutes=30,due_date=self.day)
        null=Task.objects.create(owner=self.user,title='No subject')
        TimeEntry.objects.create(task=null,date=self.day,minutes=10)
        report=subject_report(self.user,self.day,self.day)
        self.assertEqual(report['totals'],{'tasks':1,'done':0,'planned':30,'actual':30,'records':2})
        self.assertEqual(report['rows'][0]['actual'],20)
        self.assertEqual(report['rows'][0]['planned'],30)
        self.assertEqual(report['rows'][1]['name'],'Без дисциплины')
        response=self.client.get('/tasks/',{'state':'all','unassigned_subject':'1'})
        self.assertContains(response,'No subject');self.assertNotContains(response,'Later')

    def test_private_csv_formula_guard_empty_summary_and_invalid_period(self):
        other=get_user_model().objects.create_user('subject-other')
        task=Task.objects.create(owner=other,title='Secret')
        TimeEntry.objects.create(task=task,date=self.day,minutes=999)
        mine=Task.objects.create(owner=self.user,title='Mine',subject=self.subject,due_date=self.day)
        TimeEntry.objects.create(task=mine,date=self.day,minutes=10)
        response=self.client.get('/analytics/subjects/',{'start':self.day,'end':self.day,'format':'csv'})
        rows=list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig')),delimiter=';'))
        self.assertEqual(rows[0]['actual'],'10');self.assertEqual(rows[1]['subject'],"'=Subject")
        self.assertEqual(response['Cache-Control'],'private, no-store')
        with self.assertRaises(ValidationError):subject_report(self.user,self.day,self.day+timedelta(days=93))
        with patch('planner.subject_analysis.MAX_SUBJECTS',0),self.assertRaises(ValidationError):subject_report(self.user,self.day,self.day)
        empty=subject_report(self.user,self.day-timedelta(days=1),self.day-timedelta(days=1))
        self.assertEqual(empty['rows'],[])
