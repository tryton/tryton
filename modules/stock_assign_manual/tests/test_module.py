# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.tests.test_tryton import ModuleTestCase


class StockAssignManualTestCase(ModuleTestCase):
    'Test Stock Assign Manual module'
    module = 'stock_assign_manual'
    extras = ['production']


del ModuleTestCase
