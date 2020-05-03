# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction


class FieldFunctionTestCase(unittest.TestCase):
    "Test Field Function"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_accessor(self):
        "Test accessing field on unsaved instance"
        pool = Pool()
        Model = pool.get('test.function.accessor')
        Target = pool.get('test.function.accessor.target')

        target = Target()
        target.save()
        record = Model()
        record.target = target

        self.assertEqual(record.function, target)


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(FieldFunctionTestCase)
