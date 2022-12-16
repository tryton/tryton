# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.


import doctest
import unittest

from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import suite as test_suite
from trytond.tests.test_tryton import doctest_teardown
from trytond.tests.test_tryton import doctest_checker


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


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            AccountRuleTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_account_rule.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
