# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import doctest
import os

import proteus
import proteus.config
from trytond.tests.test_tryton import doctest_setup, doctest_teardown

here = os.path.dirname(__file__)
readme = os.path.normpath(os.path.join(here, '..', '..', 'README.rst'))


def load_tests(loader, tests, pattern):
    for mod in (proteus, proteus.config):
        tests.addTest(doctest.DocTestSuite(mod))
    if os.path.isfile(readme):
        tests.addTest(doctest.DocFileSuite(
                readme, module_relative=False,
                setUp=doctest_setup, tearDown=doctest_teardown,
                encoding='utf-8',
                optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
