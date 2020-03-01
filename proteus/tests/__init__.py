# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import sys
import unittest
import doctest

import proteus
import proteus.config

os.environ.setdefault('TRYTOND_DATABASE_URI', 'sqlite:///:memory:')
os.environ.setdefault('DB_NAME', ':memory:')
from trytond.tests.test_tryton import (
    doctest_setup, doctest_teardown)  # noqa: E402

here = os.path.dirname(__file__)
readme = os.path.normpath(os.path.join(here, '..', '..', 'README'))


def test_suite():
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for filename in os.listdir(os.path.dirname(__file__)):
        if filename.startswith("test") and filename.endswith(".py"):
            modname = "proteus.tests." + filename[:-3]
            __import__(modname)
            module = sys.modules[modname]
            suite.addTests(loader.loadTestsFromModule(module))
    suite.addTests(additional_tests())
    return suite


def additional_tests():
    suite = unittest.TestSuite()
    for mod in (proteus, proteus.config):
        suite.addTest(doctest.DocTestSuite(mod))
    if os.path.isfile(readme):
        suite.addTest(doctest.DocFileSuite(readme, module_relative=False,
                setUp=doctest_setup, tearDown=doctest_teardown,
                encoding='utf-8',
                optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite


def main():
    suite = test_suite()
    runner = unittest.TextTestRunner()
    return runner.run(suite)


if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))
    sys.exit(not main().wasSuccessful())
