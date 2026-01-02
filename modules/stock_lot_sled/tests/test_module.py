# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.modules.company.tests import (
    CompanyTestMixin, create_company, set_company)
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.transaction import Transaction


class StockLotSLEDTestCase(CompanyTestMixin, ModuleTestCase):
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
            default_uom=u,
            shelf_life_state='optional',
            )
        template.save()
        product = Product(template=template)
        product.save()

        supplier, = Location.search([('code', '=', 'SUP')])
        storage, = Location.search([('code', '=', 'STO')])

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
                unit=u,
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

            empty = 0
            computed = 5
            delta = -5
            for context, quantity in [
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
                    quantities = Product.products_by_location(
                        [storage.id], grouping_filter=([product.id],))
                    self.assertEqual(
                        quantities[(storage.id, product.id)],
                        quantity,
                        msg='context: %s' % repr(context))

                    quantities = Product.products_by_location(
                        [storage.id], grouping_filter=([product.id],),
                        with_childs=True)
                    self.assertEqual(
                        quantities[(storage.id, product.id)],
                        quantity,
                        msg='context: %s, with childs' % repr(context))

                    quantities = Product.products_by_location(
                        [storage.id],
                        grouping=('product.template',),
                        grouping_filter=([product.template.id],),)
                    self.assertEqual(
                        quantities[(storage.id, product.template.id)],
                        quantity,
                        msg='template, context: %s' % repr(context))

                    quantities = Product.products_by_location(
                        [storage.id],
                        grouping=('product.template',),
                        grouping_filter=([product.template.id],),
                        with_childs=True)
                    self.assertEqual(
                        quantities[(storage.id, product.template.id)],
                        quantity,
                        msg='template, context: %s, with_childs' %
                        repr(context))

            for context, delay, quantity in [
                    ({'stock_date_end': datetime.date.min},
                        datetime.timedelta(days=-1), empty),
                    ({'stock_date_end': datetime.date.max},
                        datetime.timedelta(days=1), empty),
                    ]:
                config.shelf_life_delay = delay
                config.save()
                with Transaction().set_context(context=context,
                        locations=[storage.id]):
                    quantities = Product.products_by_location(
                        [storage.id], grouping_filter=([product.id],))
                    self.assertEqual(
                        quantities[(storage.id, product.id)],
                        quantity,
                        msg='context: %s; shelf_life_delay: %s' %
                        (repr(context), delay))


del ModuleTestCase
