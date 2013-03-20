#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import sys
import os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
from decimal import Decimal

import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, test_view,\
    test_depends
from trytond.transaction import Transaction


class StockSplitTestCase(unittest.TestCase):
    '''
    Test Stock Lot module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module('stock_split')
        self.uom = POOL.get('product.uom')
        self.template = POOL.get('product.template')
        self.product = POOL.get('product.product')
        self.location = POOL.get('stock.location')
        self.company = POOL.get('company.company')
        self.user = POOL.get('res.user')
        self.move = POOL.get('stock.move')

    def test0005views(self):
        '''
        Test views.
        '''
        test_view('stock_split')

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()

    def test0010split(self):
        '''
        Test split.
        '''
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            unit, = self.uom.search([('name', '=', 'Unit')])
            template, = self.template.create([{
                        'name': 'Test Split',
                        'type': 'goods',
                        'cost_price_method': 'fixed',
                        'default_uom': unit.id,
                        'list_price': Decimal(0),
                        'cost_price': Decimal(0),
                        }])
            product, = self.product.create([{
                        'template': template.id,
                        }])
            input_, = self.location.search([('code', '=', 'IN')])
            storage, = self.location.search([('code', '=', 'STO')])
            company, = self.company.search([('rec_name', '=', 'B2CK')])
            self.user.write([self.user(USER)], {
                    'main_company': company.id,
                    'company': company.id,
                    })

            def create_move(quantity):
                move, = self.move.create([{
                            'product': product.id,
                            'uom': unit.id,
                            'quantity': quantity,
                            'from_location': input_.id,
                            'to_location': storage.id,
                            'company': company.id,
                            }])
                return move

            move = create_move(10)
            moves = move.split(5, unit)
            self.assertEqual(len(moves), 2)
            self.assertEqual([m.quantity for m in moves], [5, 5])

            move = create_move(13)
            moves = move.split(5, unit)
            self.assertEqual(len(moves), 3)
            self.assertEqual([m.quantity for m in moves], [5, 5, 3])

            move = create_move(7)
            moves = move.split(8, unit)
            self.assertEqual(moves, [move])
            self.assertEqual(move.quantity, 7)

            move = create_move(20)
            moves = move.split(5, unit, count=2)
            self.assertEqual(len(moves), 3)
            self.assertEqual([m.quantity for m in moves], [5, 5, 10])

            move = create_move(20)
            moves = move.split(5, unit, count=4)
            self.assertEqual(len(moves), 4)
            self.assertEqual([m.quantity for m in moves], [5, 5, 5, 5])

            move = create_move(10)
            moves = move.split(5, unit, count=3)
            self.assertEqual(len(moves), 2)
            self.assertEqual([m.quantity for m in moves], [5, 5])

            move = create_move(10)
            self.move.write([move], {
                    'state': 'assigned',
                    })
            moves = move.split(5, unit)
            self.assertEqual(len(moves), 2)
            self.assertEqual([m.quantity for m in moves], [5, 5])
            self.assertEqual([m.state for m in moves],
                ['assigned', 'assigned'])


def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.company.tests import test_company
    for test in test_company.suite():
        if test not in suite:
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            StockSplitTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
