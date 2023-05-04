# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.modules.company.tests import CompanyTestMixin
from trytond.tests.test_tryton import ModuleTestCase


class CompanyAcountConsolidationTestMixin(CompanyTestMixin):

    @property
    def _skip_company_rule(self):
        return super()._skip_company_rule | {
            ('account.move', 'consolidation_company'),
            ('account.invoice', 'consolidation_company'),
            }


class AccountConsolidationTestCase(
        CompanyAcountConsolidationTestMixin, ModuleTestCase):
    "Test Account Consolidation module"
    module = 'account_consolidation'
    extras = ['account_invoice']


del ModuleTestCase
