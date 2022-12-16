# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest

from trytond.exceptions import UserError
from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.pool import Pool


class TreeMixinTestCase(unittest.TestCase):
    "Test TreeMixin"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_name_domain(self):
        "Test name domain"
        pool = Pool()
        Tree = pool.get('test.tree')

        record = Tree(name="foo / bar")

        with self.assertRaises(UserError):
            record.save()

    @with_transaction()
    def test_rec_name(self):
        "Test rec_name"
        pool = Pool()
        Tree = pool.get('test.tree')

        parent = Tree(name="parent")
        parent.save()
        record = Tree(name="record", parent=parent)
        record.save()

        self.assertEqual(record.rec_name, "parent / record")

    @with_transaction()
    def test_search_rec_name_equals(self):
        "Test search_rec_name equals"
        pool = Pool()
        Tree = pool.get('test.tree')

        parent = Tree(name="parent")
        parent.save()
        record = Tree(name="record", parent=parent)
        record.save()

        records = Tree.search([('rec_name', '=', 'parent / record')])

        self.assertEqual(records, [record])

    @with_transaction()
    def test_search_rec_name_equals_toplevel(self):
        "Test search_rec_name equals top-level"
        pool = Pool()
        Tree = pool.get('test.tree')

        parent = Tree(name="parent")
        parent.save()
        record = Tree(name="record", parent=parent)
        record.save()

        records = Tree.search([('rec_name', '=', 'parent')])

        self.assertEqual(records, [parent])

    @with_transaction()
    def test_search_rec_name_equals_none(self):
        "Test search_rec_name equals"
        pool = Pool()
        Tree = pool.get('test.tree')

        parent = Tree(name="parent")
        parent.save()
        record = Tree(name="record", parent=parent)
        record.save()

        records = Tree.search([('rec_name', '=', None)])

        self.assertEqual(records, [])

    @with_transaction()
    def test_search_rec_name_non_equals(self):
        "Test search_rec_name non equals"
        pool = Pool()
        Tree = pool.get('test.tree')

        parent = Tree(name="parent")
        parent.save()
        record = Tree(name="record", parent=parent)
        record.save()

        records = Tree.search([('rec_name', '!=', 'parent / record')])

        self.assertEqual(records, [parent])

    @with_transaction()
    def test_search_rec_name_non_equals_toplevel(self):
        "Test search_rec_name non equals top-level"
        pool = Pool()
        Tree = pool.get('test.tree')

        parent = Tree(name="parent")
        parent.save()
        record = Tree(name="record", parent=parent)
        record.save()

        records = Tree.search([('rec_name', '!=', 'parent')])

        self.assertEqual(records, [record])

    @with_transaction()
    def test_search_rec_name_non_equals_none(self):
        "Test search_rec_name equals"
        pool = Pool()
        Tree = pool.get('test.tree')

        parent = Tree(name="parent")
        parent.save()
        record = Tree(name="record", parent=parent)
        record.save()

        records = Tree.search([('rec_name', '!=', None)])

        self.assertEqual(records, [parent, record])

    @with_transaction()
    def test_search_rec_name_in(self):
        "Test search_rec_name in"
        pool = Pool()
        Tree = pool.get('test.tree')

        parent = Tree(name="parent")
        parent.save()
        record = Tree(name="record", parent=parent)
        record.save()

        records = Tree.search([('rec_name', 'in', ['parent / record'])])

        self.assertEqual(records, [record])

    @with_transaction()
    def test_search_rec_name_in_toplevel(self):
        "Test search_rec_name in top-level"
        pool = Pool()
        Tree = pool.get('test.tree')

        parent = Tree(name="parent")
        parent.save()
        record = Tree(name="record", parent=parent)
        record.save()

        records = Tree.search([('rec_name', 'in', ['parent'])])

        self.assertEqual(records, [parent])

    @with_transaction()
    def test_search_rec_name_like(self):
        "Test search_rec_name like"
        pool = Pool()
        Tree = pool.get('test.tree')

        parent = Tree(name="parent")
        parent.save()
        record = Tree(name="record", parent=parent)
        record.save()
        child = Tree(name="child", parent=record)
        child.save()

        records = Tree.search([('rec_name', 'like', '%record%')])

        self.assertEqual(records, [record, child])

    @with_transaction()
    def test_search_rec_name_like_toplevel(self):
        "Test search_rec_name like top-level"
        pool = Pool()
        Tree = pool.get('test.tree')

        parent = Tree(name="parent")
        parent.save()
        record = Tree(name="record", parent=parent)
        record.save()
        child = Tree(name="child", parent=record)
        child.save()

        records = Tree.search([('rec_name', 'like', 'parent / record%')])

        self.assertEqual(records, [record, child])

    @with_transaction()
    def test_search_rec_name_like_lowlevel(self):
        "Test search_rec_name like low-level"
        pool = Pool()
        Tree = pool.get('test.tree')

        parent = Tree(name="parent")
        parent.save()
        record = Tree(name="record", parent=parent)
        record.save()
        child = Tree(name="child", parent=record)
        child.save()

        records = Tree.search([('rec_name', 'like', '%record')])

        self.assertEqual(records, [record])

    @with_transaction()
    def test_check_recursion(self):
        "Test check_recursion"
        pool = Pool()
        Tree = pool.get('test.tree')

        parent = Tree(name="parent")
        parent.save()
        record = Tree(name="record", parent=parent)
        record.save()
        child = Tree(name="child", parent=record)
        child.save()

        with self.assertRaises(UserError):
            parent.parent = child
            parent.save()

    @with_transaction()
    def test_check_recursion_polytree(self):
        "Test check_recursion on polytree"
        pool = Pool()
        Polytree = pool.get('test.polytree')

        parent1 = Polytree(name="parent1")
        parent1.save()
        parent2 = Polytree(name="parent2")
        parent2.save()
        record = Polytree(name="record", parents=[parent1, parent2])
        record.save()
        child = Polytree(name="child", parents=[record])
        child.save()

        with self.assertRaises(UserError):
            parent1.parents = [child]
            parent1.save()


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(TreeMixinTestCase)
