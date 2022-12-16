# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest
import datetime
from decimal import Decimal
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.tests.test_tryton import doctest_teardown
from trytond.tests.test_tryton import doctest_checker
from trytond.pool import Pool

from trytond.modules.company.tests import create_company, set_company
from trytond.modules.account.tests import create_chart

DATES = [
    # purchase date, lead time, supply date
    (datetime.date(2011, 11, 21), datetime.timedelta(10),
        datetime.date(2011, 12, 1)),
    (datetime.date(2011, 11, 21), datetime.timedelta(9),
        datetime.date(2011, 11, 30)),
    (datetime.date(2011, 11, 21), datetime.timedelta(8),
        datetime.date(2011, 11, 29)),
    (datetime.date(2011, 11, 21), datetime.timedelta(7),
        datetime.date(2011, 11, 28)),
    (datetime.date(2011, 11, 21), datetime.timedelta(6),
        datetime.date(2011, 11, 27)),
    (datetime.date(2011, 11, 21), datetime.timedelta(5),
        datetime.date(2011, 11, 26)),
    (datetime.date(2011, 11, 21), datetime.timedelta(4),
        datetime.date(2011, 11, 25)),
    ]


class StockSupplyTestCase(ModuleTestCase):
    'Test StockSupply module'
    module = 'stock_supply'

    def test_compute_supply_date(self):
        'Test compute_supply_date'
        @with_transaction()
        def run(purchase_date, lead_time, supply_date):
            pool = Pool()
            ProductSupplier = pool.get('purchase.product_supplier')
            product_supplier = self.create_product_supplier(lead_time)
            date = ProductSupplier.compute_supply_date(
                product_supplier, purchase_date)
            self.assertEqual(date, supply_date)
        for purchase_date, lead_time, supply_date in DATES:
            run(purchase_date, lead_time, supply_date)

    def test_compute_purchase_date(self):
        'Test compute_purchase_date'
        @with_transaction()
        def run(purchase_date, lead_time, supply_date):
            pool = Pool()
            ProductSupplier = pool.get('purchase.product_supplier')
            product_supplier = self.create_product_supplier(lead_time)
            date = ProductSupplier.compute_purchase_date(
                product_supplier, supply_date)
            self.assertEqual(date, purchase_date)
        for purchase_date, lead_time, supply_date in DATES:
            run(purchase_date, lead_time, supply_date)

    def create_product_supplier(self, lead_time):
        '''
        Create a Product with a Product Supplier

        :param lead_time: timedelta needed to supply
        :return: the id of the Product Supplier
        '''
        pool = Pool()
        Uom = pool.get('product.uom')
        UomCategory = pool.get('product.uom.category')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Party = pool.get('party.party')
        Account = pool.get('account.account')
        ProductSupplier = pool.get('purchase.product_supplier')

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
                    'cost_price': Decimal(0),
                    }])
        product, = Product.create([{
                    'template': template.id,
                    }])
        company = create_company()
        with set_company(company):
            create_chart(company)
            receivable, = Account.search([
                ('kind', '=', 'receivable'),
                ('company', '=', company.id),
                ])
            payable, = Account.search([
                ('kind', '=', 'payable'),
                ('company', '=', company.id),
                ])
            supplier, = Party.create([{
                        'name': 'supplier',
                        'account_receivable': receivable.id,
                        'account_payable': payable.id,
                        }])
            product_supplier, = ProductSupplier.create([{
                        'product': template.id,
                        'company': company.id,
                        'party': supplier.id,
                        'lead_time': lead_time,
                        }])
            return product_supplier


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        StockSupplyTestCase))
    suite.addTests(doctest.DocFileSuite('scenario_stock_internal_supply.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_stock_internal_supply_lead_time.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_stock_supply_purchase_request.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_stock_internal_supply_overflow.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
