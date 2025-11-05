# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest

from trytond.modules.stock_package_shipping.stock import lowest_common_root
from trytond.tests.test_tryton import ModuleTestCase


class StockPackageShippingTestCase(ModuleTestCase):
    'Test Stock Package Shipping module'
    module = 'stock_package_shipping'


class testLowestCommonRoot(unittest.TestCase):

    def test_simple_common_root(self):
        "Test simple common root"
        paths = [
            ["Apparel", "Men", "Shirts"],
            ["Apparel", "Men", "Pants"]
            ]
        self.assertEqual(lowest_common_root(paths), "Men")

    def test_root_only_common(self):
        "Test no common"
        paths = [
            ["Root", "Apparel", "Men", "Shirts"],
            ["Root", "Electronics", "Mobile"]
            ]
        self.assertEqual(lowest_common_root(paths), "Root")

    def test_identical_paths(self):
        "Test identical paths"
        paths = [
            ["Apparel", "Men", "Shirts"],
            ["Apparel", "Men", "Shirts"]
            ]
        self.assertEqual(lowest_common_root(paths), "Shirts")

    def test_single_path(self):
        "Test single path"
        paths = [["Apparel", "Men", "Shirts"]]
        self.assertEqual(lowest_common_root(paths), "Shirts")

    def test_empty_paths_list(self):
        "Test empty paths list"
        paths = []
        self.assertIsNone(lowest_common_root(paths))

    def test_no_common_root(self):
        "Test no common root"
        paths = [
            ["Apparel", "Men"],
            ["Electronics", "Mobile"]
            ]
        self.assertIsNone(lowest_common_root(paths))


del ModuleTestCase
