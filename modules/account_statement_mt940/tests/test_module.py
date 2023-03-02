# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.tests.test_tryton import ModuleTestCase


class AccountStatementMt940TestCase(ModuleTestCase):
    "Test Account Statement Mt940 module"
    module = 'account_statement_mt940'


del ModuleTestCase
