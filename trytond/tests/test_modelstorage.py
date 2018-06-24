# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import unittest

from trytond.pool import Pool
from trytond.tests.test_tryton import install_module, with_transaction


class ModelStorageTestCase(unittest.TestCase):
    'Test ModelStorage'

    @classmethod
    def setUpClass(cls):
        install_module('tests')

    @with_transaction()
    def test_search_read_order(self):
        'Test search_read order'
        pool = Pool()
        ModelStorage = pool.get('test.modelstorage')

        ModelStorage.create([{'name': i} for i in ['foo', 'bar', 'test']])

        rows = ModelStorage.search_read([])
        self.assertTrue(
            all(x['id'] < y['id'] for x, y in zip(rows, rows[1:])))

        rows = ModelStorage.search_read([], order=[('name', 'ASC')])
        self.assertTrue(
            all(x['name'] <= y['name'] for x, y in zip(rows, rows[1:])))

        rows = ModelStorage.search_read([], order=[('name', 'DESC')])
        self.assertTrue(
            all(x['name'] >= y['name'] for x, y in zip(rows, rows[1:])))

    @with_transaction()
    def test_copy_order(self):
        "Test copy order"
        pool = Pool()
        ModelStorage = pool.get('test.modelstorage')

        # Use both order to avoid false positive by chance
        records = ModelStorage.create(
            [{'name': n} for n in ['foo', 'bar', 'test']])
        new_records = ModelStorage.copy(records)
        reversed_records = list(reversed(records))
        new_reversed_records = ModelStorage.copy(reversed_records)

        self.assertListEqual(
            [r.name for r in records],
            [r.name for r in new_records])
        self.assertListEqual(
            [r.name for r in reversed_records],
            [r.name for r in new_reversed_records])


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ModelStorageTestCase)
