# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.tests.test_tryton import ModuleTestCase


class SaleSupplyTestCase(ModuleTestCase):
    'Test SaleSupply module'
    module = 'sale_supply'
    extras = ['stock_supply']


del ModuleTestCase
