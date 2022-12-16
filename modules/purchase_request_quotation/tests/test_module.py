# This file is part purchase_request_for_quotation module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.

from trytond.modules.company.tests import CompanyTestMixin
from trytond.tests.test_tryton import ModuleTestCase


class PurchaseRequestForQuotationTestCase(CompanyTestMixin, ModuleTestCase):
    'Test Purchase Request For Quotation module'
    module = 'purchase_request_quotation'


del ModuleTestCase
