# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from unittest.mock import patch

from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class ProductionSplitTestCase(ModuleTestCase):
    'Test Production Split module'
    module = 'production_split'

    @with_transaction()
    def test_split(self):
        'Test split'
        pool = Pool()
        Uom = pool.get('product.uom')
        Production = pool.get('production')

        unit, = Uom.search([('name', '=', 'Unit')])

        with patch.object(Production, 'save'), \
                patch.object(Production, 'explode_bom'), \
                patch.object(Production, 'copy') as copy:
            copy.side_effect = lambda l, values: [
                Production(**values) for r in l]
            for quantity, quantity_split, count, quantities in [
                    (10, 5, None, [5, 5]),
                    (13, 5, None, [5, 5, 3]),
                    (7, 8, None, [7]),
                    (20, 5, 2, [5, 5, 10]),
                    (20, 5, 4, [5, 5, 5, 5]),
                    ]:
                production = Production()
                production.quantity = quantity
                production.uom = unit

                productions = production.split(
                    quantity_split, unit, count=count)
                self.assertEqual(
                    [p.quantity for p in productions], quantities)


del ModuleTestCase
