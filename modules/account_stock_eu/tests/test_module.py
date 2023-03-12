# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.tests.test_tryton import ModuleTestCase


class AccountStockEuTestCase(ModuleTestCase):
    "Test Account Stock Eu module"
    module = 'account_stock_eu'
    extras = ['carrier', 'incoterm', 'stock_consignment']


del ModuleTestCase
