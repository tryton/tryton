# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase


class ProductClassificationTaxonomicTestCase(ModuleTestCase):
    'Test Product Classification module'
    module = 'product_classification_taxonomic'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ProductClassificationTaxonomicTestCase))
    return suite
