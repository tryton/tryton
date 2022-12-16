# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from unittest.mock import Mock, patch

from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class AccountStockAngloSaxonTestCase(ModuleTestCase):
    'Test Account Stock Anglo Saxon module'
    module = 'account_stock_anglo_saxon'

    @with_transaction()
    def test_get_anglo_saxon_move(self):
        'Test _get_anglo_saxon_move'
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
                patch.object(Uom, 'compute_price') as compute_price, \
                patch.object(Currency, 'compute') as compute:
            compute_qty.side_effect = lambda *args, **kwargs: args[1]
            compute_price.side_effect = lambda *args, **kwargs: args[1]
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


del ModuleTestCase
