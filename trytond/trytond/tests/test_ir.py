# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from .test_tryton import ModuleTestCase


class IrTestCase(ModuleTestCase):
    'Test ir module'
    module = 'ir'


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(IrTestCase)
