# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest

from trytond.model import descriptors


def suite():
    suite = unittest.TestSuite()
    suite.addTest(doctest.DocTestSuite(descriptors))
    return suite
