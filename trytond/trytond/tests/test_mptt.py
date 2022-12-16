# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import sys
import unittest
from mock import patch
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, \
        install_module
from trytond.transaction import Transaction


class MPTTTestCase(unittest.TestCase):
    'Test Modified Preorder Tree Traversal'

    def setUp(self):
        install_module('tests')
        self.mptt = POOL.get('test.mptt')

    def CheckTree(self, parent_id=None, left=-1, right=sys.maxint):
        with Transaction().set_context(active_test=False):
            childs = self.mptt.search([
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
            self.CheckTree(child.id, left=child.left,
                right=child.right)
        next_left = -1
        for child in childs:
            assert child.left > next_left, \
                '%s: left %d <= next left %d' % \
                (child, child.left, next_left)
            next_left = child.right
        childs.reverse()
        previous_right = sys.maxint
        for child in childs:
            assert child.right < previous_right, \
                '%s: right %d >= previous right %d' \
                % (child, child.right, previous_right)
            previous_right = child.left

    def ReParent(self, parent=None):
        records = self.mptt.search([
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
            self.ReParent(record)

    def test0010create(self):
        'Test create tree'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            new_records = [None, None, None]
            for j in range(3):
                parent_records = new_records
                new_records = []
                k = 0
                for parent_record in parent_records:
                    new_records += self.mptt.create([{
                                'name': 'Test %d %d %d' % (j, k, i),
                                'parent': (parent_record.id
                                    if parent_record else None),
                                } for i in range(3)])
                    k += 1
            self.CheckTree()

            transaction.cursor.commit()

    def test0030reparent(self):
        'Test re-parent'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            self.ReParent()
            transaction.cursor.rollback()

    def test0040active(self):
        'Test active'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            records = self.mptt.search([])
            for record in records:
                if record.id % 2:
                    record.active = False
                    record.save()
            self.CheckTree()
            self.ReParent()
            self.CheckTree()

            transaction.cursor.rollback()

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            records = self.mptt.search([])
            self.mptt.write(records[::2], {
                    'active': False
                    })
            self.CheckTree()

            transaction.cursor.rollback()

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            records = self.mptt.search([])
            self.mptt.write(records[:len(records) // 2], {
                    'active': False
                    })
            self.CheckTree()

            transaction.cursor.rollback()

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            records = self.mptt.search([])
            self.mptt.write(records, {
                    'active': False
                    })
            self.ReParent()
            self.CheckTree()

            transaction.cursor.rollback()

    def test0050delete(self):
        'Test delete'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            records = self.mptt.search([])
            for record in records:
                if record.id % 2:
                    self.mptt.delete([record])
            self.CheckTree()

            transaction.cursor.rollback()

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            records = self.mptt.search([])
            self.mptt.delete(records[:len(records) // 2])
            self.CheckTree()

            transaction.cursor.rollback()

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            records = self.mptt.search([])
            self.mptt.delete(records)
            self.CheckTree()

            transaction.cursor.rollback()

    def test0060_update_only_if_parent_is_modified(self):
        'The left and right fields must only be updated if parent is modified'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            records = self.mptt.search([
                    ('parent', '=', None),
                    ])
            with patch.object(self.mptt, '_update_tree') as mock:
                self.mptt.write(records, {'name': 'Parent Records'})
                self.assertFalse(mock.called)

                first_parent, second_parent = records[:2]
                self.mptt.write(list(first_parent.childs), {
                        'parent': second_parent.id,
                        })

                self.assertTrue(mock.called)


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(MPTTTestCase)
