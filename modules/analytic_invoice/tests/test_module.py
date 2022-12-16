# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.tests.test_tryton import ModuleTestCase


class AnalyticInvoiceTestCase(ModuleTestCase):
    'Test AnalyticInvoice module'
    module = 'analytic_invoice'
    extras = ['account_asset']


del ModuleTestCase
