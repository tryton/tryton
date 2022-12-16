# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import sys
import unittest
from unittest.mock import patch

from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.transaction import Transaction
from trytond.pool import Pool


class MPTTTestCase(unittest.TestCase):
    'Test Modified Preorder Tree Traversal'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    def check_tree(self, parent_id=None, left=-1, right=sys.maxsize):
        pool = Pool()
        Mptt = pool.get('test.mptt')

        with Transaction().set_context(active_test=False):
            childs = Mptt.search([
                    ('parent', '=', parent_id),
                    ], order=[('left', 'ASC')])
        for child in childs:
            assert child.left > left, \
                '%s: left %d <= parent left %d' % \
                (child, child.left, left)
            assert child.left < child.right, \
                '%s: left %d >= right %d' % \
                (child, child.left, child.right)
            assert child.right < right, \
                '%s: right %d >= parent right %d' % \
                (child, child.right, right)
            self.check_tree(child.id, left=child.left,
                right=child.right)
        next_left = -1
        for child in childs:
            assert child.left > next_left, \
                '%s: left %d <= next left %d' % \
                (child, child.left, next_left)
            next_left = child.right
        childs.reverse()
        previous_right = sys.maxsize
        for child in childs:
            assert child.right < previous_right, \
                '%s: right %d >= previous right %d' \
                % (child, child.right, previous_right)
            previous_right = child.left

    def reparent(self, parent=None):
        pool = Pool()
        Mptt = pool.get('test.mptt')

        records = Mptt.search([
                ('parent', '=', parent),
                ])
        if not records:
            return
        for record in records:
            for record2 in records:
                if record != record2:
                    record.parent = record2
                    record.save()
                    record.parent = parent
                    record.save()
        for record in records:
            self.reparent(record)

    def create(self):
        pool = Pool()
        Mptt = pool.get('test.mptt')

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
            new_records = Mptt.create(to_create)

    @with_transaction()
    def test_create(self):
        'Test create tree'
        self.create()
        self.check_tree()

    @with_transaction()
    def test_reparent(self):
        'Test re-parent'
        self.create()
        self.reparent()

    @with_transaction()
    def test_active(self):
        'Test active'
        pool = Pool()
        Mptt = pool.get('test.mptt')

        self.create()

        records = Mptt.search([])
        for record in records:
            if record.id % 2:
                record.active = False
                record.save()
        self.check_tree()
        self.reparent()
        self.check_tree()

        records = Mptt.search([])
        Mptt.write(records, {
                'active': True,
                })
        Mptt.write(records[::2], {
                'active': False
                })
        self.check_tree()

        records = Mptt.search([])
        Mptt.write(records, {
                'active': True,
                })
        Mptt.write(records[:len(records) // 2], {
                'active': False
                })
        self.check_tree()

        records = Mptt.search([])
        Mptt.write(records, {
                'active': False
                })
        self.reparent()
        self.check_tree()

    @with_transaction()
    def test_delete(self):
        'Test delete'
        pool = Pool()
        Mptt = pool.get('test.mptt')

        self.create()

        records = Mptt.search([])
        for record in records:
            if record.id % 2:
                Mptt.delete([record])
        self.check_tree()

        records = Mptt.search([])
        Mptt.delete(records[:len(records) // 2])
        self.check_tree()

        records = Mptt.search([])
        Mptt.delete(records)
        self.check_tree()

    @with_transaction()
    def test_update_only_if_parent_is_modified(self):
        'The left and right fields must only be updated if parent is modified'
        pool = Pool()
        Mptt = pool.get('test.mptt')

        self.create()

        records = Mptt.search([
                ('parent', '=', None),
                ])
        with patch.object(Mptt, '_update_tree') as update, \
                patch.object(Mptt, '_rebuild_tree') as rebuild:
            Mptt.write(records, {'name': 'Parent Records'})
            self.assertFalse(update.called)
            self.assertFalse(rebuild.called)

            first_parent, second_parent = records[:2]
            Mptt.write(list(first_parent.childs), {
                    'parent': second_parent.id,
                    })

            self.assertTrue(update.called or rebuild.called)

    @with_transaction()
    def test_nested_create(self):
        pool = Pool()
        Mptt = pool.get('test.mptt')

        record, = Mptt.create([{
                    'name': 'Test nested create 1',
                    'childs': [('create', [{
                                    'name': 'Test nested create 1 1',
                                    }])],
                    }])
        self.check_tree()


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(MPTTTestCase)
