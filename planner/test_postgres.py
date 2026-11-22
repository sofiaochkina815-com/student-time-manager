from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import connections
from django.test import SimpleTestCase, TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone
from config.database import postgres_database
from .models import Task, TimeEntry
from .services import record_time


class DatabaseConfigurationTests(SimpleTestCase):
    def test_tls_and_escaped_credentials_are_preserved(self):
        db=postgres_database('postgresql://u:p%40ss@db.example:5433/study?sslmode=require&connect_timeout=5&channel_binding=require')
        self.assertEqual(db['PASSWORD'],'p@ss')
        self.assertEqual(db['OPTIONS'],{'sslmode':'require','connect_timeout':5,'channel_binding':'require'})
        self.assertEqual(db['PORT'],5433)
        for value in ['sqlite:///x','postgresql://host/','postgresql://host/x?sslmode=bad','postgresql://host/x?unknown=x','postgresql://host/x?sslmode=require&sslmode=disable']:
            with self.assertRaises(ImproperlyConfigured):postgres_database(value)


class PostgreSQLConcurrencyTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_simultaneous_records_cannot_exceed_daily_limit(self):
        user=get_user_model().objects.create_user('parallel')
        task=Task.objects.create(owner=user,title='Parallel task')
        barrier=Barrier(2)
        def write():
            try:
                local_user=get_user_model().objects.get(pk=user.pk)
                barrier.wait(timeout=10)
                try:
                    record_time(user=local_user,task_id=task.pk,date=timezone.localdate(),minutes=1000)
                    return 'saved'
                except ValidationError:
                    return 'limited'
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:write(),range(2)))
        self.assertCountEqual(results,['saved','limited'])
        self.assertEqual(TimeEntry.objects.get().minutes,1000)
