# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest

from mock import Mock, patch

import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import DB_NAME, USER, CONTEXT
from trytond.tests.test_tryton import doctest_setup, doctest_teardown
from trytond.pool import Pool
from trytond.transaction import Transaction


class AccountStockAngloSaxonTestCase(ModuleTestCase):
    'Test Account Stock Anglo Saxon module'
    module = 'account_stock_anglo_saxon'

    def test_get_anglo_saxon_move(self):
        'Test _get_anglo_saxon_move'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            pool = Pool()
            Move = pool.get('stock.move')
            Uom = pool.get('product.uom')
            Currency = pool.get('currency.currency')

            def move(quantity, price):
                move = Mock()
                move.quantity = quantity
                move.unit_price = price
                move.cost_price = price
                move.in_anglo_saxon_quantity = 0
                move.out_anglo_saxon_quantity = 0
                return move

            with patch.object(Uom, 'compute_qty') as compute_qty, \
                    patch.object(Currency, 'compute') as compute:
                compute_qty.side_effect = lambda *args, **kwargs: args[1]
                compute.side_effect = lambda *args, **kwargs: args[1]

                moves = [move(1, 3), move(2, 2)]
                result = list(Move._get_anglo_saxon_move(
                        moves, 1, 'in_supplier'))
                self.assertEqual(result, [(moves[0], 1, 3)])

                moves = [move(1, 3), move(2, 2)]
                result = list(Move._get_anglo_saxon_move(
                        moves, 2, 'in_supplier'))
                self.assertEqual(result,
                    [(moves[0], 1, 3), (moves[1], 1, 2)])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        AccountStockAngloSaxonTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_account_stock_anglo_saxon.rst',
            setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_account_stock_anglo_saxon_with_drop_shipment.rst',
            setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
