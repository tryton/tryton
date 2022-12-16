# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import doctest
import glob
import os

from trytond.tests.test_tryton import doctest_checker, doctest_teardown


def load_tests(loader, tests, pattern):
    cwd = os.getcwd()
    try:
        os.chdir(os.path.dirname(__file__))
        for scenario in glob.glob('*.rst'):
            tests.addTests(doctest.DocFileSuite(
                    scenario, tearDown=doctest_teardown, encoding='utf-8',
                    checker=doctest_checker,
                    optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    finally:
        os.chdir(cwd)
    return tests
