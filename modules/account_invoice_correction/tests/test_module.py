# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.tests.test_tryton import ModuleTestCase


class AccountInvoiceCorrectionTestCase(ModuleTestCase):
    'Test Account Invoice Correction module'
    module = 'account_invoice_correction'


del ModuleTestCase
