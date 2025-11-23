# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.tests.test_tryton import ModuleTestCase


class SaleRentalProgressInvoiceTestCase(ModuleTestCase):
    "Test Sale Rental Progress Invoice module"
    module = 'sale_rental_progress_invoice'
    extras = ['account_asset']


del ModuleTestCase
