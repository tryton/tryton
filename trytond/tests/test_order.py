# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.pool import Pool


class SequenceOrderedMixinTestCase(unittest.TestCase):
    'Test SequenceOrderedMixin'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_order(self):
        'Test order'
        pool = Pool()
        Order = pool.get('test.order.sequence')

        models = []
        for i in reversed(list(range(1, 4))):
            models.append(Order(sequence=i))
        Order.save(models)
        models.reverse()
        self.assertListEqual(Order.search([]), models)

        model = models.pop()
        model.sequence = None
        model.save()
        models.insert(0, model)

        self.assertListEqual(Order.search([]), models)


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(
        SequenceOrderedMixinTestCase)
