# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.tests.test_tryton import ModuleTestCase


class AccountStockLandedCostTestCase(ModuleTestCase):
    'Test Account Stock Landed Cost module'
    module = 'account_stock_landed_cost'


del ModuleTestCase
