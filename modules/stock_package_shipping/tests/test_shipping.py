# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest

from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.tests.test_tryton import suite as test_suite
from trytond.pool import Pool


class StockPackageShippingTestCase(ModuleTestCase):
    'Test Stock Package Shipping module'
    module = 'stock_package_shipping'

    @with_transaction()
    def test_package_weight(self):
        'Test package weight'
        pool = Pool()
        UoM = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Move = pool.get('stock.move')
        Package = pool.get('stock.package')

        u, = UoM.search([('symbol', '=', 'u')])
        g, = UoM.search([('symbol', '=', 'g')])

        template_u = Template(
            name='Product Unit',
            type='goods',
            list_price=0,
            cost_price=0,
            default_uom=u,
            weight=500,
            weight_uom=g,
            )
        template_u.save()
        product_u = Product(template=template_u)
        product_u.save()

        template_g = Template(
            name='Product Gram',
            type='goods',
            list_price=0,
            cost_price=0,
            default_uom=g,
            )
        template_g.save()
        product_g = Product(template=template_g)
        product_g.save()

        move1 = Move(
            product=product_u,
            uom=u,
            quantity=1,
            internal_quantity=1,
            )
        move2 = Move(
            product=product_g,
            uom=g,
            quantity=200,
            internal_quantity=200,
            )

        package = Package()
        package.moves = [move1, move2]
        self.assertEqual(package.get_weight('weight'), 0.7)


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            StockPackageShippingTestCase))
    return suite
