# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.tests.test_tryton import ModuleTestCase


class AccountRuleTestCase(ModuleTestCase):
    'Test Account Rule module'
    module = 'account_rule'
    extras = [
        'account_invoice',
        'account_invoice_stock',
        'account_stock_continental',
        'account_stock_anglo_saxon',
        'product',
        'purchase',
        'purchase_shipment_cost',
        'sale',
        'sale_gift_card',
        'stock',
        'stock_consignment',
        ]


del ModuleTestCase
