# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.modules.company.tests import CompanyTestMixin
from trytond.tests.test_tryton import ModuleTestCase


class StockQuantityEarlyPlanningTestCase(CompanyTestMixin, ModuleTestCase):
    'Test Stock Quantity Early Planning module'
    module = 'stock_quantity_early_planning'
    extras = ['production']


del ModuleTestCase
