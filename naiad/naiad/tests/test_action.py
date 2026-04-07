# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from unittest.mock import patch

from naiad import Record

from .common import NaiadTestCase


class ActionTestCase(NaiadTestCase):

    def setUp(self):
        super().setUp()
        patcher = patch('trytond.res.user._send_email')
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_action(self):
        "Test action"
        preferences = self.client().action('res.user', 'get_preferences')

        self.assertIsInstance(preferences, dict)

    def test_action_record(self):
        "Test action on record"
        record = Record('res.user', id=1)
        record = self.client().action(
            record, 'reset_password', fields=['password_reset'])

        self.assertIsNotNone(record.password_reset)

    def test_action_arguments(self):
        "Test action with arguments"
        record = self.client().action(
            'res.user', 'reset_password', id=1, fields=['password_reset'],
            kwargs={
                'length': 12,
                })

        self.assertEqual(len(record.password_reset), 12)
