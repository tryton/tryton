# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import unittest

from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction


class ModelTestCase(unittest.TestCase):
    'Test Model'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_repr(self):
        'Test repr'
        pool = Pool()
        Model = pool.get('test.model')

        record = Model(name='foo')
        self.assertEqual(
            repr(record), "Pool().get('test.model')(**{'name': 'foo'})")

        record.save()
        self.assertEqual(
            repr(record), "Pool().get('test.model')(%s)" % record.id)


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ModelTestCase)
