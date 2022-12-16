# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.modules.company.tests import CompanyTestMixin
from trytond.tests.test_tryton import ModuleTestCase


class IncotermTestCase(CompanyTestMixin, ModuleTestCase):
    'Test Incoterm module'
    module = 'incoterm'
    extras = [
        'carrier', 'company', 'purchase', 'purchase_request_quotation',
        'sale', 'sale_shipment_cost', 'sale_opportunity',
        'sale_invoice_grouping', 'stock', 'account_invoice',
        'account_invoice_stock']


del ModuleTestCase
