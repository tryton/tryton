# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.tests.test_tryton import ModuleTestCase


class AccountStatementSepaTestCase(ModuleTestCase):
    "Test Account Statement Sepa module"
    module = 'account_statement_sepa'


del ModuleTestCase
