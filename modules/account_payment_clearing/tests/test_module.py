# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.modules.company.tests import CompanyTestMixin
from trytond.tests.test_tryton import ModuleTestCase


class AccountPaymentTestCase(CompanyTestMixin, ModuleTestCase):
    'Test Account Payment module'
    module = 'account_payment_clearing'
    extras = ['account_statement', 'account_statement_rule']


del ModuleTestCase
