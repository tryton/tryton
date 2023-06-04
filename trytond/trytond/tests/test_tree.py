# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest
from collections import defaultdict

from trytond.model import sum_tree
from trytond.model.exceptions import DomainValidationError, RecursionError
from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction


class TreeTestCaseMixin:
    model_name = None

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    def create(self):
        pool = Pool()
        Model = pool.get(self.model_name)

        new_records = [None, None, None]
        for j in range(3):
            parent_records = new_records
            new_records = []
            k = 0
            to_create = []
            for parent_record in parent_records:
                to_create.extend([{
                            'name': 'Test %d %d %d' % (j, k, i),
                            'parent': (parent_record.id
                                if parent_record else None),
                            } for i in range(3)])
                k += 1
            new_records = Model.create(to_create)

    def check_tree(self):
        raise NotImplementedError

    def change_parent(self, parent=None, restore=False):
        pool = Pool()
        Model = pool.get(self.model_name)

        records = Model.search([
                ('parent', '=', parent),
                ])
        if not records:
            return
        for record in records[::2]:
            for record2 in records[1::2]:
                record.parent = record2
                record.save()
                if restore:
                    record.parent = parent
                    record.save()
        for record in records:
            self.change_parent(record, restore=restore)

    @with_transaction()
    def test_create(self):
        "Test create tree"
        self.create()
        self.check_tree()

    @with_transaction()
    def test_reparent(self):
        "Test re-parent"
        self.create()
        self.change_parent(restore=True)
        self.check_tree()

    @with_transaction()
    def test_move(self):
        "Test move"
        self.create()
        self.change_parent()
        self.check_tree()

    @with_transaction()
    def test_active(self):
        "Test active"
        pool = Pool()
        Model = pool.get(self.model_name)

        self.create()

        records = Model.search([])
        for record in records:
            if record.id % 2:
                record.active = False
                record.save()
        self.check_tree()
        self.change_parent()
        self.check_tree()

        records = Model.search([])
        Model.write(records, {
                'active': True,
                })
        Model.write(records[::2], {
                'active': False
                })
        self.check_tree()

        records = Model.search([])
        Model.write(records, {
                'active': True,
                })
        Model.write(records[:len(records) // 2], {
                'active': False
                })
        self.check_tree()

        records = Model.search([])
        Model.write(records, {
                'active': False
                })
        self.change_parent()
        self.check_tree()

    @with_transaction()
    def test_delete(self):
        "Test delete"
        pool = Pool()
        Model = pool.get(self.model_name)

        self.create()

        records = Model.search([])
        for record in records:
            if record.id % 2:
                Model.delete([record])
        self.check_tree()

        records = Model.search([])
        Model.delete(records[:len(records) // 2])
        self.check_tree()

        records = Model.search([])
        Model.delete(records)
        self.check_tree()

    @with_transaction()
    def test_write_multiple_parents(self):
        "Test write multiple parents"
        pool = Pool()
        Model = pool.get(self.model_name)

        record1 = Model(name="Root")
        record1.save()
        record2 = Model(name="Child", parent=record1)
        record2.save()
        record3 = Model(name="Grand Child", parent=record2)
        record3.save()
        self.check_tree()

        Model.write([record2, record3], {'parent': None})
        self.check_tree()

    def rebuild(self):
        raise NotImplementedError

    @with_transaction()
    def test_rebuild(self):
        "Test rebuild"
        self.create()

        self.rebuild()

        self.check_tree()


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

        with self.assertRaises(DomainValidationError):
            record.save()

    @with_transaction()
    def test_name_domain_wildcard(self):
        "Test name domain on tree with wildcard"
        pool = Pool()
        Tree = pool.get('test.tree_wildcard')

        record = Tree(name="test 10%")
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
    def test_on_change_with_rec_name(self):
        "Test on_change_with_rec_name"
        pool = Pool()
        Tree = pool.get('test.tree')

        parent = Tree(name="parent")
        parent.save()
        record = Tree(name="record", parent=parent)
        record.save()

        self.assertEqual(record.rec_name, record.on_change_with_rec_name())

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

        with self.assertRaises(RecursionError):
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

        with self.assertRaises(RecursionError):
            parent1.parents = [child]
            parent1.save()


class TreeTestCase(unittest.TestCase):
    "Test Tree"

    @with_transaction()
    def test_sum_tree(self):
        pool = Pool()
        Model = pool.get('test.tree')
        records = [
            Model(1, parent=None),
            Model(2, parent=1),
            Model(3, parent=1),
            Model(4, parent=2),
            Model(5, parent=2),
            ]
        values = defaultdict(lambda: 1)
        self.assertEqual(
            dict(sum_tree(records, values)), {
                5: 1,
                4: 1,
                3: 1,
                2: 3,
                1: 5,
                })
