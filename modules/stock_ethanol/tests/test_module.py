# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal

from trytond.modules.company.tests import create_company, set_company
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class StockEthanolTestCase(ModuleTestCase):
    "Test Stock Ethanol module"
    module = 'stock_ethanol'
    extras = [
        'account_stock_eu_excise',
        'product_measurements',
        'product_price_list']

    @with_transaction()
    def test_convert_quantity(self):
        "Test convert quantity"
        pool = Pool()
        ExciseTax = pool.get('account.stock.eu.excise.tax')
        Product = pool.get('product.product')
        UoM = pool.get('product.uom')
        liter, = UoM.search([('name', '=', "Liter")])

        excise_tax = ExciseTax(
            quantity='ethanol_volume',
            uom=liter,
            )
        product = Product(
            ethanol_by_volume_used=.2,
            default_uom=liter,
            )

        self.assertEqual(excise_tax.convert_quantity(product, 10), 2)

    @with_transaction()
    def test_convert_quantity_volume(self):
        "Test convert quantity volume"
        pool = Pool()
        ExciseTax = pool.get('account.stock.eu.excise.tax')
        Product = pool.get('product.product')
        UoM = pool.get('product.uom')
        liter, = UoM.search([('name', '=', "Liter")])
        unit, = UoM.search([('name', '=', "Unit")])

        excise_tax = ExciseTax(
            quantity='ethanol_volume',
            uom=liter,
            )
        product = Product(
            ethanol_by_volume_used=.2,
            default_uom=unit,
            volume=.5,
            volume_uom=liter,
            )

        self.assertEqual(excise_tax.convert_quantity(product, 10), 1)

    @with_transaction()
    def test_price_list_context_formula(self):
        "Test price list context formula"
        pool = Pool()
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        UoM = pool.get('product.uom')
        PriceList = pool.get('product.price_list')

        unit, = UoM.search([('name', '=', "Liter")])
        cm3, = UoM.search([('name', '=', "Cubic centimeter")])

        company = create_company()
        with set_company(company):
            template = Template(
                name="Product", default_uom=unit, products=None,
                list_price=Decimal('100'),
                contain_ethanol=True, ethanol_by_volume=.2)
            template.save()
            product = Product(template=template)
            product.save()

            price_list = PriceList(
                name="List", price='list_price',
                lines=[{
                        'formula': 'unit_price - .05 * ethanol_volume',
                        'ethanol_volume_uom': cm3,
                        }])
            price_list.save()

            self.assertEqual(price_list.compute(product, 5, unit), Decimal(90))


del ModuleTestCase
