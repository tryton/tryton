# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.modules.company.tests import (
    CompanyTestMixin, PartyCompanyCheckEraseMixin)
from trytond.tests.test_tryton import ModuleTestCase


class SaleRentalTestCase(
        PartyCompanyCheckEraseMixin, CompanyTestMixin, ModuleTestCase):
    "Test Sale Rental module"
    module = 'sale_rental'
    extras = ['account_asset']


del ModuleTestCase
