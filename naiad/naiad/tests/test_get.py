# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from naiad import Record

from .common import NaiadTestCase


class GetTestCase(NaiadTestCase):

    def test_get(self):
        "Test get"
        record = self.client().get('res.user', 1)

        self.assertEqual(record, Record('res.user', id=1))

    def test_get_fields(self):
        "Test get fields"
        record = self.client().get('res.user', 1, fields=['name'])

        self.assertEqual(
            record, Record('res.user', id=1, name="Administrator"))
