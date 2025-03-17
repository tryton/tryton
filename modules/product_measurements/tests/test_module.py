# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal

from trytond.modules.company.tests import create_company, set_company
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class ProductMeasurementsTestCase(ModuleTestCase):
    "Test Product Measurements module"
    module = 'product_measurements'
    extras = ['product_price_list']

    @with_transaction()
    def test_price_list_context_formula_volume(self):
        "Test price list context formula with volume"
        pool = Pool()
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        UoM = pool.get('product.uom')
        PriceList = pool.get('product.price_list')

        unit, = UoM.search([('name', '=', "Unit")])
        cm3, = UoM.search([('name', '=', "Cubic centimeter")])
        inch3, = UoM.search([('name', '=', "Cubic inch")])

        company = create_company()
        with set_company(company):
            template = Template(
                name="Product", default_uom=unit, products=None,
                list_price=Decimal('100'),
                volume=2, volume_uom=cm3)
            template.save()
            product = Product(template=template)
            product.save()

            price_list = PriceList(
                name="List", price='list_price',
                lines=[{
                        'formula': 'unit_price + 5 * volume',
                        'volume_uom': inch3}])
            price_list.save()

            self.assertEqual(
                price_list.compute(product, 5, unit),
                Decimal('100.6102'))

    @with_transaction()
    def test_price_list_context_formula_weight(self):
        "Test price list context formula with weight"
        pool = Pool()
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        UoM = pool.get('product.uom')
        PriceList = pool.get('product.price_list')

        unit, = UoM.search([('name', '=', "Unit")])
        gram, = UoM.search([('name', '=', "Gram")])
        pound, = UoM.search([('name', '=', "Pound")])

        company = create_company()
        with set_company(company):
            template = Template(
                name="Product", default_uom=unit, products=None,
                list_price=Decimal('100'),
                weight=5, weight_uom=gram)
            template.save()
            product = Product(template=template)
            product.save()

            price_list = PriceList(
                name="List", price='list_price',
                lines=[{
                        'formula': 'unit_price + 5 * weight',
                        'weight_uom': pound}])
            price_list.save()

            self.assertEqual(
                price_list.compute(product, 5, unit),
                Decimal('100.0551'))


del ModuleTestCase
