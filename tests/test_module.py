# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime

from trytond.modules.account.tests import create_chart
from trytond.modules.company.tests import (
    CompanyTestMixin, create_company, set_company)
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction

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


class StockSupplyTestCase(CompanyTestMixin, ModuleTestCase):
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
            return product_supplier

    @with_transaction()
    def test_order_point_location_searcher(self):
        pool = Pool()
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Location = pool.get('stock.location')
        OrderPoint = pool.get('stock.order_point')
        unit, = Uom.search([('symbol', '=', 'u')])
        template, = Template.create([{
                    'name': 'ProductTest',
                    'type': 'goods',
                    'default_uom': unit.id,
                    'purchase_uom': unit.id,
                    'purchasable': True,
                    }])
        product, = Product.create([{
                    'template': template.id,
                    }])

        warehouse, = Location.search([('type', '=', 'warehouse')])
        storage, = Location.search([('code', '=', 'STO')])

        company = create_company()
        with set_company(company):
            order_point, = OrderPoint.create([{
                        'product': product.id,
                        'type': 'purchase',
                        'warehouse_location': warehouse.id,
                        'min_quantity': 0.0,
                        'target_quantity': 5.0,
                        }])

            for clause, result in [
                    (('location', '=', warehouse.name), [order_point]),
                    (('location', '=', 'storage'), []),
                    (('location', '!=', warehouse.name), []),
                    (('location', '!=', 'storage'), [order_point]),
                    ]:
                self.assertListEqual(
                    OrderPoint.search(clause), result, msg=clause)


del ModuleTestCase
