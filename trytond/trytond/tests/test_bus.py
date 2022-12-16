# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import time
import unittest
from unittest.mock import patch

from trytond import bus, backend
from trytond.bus import _MessageQueue, notify, Bus
from trytond.tests.test_tryton import (
    activate_module, with_transaction, DB_NAME)
from trytond.transaction import Transaction


class MessageQueueTestCase(unittest.TestCase):

    def setUp(self):
        self._timestamp = 0

    def _time(self):
        _timestamp = self._timestamp
        self._timestamp += 1
        return _timestamp

    def test_get_next(self):
        "Testing the basic functionality of get_next"
        with patch('time.time', self._time):
            mq = _MessageQueue(5)
            for x in range(15):
                mq.append('channel', {'message_id': x})
            channel, content = mq.get_next({'channel'}, 11)

        self.assertEqual(content, {'message_id': 12})

    def test_get_next_channels(self):
        "Testing get_next with multiple channels"
        with patch('time.time', self._time):
            mq = _MessageQueue(5)
            for x in range(15):
                mq.append('odd' if x % 2 else 'even', {'message_id': x})
            channel, content = mq.get_next({'odd'}, 11)

        self.assertEqual(content, {'message_id': 13})
        self.assertEqual(channel, 'odd')

    def test_get_next_timeout_expired(self):
        "Testing get_next when requesting an outdated message"
        with patch('time.time', self._time):
            mq = _MessageQueue(5)
            for x in range(15):
                mq.append('channel', {'message_id': x})
            channel, content = mq.get_next({'channel'}, 0)

        self.assertEqual(content, {'message_id': 10})

    def test_get_next_message_id_missing(self):
        "Testing get_next when requesting a missing message"
        with patch('time.time', self._time):
            mq = _MessageQueue(5)
            for x in range(15):
                mq.append('channel', {'message_id': x})
            channel, content = mq.get_next({'channel'}, -5)

        self.assertEqual(content, {'message_id': 10})

    def test_get_next_message_id_None(self):
        "Testing get_next when not specifying a message"
        with patch('time.time', self._time):
            mq = _MessageQueue(5)
            for x in range(15):
                mq.append('channel', {'message_id': x})
            channel, content = mq.get_next({'channel'})

        self.assertEqual(content, {'message_id': 10})


class BusTestCase(unittest.TestCase):
    "Test Bus"

    @classmethod
    def setUpClass(cls):
        activate_module('ir')
        super().setUpClass()

    def setUp(self):
        super().setUp()

        reset_polling_timeout = bus._long_polling_timeout
        bus._long_polling_timeout = 1
        self.addCleanup(
            setattr, bus, '_long_polling_timeout', reset_polling_timeout)

        reset_select_timeout = bus._select_timeout
        bus._select_timeout = 1
        self.addCleanup(
            setattr, bus, '_select_timeout', reset_select_timeout)

    def tearDown(self):
        pid = os.getpid()
        if (pid, DB_NAME) in Bus._queues:
            with Bus._queues_lock[pid]:
                Bus._queues[pid, DB_NAME]['timeout'] = 0
                listener = Bus._queues[pid, DB_NAME]['listener']
            listener.join()
        Bus._messages.clear()

    @with_transaction()
    def test_notify(self):
        "Test notify"
        notify("Test", "Message", user=1)

    @unittest.skipIf(backend.name() == 'sqlite', 'SQLite has not channel')
    def test_subscribe_nothing(self):
        "Test subscribe with nothing"
        response = Bus.subscribe(DB_NAME, ['user:1'])

        self.assertEqual(response, {'message': None, 'channel': None})

    @unittest.skipIf(backend.name() == 'sqlite', 'SQLite has not channel')
    def test_subscribe_message(self):
        "Test subscribe with message"
        Bus.subscribe(DB_NAME, ['user:1'])

        transaction = Transaction()
        with transaction.start(DB_NAME, 1):
            notify("Test", "Message", user=1)
            transaction.commit()
        # Let the listen thread registers the message
        time.sleep(1)
        response = Bus.subscribe(DB_NAME, ['user:1'])

        self.assertTrue(response['message'].pop('message_id'))
        self.assertEqual(response, {
                'message': {
                    'type': 'notification',
                    'title': "Test",
                    'body': "Message",
                    'priority': 1,
                    },
                'channel': 'user:1',
                })


def suite():
    suite_ = unittest.TestSuite()
    suite_.addTests(unittest.TestLoader().loadTestsFromTestCase(
            MessageQueueTestCase))
    suite_.addTests(unittest.TestLoader().loadTestsFromTestCase(
            BusTestCase))
    return suite_
