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
            unit_id, = self.uom.search([('name', '=', 'Unit')])
            unit = self.uom.browse(unit_id)
            product_id = self.product.create({
                    'name': 'Test Split',
                    'type': 'goods',
                    'cost_price_method': 'fixed',
                    'default_uom': unit_id,
                    })
            input_id, = self.location.search([('code', '=', 'IN')])
            storage_id, = self.location.search([('code', '=', 'STO')])
            company_id, = self.company.search([('name', '=', 'B2CK')])
            self.user.write(USER, {
                'main_company': company_id,
                'company': company_id,
                })

            def create_move(quantity):
                move_id = self.move.create({
                        'product': product_id,
                        'uom': unit_id,
                        'quantity': quantity,
                        'from_location': input_id,
                        'to_location': storage_id,
                        'company': company_id,
                        })
                return self.move.browse(move_id)

            move = create_move(10)
            move_ids = self.move.split(move, 5, unit)
            self.assertEqual(len(move_ids), 2)
            self.assertEqual([m.quantity for m in self.move.browse(move_ids)],
                [5, 5])

            move = create_move(13)
            move_ids = self.move.split(move, 5, unit)
            self.assertEqual(len(move_ids), 3)
            self.assertEqual([m.quantity for m in self.move.browse(move_ids)],
                [5, 5, 3])

            move = create_move(7)
            move_ids = self.move.split(move, 8, unit)
            self.assertEqual(move_ids, [move.id])
            self.assertEqual(move.quantity, 7)

            move = create_move(20)
            move_ids = self.move.split(move, 5, unit, count=2)
            self.assertEqual(len(move_ids), 3)
            self.assertEqual([m.quantity for m in self.move.browse(move_ids)],
                [5, 5, 10])

            move = create_move(20)
            move_ids = self.move.split(move, 5, unit, count=4)
            self.assertEqual(len(move_ids), 4)
            self.assertEqual([m.quantity for m in self.move.browse(move_ids)],
                [5, 5, 5, 5])

            move = create_move(10)
            move_ids = self.move.split(move, 5, unit, count=3)
            self.assertEqual(len(move_ids), 2)
            self.assertEqual([m.quantity for m in self.move.browse(move_ids)],
                [5, 5])

            move = create_move(10)
            self.move.write(move.id, {
                    'state': 'assigned',
                    })
            move_ids = self.move.split(move, 5, unit)
            self.assertEqual(len(move_ids), 2)
            self.assertEqual([m.quantity for m in self.move.browse(move_ids)],
                [5, 5])
            self.assertEqual([m.state for m in self.move.browse(move_ids)],
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
