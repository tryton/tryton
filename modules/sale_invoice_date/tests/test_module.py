# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.tests.test_tryton import ModuleTestCase


class SaleInvoiceDateTestCase(ModuleTestCase):
    'Test Sale Invoice Date module'
    module = 'sale_invoice_date'


del ModuleTestCase
