# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import datetime

import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.transaction import Transaction
from trytond.pool import Pool

from trytond.modules.company.tests import create_company, set_company


class StockLotSLEDTestCase(ModuleTestCase):
    'Test Stock Lot SLED module'
    module = 'stock_lot_sled'
    longMessage = True

    @with_transaction()
    def test_sled(self):
        'Test SLED'
        pool = Pool()
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Location = pool.get('stock.location')
        Date = pool.get('ir.date')
        Move = pool.get('stock.move')
        Lot = pool.get('stock.lot')
        Period = pool.get('stock.period')
        Config = pool.get('stock.configuration')

        u, = Uom.search([('name', '=', 'Unit')])
        template = Template(
            name='Test SLED',
            type='goods',
            list_price=0,
            default_uom=u,
            shelf_life_state='optional',
            )
        template.save()
        product = Product(template=template)
        product.save()

        supplier, = Location.search([('code', '=', 'SUP')])
        storage, = Location.search([('code', '=', 'CUS')])

        company = create_company()
        with set_company(company):
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

            config = Config(1)

            empty = {}
            computed = {(storage.id, product.id): 5}
            delta = {(storage.id, product.id): -5}
            for context, result in [
                    ({'stock_date_end': datetime.date.min}, empty),
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
                    ({'stock_date_start': today, 'stock_date_end': today},
                        empty),
                    ({'stock_date_start': today + datetime.timedelta(days=1),
                      'stock_date_end': today + datetime.timedelta(days=7)},
                        delta),
                    ({'stock_date_start': today + datetime.timedelta(days=1),
                      'stock_date_end': today + datetime.timedelta(days=2)},
                        empty),
                    ({'stock_date_start': today + datetime.timedelta(days=1),
                      'stock_date_end': today + datetime.timedelta(days=5)},
                        empty),
                    ({'stock_date_start': today + datetime.timedelta(days=5),
                      'stock_date_end': today + datetime.timedelta(days=6)},
                        delta),
                    ({'stock_date_start': today + datetime.timedelta(days=5),
                      'stock_date_end': today + datetime.timedelta(days=7)},
                        delta),
                    ({'stock_date_start': today + datetime.timedelta(days=6),
                      'stock_date_end': today + datetime.timedelta(days=7)},
                        empty),
                    ({'stock_date_end': datetime.date.max}, empty),
                    ]:
                with Transaction().set_context(context=context,
                        locations=[storage.id]):
                    quantity = Product.products_by_location(
                        [storage.id], grouping_filter=([product.id],))
                    self.assertEqual(quantity, result,
                        msg='context: %s' % repr(context))

                    quantity = Product.products_by_location(
                        [storage.id], grouping_filter=([product.id],),
                        with_childs=True)
                    self.assertEqual(quantity, result,
                        msg='context: %s, with childs' % repr(context))

                    quantity = Product.products_by_location(
                        [storage.id],
                        grouping=('product.template',),
                        grouping_filter=([product.template.id],),)
                    self.assertEqual(quantity, result,
                        msg='template, context: %s' % repr(context))

                    quantity = Product.products_by_location(
                        [storage.id],
                        grouping=('product.template',),
                        grouping_filter=([product.template.id],),
                        with_childs=True)
                    self.assertEqual(quantity, result,
                        msg='template, context: %s, with_childs' %
                        repr(context))

            for context, delay, result in [
                    ({'stock_date_end': datetime.date.min},
                        datetime.timedelta(days=-1), empty),
                    ({'stock_date_end': datetime.date.max},
                        datetime.timedelta(days=1), empty),
                    ]:
                config.shelf_life_delay = delay
                config.save()
                with Transaction().set_context(context=context,
                        locations=[storage.id]):
                    quantity = Product.products_by_location(
                        [storage.id], grouping_filter=([product.id],))
                    self.assertEqual(quantity, result,
                        msg='context: %s; shelf_life_delay: %s' %
                        (repr(context), delay))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            StockLotSLEDTestCase))
    return suite
