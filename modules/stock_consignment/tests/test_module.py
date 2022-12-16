# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.tests.test_tryton import ModuleTestCase


class StockConsignmentTestCase(ModuleTestCase):
    'Test Stock Consignment module'
    module = 'stock_consignment'
    extras = ['stock_supply']


del ModuleTestCase
