# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest
import datetime

import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import DB_NAME, USER, CONTEXT
from trytond.pool import Pool
from trytond.transaction import Transaction


class StockLotSLEDTestCase(ModuleTestCase):
    'Test Stock Lot SLED module'
    module = 'stock_lot_sled'
    longMessage = True

    def test_sled(self):
        'Test SLED'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            pool = Pool()
            Uom = pool.get('product.uom')
            Template = pool.get('product.template')
            Product = pool.get('product.product')
            Location = pool.get('stock.location')
            Company = pool.get('company.company')
            User = pool.get('res.user')
            Date = pool.get('ir.date')
            Move = pool.get('stock.move')
            Lot = pool.get('stock.lot')
            Period = pool.get('stock.period')

            u, = Uom.search([('name', '=', 'Unit')])
            template = Template(
                name='Test SLED',
                type='goods',
                list_price=0,
                cost_price=0,
                default_uom=u,
                shelf_life_state='optional',
                )
            template.save()
            product = Product(template=template)
            product.save()

            supplier, = Location.search([('code', '=', 'SUP')])
            storage, = Location.search([('code', '=', 'CUS')])

            company, = Company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ])
            user = User(USER)
            user.main_company = company
            user.company = company
            user.save()

            today = Date.today()

            lot = Lot(
                number='Test',
                product=product,
                shelf_life_expiration_date=today + datetime.timedelta(days=5),
                )
            lot.save()

            move = Move(
                product=product,
                uom=u,
                quantity=5,
                from_location=supplier,
                to_location=storage,
                planned_date=today,
                company=company,
                unit_price=0,
                currency=company.currency,
                lot=lot,
                )
            move.save()

            period = Period(date=today + datetime.timedelta(days=-10),
                company=company)
            period.save()
            Period.close([period])

            empty = {}
            computed = {(storage.id, product.id): 5}
            for context, result in [
                    ({'stock_date_end': today + datetime.timedelta(days=-1)},
                        empty),
                    ({'stock_date_end': today}, empty),
                    ({'stock_date_end': today, 'forecast': True}, computed),
                    ({'stock_date_end': today + datetime.timedelta(days=3)},
                        computed),
                    ({'stock_date_end': today + datetime.timedelta(days=5)},
                        computed),
                    ({'stock_date_end': today + datetime.timedelta(days=6)},
                        empty),
                    ({}, empty),
                    ]:
                with Transaction().set_context(context=context,
                        locations=[storage.id]):
                    quantity = Product.products_by_location(
                        [storage.id], [product.id])
                    self.assertEqual(quantity, result,
                        msg='context: %s' % repr(context))


def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.company.tests import test_company
    for test in test_company.suite():
        if test not in suite and not isinstance(test, doctest.DocTestCase):
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            StockLotSLEDTestCase))
    return suite
