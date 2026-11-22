from unittest.mock import patch
from django.db import OperationalError
from django.test import TestCase


class HealthTests(TestCase):
    def test_ready_checks_database_without_leaking_configuration(self):
        self.assertEqual(self.client.get('/health/live/').json(),{'status':'alive'})
        self.assertEqual(self.client.get('/health/ready/').json(),{'status':'ready'})
        with patch('config.health.connection.cursor',side_effect=OperationalError('SECRET CONNECTION DETAILS')):
            response=self.client.get('/health/ready/')
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.json(),{'status':'unavailable'})
        self.assertNotContains(response,'SECRET',status_code=503)
        self.assertEqual(self.client.post('/health/ready/').status_code,405)
