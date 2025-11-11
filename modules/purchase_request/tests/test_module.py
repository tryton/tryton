# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt

from trytond.modules.company.tests import create_company, set_company
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class PurchaseRequestTestCase(ModuleTestCase):
    'Test Purchase Request module'
    module = 'purchase_request'

    @with_transaction()
    def test_find_best_product_supplier(self):
        "Test finding best product supplier"
        pool = Pool()
        ProductTemplate = pool.get('product.template')
        Product = pool.get('product.product')
        ProductSupplier = pool.get('purchase.product_supplier')
        Party = pool.get('party.party')
        UoM = pool.get('product.uom')
        PurchaseRequest = pool.get('purchase.request')
        Date = pool.get('ir.date')

        supplier = Party(name="Supplier")
        supplier.save()

        company = create_company()
        with set_company(company):
            unit, = UoM.search([('name', '=', "Unit")])
            template = ProductTemplate(name="Product")
            template.purchasable = True
            template.default_uom = unit
            template.purchase_uom = unit
            template.save()
            product = Product(template=template)
            product.save()

            product_supplier1 = ProductSupplier(
                template=template, party=supplier,
                lead_time=dt.timedelta(days=5))
            product_supplier1.save()
            product_supplier2 = ProductSupplier(
                template=template, party=supplier,
                lead_time=dt.timedelta(days=2))
            product_supplier2.save()
            product_supplier3 = ProductSupplier(
                template=template, party=supplier,
                lead_time=dt.timedelta(days=3))
            product_supplier3.save()

            today = Date.today()
            for date, product_supplier in [
                    (None, product_supplier1),
                    (today, product_supplier2),
                    (today + dt.timedelta(days=1), product_supplier2),
                    (today + dt.timedelta(days=2), product_supplier2),
                    (today + dt.timedelta(days=3), product_supplier2),
                    (today + dt.timedelta(days=4), product_supplier2),
                    (today + dt.timedelta(days=5), product_supplier1),
                    (dt.date.max, product_supplier1),
                    (dt.date.min, product_supplier2),
                    ]:
                with self.subTest(date=date):
                    self.assertEqual(
                        PurchaseRequest.find_best_product_supplier(
                            product, date),
                        product_supplier)


del ModuleTestCase
