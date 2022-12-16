# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.tests.test_tryton import ModuleTestCase


class PurchaseSecondaryUnitTestCase(ModuleTestCase):
    'Test Purchase Secondary Unit module'
    module = 'purchase_secondary_unit'
    extras = ['account_invoice_secondary_unit', 'stock_secondary_unit']


del ModuleTestCase
