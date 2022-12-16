# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.tests.test_tryton import ModuleTestCase


class StockLocationMoveTestCase(ModuleTestCase):
    'Test Stock Location Move module'
    module = 'stock_location_move'
    extras = ['stock_supply']


del ModuleTestCase
