# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import doctest

from trytond.model import descriptors


def load_tests(loader, tests, pattern):
    tests.addTest(doctest.DocTestSuite(descriptors))
    return tests
