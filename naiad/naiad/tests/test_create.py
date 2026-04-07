# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from .common import NaiadTestCase


class CreateTestCase(NaiadTestCase):

    def test_create(self):
        "Test create"
        record = self.client().create('res.group', {
                'name': "Test",
                })

        self.assertEqual(record._model, 'res.group')
        self.assertGreaterEqual(record.id, 0)

    def test_create_fields(self):
        "Test create with fields"
        record = self.client().create('res.group', {
                'name': "Test w/ fields",
                }, fields=['name'])

        self.assertEqual(record._model, 'res.group')
        self.assertEqual(record.name, "Test w/ fields")
        self.assertGreaterEqual(record.id, 0)
