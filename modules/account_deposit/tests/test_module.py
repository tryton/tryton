# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.modules.company.tests import (
    CompanyTestMixin, PartyCompanyCheckEraseMixin)
from trytond.tests.test_tryton import ModuleTestCase


class AccountDepositTestCase(
        PartyCompanyCheckEraseMixin, CompanyTestMixin, ModuleTestCase):
    'Test Account Deposit module'
    module = 'account_deposit'


del ModuleTestCase
