# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.tests.test_tryton import ModuleTestCase


class AccountCashRoundingTestCase(ModuleTestCase):
    'Test Account Cash Rounding module'
    module = 'account_cash_rounding'
    extras = ['account_invoice', 'purchase', 'sale']


del ModuleTestCase
