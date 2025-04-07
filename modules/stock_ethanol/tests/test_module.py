# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class StockEthanolTestCase(ModuleTestCase):
    "Test Stock Ethanol module"
    module = 'stock_ethanol'
    extras = ['account_stock_eu_excise', 'product_measurements']

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


del ModuleTestCase
