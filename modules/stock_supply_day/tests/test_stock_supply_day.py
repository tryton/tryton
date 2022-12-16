# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import datetime
from decimal import Decimal
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.pool import Pool

from trytond.modules.company.tests import create_company, set_company
from trytond.modules.account.tests import create_chart


class StockSupplyDayTestCase(ModuleTestCase):
    'Test StockSupplyDay module'
    module = 'stock_supply_day'

    def test_compute_supply_date(self):
        'Test compute_supply_date'
        dates = [
            # purchase date, lead time, weekday, supply date
            (datetime.date(2011, 11, 21), datetime.timedelta(10), 0,
                datetime.date(2011, 12, 5)),
            (datetime.date(2011, 11, 21), datetime.timedelta(9), 1,
                datetime.date(2011, 12, 6)),
            (datetime.date(2011, 11, 21), datetime.timedelta(8), 2,
                datetime.date(2011, 11, 30)),
            (datetime.date(2011, 11, 21), datetime.timedelta(7), 3,
                datetime.date(2011, 12, 1)),
            (datetime.date(2011, 11, 21), datetime.timedelta(6), 4,
                datetime.date(2011, 12, 2)),
            (datetime.date(2011, 11, 21), datetime.timedelta(5), 5,
                datetime.date(2011, 11, 26)),
            (datetime.date(2011, 11, 21), datetime.timedelta(4), 6,
                datetime.date(2011, 11, 27)),
            (datetime.date(2011, 12, 22), datetime.timedelta(12), 6,
                datetime.date(2012, 1, 8)),
            (datetime.date(2011, 11, 21), datetime.timedelta(10), None,
                datetime.date(2011, 12, 1)),
            (datetime.date(2011, 11, 21), None, 0, datetime.date.max),
            ]
        # Purchase date is Monday, 2011-11-21, the regular days to deliver is
        # 10 days, which would be Wednesday 2011-12-01. But with the supplier
        # weekday 0 (Monday) the forecast supply date is next Monday, the
        # 2011-12-05.

        @with_transaction()
        def run(purchase_date, lead_time, weekday, supply_date):
            product_supplier = self.create_product_supplier_day(
                lead_time, weekday)
            date = product_supplier.compute_supply_date(purchase_date)
            self.assertEqual(date, supply_date)
        for purchase_date, lead_time, weekday, supply_date in dates:
            run(purchase_date, lead_time, weekday, supply_date)

    def test_compute_purchase_date(self):
        'Test compute_purchase_date'
        dates = [
            # purchase date, lead time, weekday, supply date
            (datetime.date(2011, 11, 25), datetime.timedelta(10), 0,
                datetime.date(2011, 12, 6)),
            (datetime.date(2011, 11, 27), datetime.timedelta(9), 1,
                datetime.date(2011, 12, 6)),
            (datetime.date(2011, 11, 22), datetime.timedelta(8), 2,
                datetime.date(2011, 12, 6)),
            (datetime.date(2011, 11, 24), datetime.timedelta(7), 3,
                datetime.date(2011, 12, 6)),
            (datetime.date(2011, 11, 26), datetime.timedelta(6), 4,
                datetime.date(2011, 12, 6)),
            (datetime.date(2011, 11, 28), datetime.timedelta(5), 5,
                datetime.date(2011, 12, 6)),
            (datetime.date(2011, 11, 30), datetime.timedelta(4), 6,
                datetime.date(2011, 12, 6)),
            (datetime.date(2011, 12, 27), datetime.timedelta(6), 0,
                datetime.date(2012, 1, 3)),
            ]
        # Supply date max is Tuesday, 2012-01-03, the supplier weekday 0 which
        # would be Monday 2012-01-02. But with the 6 days of delivery the
        # forecast purchase date is the 2011-12-27.

        @with_transaction()
        def run(purchase_date, lead_time, weekday, supply_date):
            product_supplier = self.create_product_supplier_day(
                lead_time, weekday)
            date = product_supplier.compute_purchase_date(supply_date)
            self.assertEqual(date, purchase_date)
        for purchase_date, lead_time, weekday, supply_date in dates:
            run(purchase_date, lead_time, weekday, supply_date)

    def create_product_supplier_day(self, lead_time, weekday):
        '''
        Create a Product with a Product Supplier Day

        :param lead_time: minimal timedelta needed to supply
        :param weekday: supply day of the week (0 - 6)
        :return: the id of the Product Supplier Day
        '''
        pool = Pool()
        Uom = pool.get('product.uom')
        UomCategory = pool.get('product.uom.category')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Party = pool.get('party.party')
        Account = pool.get('account.account')
        ProductSupplier = pool.get('purchase.product_supplier')
        ProductSupplierDay = pool.get('purchase.product_supplier.day')
        Day = pool.get('ir.calendar.day')

        uom_category, = UomCategory.create([{'name': 'Test'}])
        uom, = Uom.create([{
                    'name': 'Test',
                    'symbol': 'T',
                    'category': uom_category.id,
                    'rate': 1.0,
                    'factor': 1.0,
                    }])
        template, = Template.create([{
                    'name': 'ProductTest',
                    'default_uom': uom.id,
                    'list_price': Decimal(0),
                    }])
        product, = Product.create([{
                    'template': template.id,
                    }])
        company = create_company()
        with set_company(company):
            create_chart(company)
            receivable, = Account.search([
                ('type.receivable', '=', True),
                ('company', '=', company.id),
                ])
            payable, = Account.search([
                ('type.payable', '=', True),
                ('company', '=', company.id),
                ])
            supplier, = Party.create([{
                        'name': 'supplier',
                        'account_receivable': receivable.id,
                        'account_payable': payable.id,
                        }])
            product_supplier, = ProductSupplier.create([{
                        'template': template.id,
                        'company': company.id,
                        'party': supplier.id,
                        'lead_time': lead_time,
                        }])
            if weekday is not None:
                day, = Day.search([('index', '=', weekday)])
                ProductSupplierDay.create([{
                            'product_supplier': product_supplier.id,
                            'day': day.id,
                            }])
            return product_supplier


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        StockSupplyDayTestCase))
    return suite
