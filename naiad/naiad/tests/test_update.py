# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from .common import NaiadTestCase


class UpdateTestCase(NaiadTestCase):

    def test_update(self):
        "Test update"
        record = self.client().update('res.user', 1, {
                'signature': "Admin",
                })

        self.assertEqual(record._model, 'res.user')
        self.assertGreaterEqual(record.id, 0)

    def test_update_fields(self):
        "Test update with fields"
        record = self.client().update('res.user', 1, {
                'signature': "Admin",
                }, fields=['signature'])

        self.assertEqual(record._model, 'res.user')
        self.assertEqual(record.signature, "Admin")
        self.assertGreaterEqual(record.id, 0)
