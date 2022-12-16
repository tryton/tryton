# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import sys
import unittest


def test_suite():
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for filename in os.listdir(os.path.dirname(__file__)):
        if filename.startswith("test") and filename.endswith(".py"):
            modname = "tryton.tests." + filename[:-3]
            __import__(modname)
            module = sys.modules[modname]
            suite.addTests(loader.loadTestsFromModule(module))
    return suite


def main():
    suite = test_suite()
    runner = unittest.TextTestRunner()
    return runner.run(suite)


if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))
    sys.exit(not main().wasSuccessful())
