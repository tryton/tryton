# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest

import doctest

from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import suite as test_suite
from trytond.tests.test_tryton import doctest_teardown
from trytond.tests.test_tryton import doctest_checker

from trytond.modules.company.tests import CompanyTestMixin


class IncotermTestCase(CompanyTestMixin, ModuleTestCase):
    'Test Incoterm module'
    module = 'incoterm'
    extras = [
        'carrier', 'company', 'purchase', 'purchase_request_quotation',
        'sale', 'sale_shipment_cost', 'sale_opportunity',
        'sale_invoice_grouping', 'stock', 'account_invoice',
        'account_invoice_stock']


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            IncotermTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_incoterm.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
