# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.tests.test_tryton import ModuleTestCase


class AccountPaymentCheckTestCase(ModuleTestCase):
    "Test Account Payment Check module"
    module = 'account_payment_check'
    extras = ['account_statement_rule']


del ModuleTestCase
