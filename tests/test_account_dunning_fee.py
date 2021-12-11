# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import doctest
import unittest

from trytond.tests.test_tryton import (
    ModuleTestCase, doctest_checker, doctest_teardown)
from trytond.tests.test_tryton import suite as test_suite


class AccountDunningFeeTestCase(ModuleTestCase):
    'Test Account Dunning Fee module'
    module = 'account_dunning_fee'
    extras = ['account_dunning_letter']


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            AccountDunningFeeTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_account_dunning_fee.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
