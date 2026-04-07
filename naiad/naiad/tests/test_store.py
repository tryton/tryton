# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from naiad import Record

from .common import NaiadTestCase


class StoreTestCase(NaiadTestCase):

    def test_store_create(self):
        "Test store with creation"
        record = Record('res.group', name="Test store")
        record = self.client().store(record, fields=['name'])

        self.assertEqual(record._model, 'res.group')
        self.assertEqual(record.name, "Test store")
        self.assertGreaterEqual(record.id, 0)

    def test_store_update(self):
        "Test store with creation"
        record = Record('res.user', id=1)
        record.signature = "Admin"
        record = self.client().store(record, fields=['signature'])

        self.assertEqual(record._model, 'res.user')
        self.assertEqual(record.signature, "Admin")
        self.assertEqual(record.id, 1)
