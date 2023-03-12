# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.tests.test_tryton import ModuleTestCase


class QualityTestCase(ModuleTestCase):
    "Test Quality module"
    module = 'quality'
    extras = ['stock', 'production']


del ModuleTestCase
