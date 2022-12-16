#!/usr/bin/env python
# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import unittest
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, \
        install_module
from trytond.transaction import Transaction


class MPTTTestCase(unittest.TestCase):
    '''
    Test Modified Preorder Tree Traversal.
    '''

    def setUp(self):
        install_module('test')
        self.mptt = POOL.get('test.mptt')

    def CheckTree(self, parent_id=False, left=0, right=0):
        childs = self.mptt.search([
                ('parent', '=', parent_id),
                ])
        child_index = dict((x.id, i) for i, x in enumerate(childs))
        childs.sort(key=lambda x: child_index[x.id])
        for child in childs:
            assert child.left > left, \
                '%s: left %d <= parent left %d' % \
                (child, child.left, left)
            assert child.left < child.right, \
                '%s: left %d >= right %d' % \
                (child, child.left, child.right)
            assert right == 0 or child.right < right, \
                '%s: right %d >= parent right %d' % \
                (child, child.right, right)
            self.CheckTree(child.id, left=child.left,
                right=child.right)
        next_left = 0
        for child in childs:
            assert child.left > next_left, \
                '%s: left %d <= next left %d' % \
                (child, child.left, next_left)
            next_left = child.right
        childs.reverse()
        previous_right = 0
        for child in childs:
            assert previous_right == 0 or child.right < previous_right, \
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

    def ReOrder(self, parent=None):
        records = self.mptt.search([
                ('parent', '=', parent),
                ])
        if not records:
            return
        i = len(records)
        for record in records:
            record.sequence = i
            record.save()
            i -= 1
        i = 0
        for record in records:
            record.sequence = i
            record.save()
            i += 1
        for record in records:
            self.ReOrder(record)

        records = self.mptt.search([])
        self.mptt.write(records, {
                'sequence': 0,
                })

    def test0010create(self):
        '''
        Create tree.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            new_records = [None]
            for j in range(3):
                parent_records = new_records
                new_records = []
                k = 0
                for parent_record in parent_records:
                    for i in range(3):
                        new_records += self.mptt.create([{
                                    'name': 'Test %d %d %d' % (j, k, i),
                                    'parent': (parent_record.id
                                            if parent_record else None),
                                    }])
                    k += 1
            self.CheckTree()

            transaction.cursor.commit()

    def test0020reorder(self):
        '''
        Re-order.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            self.ReOrder()
            transaction.cursor.rollback()

    def test0030reparent(self):
        '''
        Re-parent.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            self.ReParent()
            transaction.cursor.rollback()

    def test0040active(self):
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
            self.ReOrder()
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
            self.ReOrder()
            self.CheckTree()

            transaction.cursor.rollback()

    def test0050delete(self):
        '''
        Delete.
        '''
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


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(MPTTTestCase)

if __name__ == '__main__':
    suite = suite()
    unittest.TextTestRunner(verbosity=2).run(suite)
