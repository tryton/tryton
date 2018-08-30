# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from unittest.mock import patch

from trytond.bus import _MessageQueue


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


def suite():
    suite_ = unittest.TestSuite()
    suite_.addTests(unittest.TestLoader().loadTestsFromTestCase(
            MessageQueueTestCase))
    return suite_
