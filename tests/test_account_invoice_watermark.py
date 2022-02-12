# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import doctest
import shutil
import unittest

from trytond.tests.test_tryton import (
    ModuleTestCase, doctest_checker, doctest_teardown)
from trytond.tests.test_tryton import suite as test_suite


class AccountInvoiceWatermarkTestCase(ModuleTestCase):
    'Test Account Invoice Watermark module'
    module = 'account_invoice_watermark'


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            AccountInvoiceWatermarkTestCase))
    if shutil.which('soffice') and shutil.which('mutool'):
        suite.addTests(doctest.DocFileSuite(
                'scenario_account_invoice_watermark.rst',
                tearDown=doctest_teardown, encoding='utf-8',
                checker=doctest_checker,
                optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
