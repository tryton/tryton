# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import unittest

from trytond.pool import Pool
from trytond.transaction import Transaction
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
    def test_browse_context(self):
        'Test context when browsing'
        pool = Pool()
        ModelStorageContext = pool.get('test.modelstorage.context')

        record, = ModelStorageContext.create([{}])
        record_context = {'_check_access': False}  # From Function.get

        self.assertDictEqual(record.context, record_context)

        # Clean the instance cache
        record = ModelStorageContext(record.id)

        with Transaction().set_context(foo='bar'):
            self.assertDictEqual(record.context, record_context)

            record = ModelStorageContext(record.id)
            self.assertDictContainsSubset({'foo': 'bar'}, record.context)


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ModelStorageTestCase)
