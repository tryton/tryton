# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from unittest import TestCase

from tryton.common.selection import freeze_value


class SelectionTestCase(TestCase):
    "Test common selection"

    def test_freeze_value(self):
        "Test freeze_value"
        self.assertEqual(freeze_value({'foo': 'bar'}), (('foo', 'bar'),))
        self.assertEqual(freeze_value([1, 42, 2, 3]), (1, 42, 2, 3))
        self.assertEqual(freeze_value('foo'), 'foo')
        self.assertEqual(
            freeze_value({'foo': {'bar': 42}}), (('foo', (('bar', 42),)),))
