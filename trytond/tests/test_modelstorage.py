# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import unittest

from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.tests.test_tryton import DB_NAME, USER, CONTEXT, install_module


class ModelStorageTestCase(unittest.TestCase):
    'Test ModelStorage'

    def setUp(self):
        install_module('tests')

    def test_search_read_order(self):
        'Test search_read order'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
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


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ModelStorageTestCase)
