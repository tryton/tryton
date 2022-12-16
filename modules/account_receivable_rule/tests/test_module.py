# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.tests.test_tryton import ModuleTestCase


class AccountReceivableRuleTestCase(ModuleTestCase):
    'Test Account Receivable Rule module'
    module = 'account_receivable_rule'


del ModuleTestCase
