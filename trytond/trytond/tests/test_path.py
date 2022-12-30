# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from trytond.pool import Pool
from trytond.transaction import inactive_records

from .test_tree import TreeTestCaseMixin


class PathTestCase(TreeTestCaseMixin, unittest.TestCase):
    "Test Path"
    model_name = 'test.path'

    def check_tree(self, parent_id=None):
        pool = Pool()
        Path = pool.get(self.model_name)

        with inactive_records():
            children = Path.search([
                    ('parent', '=', parent_id),
                    ])
        for child in children:
            if child.parent:
                self.assertEqual(
                    child.path, '%s%s/' % (child.parent.path, child.id))
            else:
                self.assertEqual(child.path, '%s/' % child.id)
            self.check_tree(child.id)

    def rebuild(self):
        pool = Pool()
        Path = pool.get(self.model_name)
        Path._rebuild_path('parent')
