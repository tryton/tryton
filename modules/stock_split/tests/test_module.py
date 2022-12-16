# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.modules.company.tests import (
    CompanyTestMixin, create_company, set_company)
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class StockSplitTestCase(CompanyTestMixin, ModuleTestCase):
    'Test Stock Lot module'
    module = 'stock_split'

    @with_transaction()
    def test_split(self):
        'Test split'
        pool = Pool()
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')

        unit, = Uom.search([('name', '=', 'Unit')])
        template, = Template.create([{
                    'name': 'Test Split',
                    'type': 'goods',
                    'default_uom': unit.id,
                    }])
        product, = Product.create([{
                    'template': template.id,
                    }])
        input_, = Location.search([('code', '=', 'IN')])
        storage, = Location.search([('code', '=', 'STO')])
        company = create_company()
        with set_company(company):

            def create_move(quantity):
                move, = Move.create([{
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
            Move.write([move], {
                    'state': 'assigned',
                    })
            moves = move.split(5, unit)
            self.assertEqual(len(moves), 2)
            self.assertEqual([m.quantity for m in moves], [5, 5])
            self.assertEqual([m.state for m in moves],
                ['assigned', 'assigned'])


del ModuleTestCase
