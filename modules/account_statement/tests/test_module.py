# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.modules.company.tests import CompanyTestMixin
from trytond.modules.party.tests import PartyCheckEraseMixin
from trytond.tests.test_tryton import ModuleTestCase


class AccountStatementTestCase(
        CompanyTestMixin, PartyCheckEraseMixin, ModuleTestCase):
    'Test AccountStatement module'
    module = 'account_statement'


del ModuleTestCase
