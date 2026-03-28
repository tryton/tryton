# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.modules.company.tests import CompanyTestMixin
from trytond.tests.test_tryton import ModuleTestCase


class AccountStockEuExciseTestCase(CompanyTestMixin, ModuleTestCase):
    "Test Account Stock Eu Excise module"
    module = 'account_stock_eu_excise'
    extras = ['product_measurements', 'production']


del ModuleTestCase
