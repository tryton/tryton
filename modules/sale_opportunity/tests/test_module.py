# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.modules.company.tests import CompanyTestMixin
from trytond.modules.party.tests import PartyCheckReplaceMixin
from trytond.tests.test_tryton import ModuleTestCase


class SaleOpportunityTestCase(
        PartyCheckReplaceMixin, CompanyTestMixin, ModuleTestCase):
    'Test SaleOpportunity module'
    module = 'sale_opportunity'


del ModuleTestCase
