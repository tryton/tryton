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
        child_ids = self.mptt.search([
            ('parent', '=', parent_id),
            ])
        childs = self.mptt.read(child_ids, ['left', 'right'])
        childs.sort(key=lambda x: child_ids.index(x['id']))
        for child in childs:
            assert child['left'] > left, \
                    'Record (%d): left %d <= parent left %d' % \
                    (child['id'], child['left'], left)
            assert child['left'] < child['right'], \
                    'Record (%d): left %d >= right %d' % \
                    (child['id'], child['left'], child['right'])
            assert right == 0 or child['right'] < right, \
                    'Record (%d): right %d >= parent right %d' % \
                    (child['id'], child['right'], right)
            self.CheckTree(child['id'], left=child['left'],
                    right=child['right'])
        next_left = 0
        for child in childs:
            assert child['left'] > next_left, \
                    'Record (%d): left %d <= next left %d' % \
                    (child['id'], child['left'], next_left)
            next_left = child['right']
        childs.reverse()
        previous_right = 0
        for child in childs:
            assert previous_right == 0 or child['right'] < previous_right, \
                    'Record (%d): right %d >= previous right %d' % \
                    (child['id'] , child['right'], previous_right)
            previous_right = child['left']


    def ReParent(self, parent_id=False):
        record_ids = self.mptt.search([
            ('parent', '=', parent_id),
            ])
        if not record_ids:
            return
        for record_id in record_ids:
            for record2_id in record_ids:
                if record_id != record2_id:
                    self.mptt.write(record_id, {
                        'parent': record2_id,
                        })
                    self.mptt.write(record_id, {
                        'parent': parent_id,
                        })
        for record_id in record_ids:
            self.ReParent(record_id)

    def ReOrder(self, parent_id=False):
        record_ids = self.mptt.search([
            ('parent', '=', parent_id),
            ])
        if not record_ids:
            return
        i = len(record_ids)
        for record_id in record_ids:
            self.mptt.write(record_id, {
                'sequence': i,
                })
            i -= 1
        i = 0
        for record_id in record_ids:
            self.mptt.write(record_id, {
                'sequence': i,
                })
            i += 1
        for record_id in record_ids:
            self.ReOrder(record_id)

        record_ids = self.mptt.search([])
        self.mptt.write(record_ids, {
            'sequence': 0,
            })

    def test0010create(self):
        '''
        Create tree.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            new_records = [False]
            for j in range(3):
                parent_records = new_records
                new_records = []
                k = 0
                for parent_record in parent_records:
                    for i in range(3):
                        record_id = self.mptt.create({
                            'name': 'Test %d %d %d' % (j, k, i),
                            'parent': parent_record,
                            })
                        new_records.append(record_id)
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
            record_ids = self.mptt.search([])
            for record_id in record_ids:
                if record_id % 2:
                    self.mptt.write(record_id, {
                            'active': False
                            })
            self.CheckTree()
            self.ReParent()
            self.CheckTree()
            self.ReOrder()
            self.CheckTree()

            transaction.cursor.rollback()

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            record_ids = self.mptt.search([])
            self.mptt.write(record_ids[:len(record_ids) // 2], {
                    'active': False
                    })
            self.CheckTree()

            transaction.cursor.rollback()

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            record_ids = self.mptt.search([])
            self.mptt.write(record_ids, {
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
            record_ids = self.mptt.search([])
            for record_id in record_ids:
                if record_id % 2:
                    self.mptt.delete(record_id)
            self.CheckTree()

            transaction.cursor.rollback()

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            record_ids = self.mptt.search([])
            self.mptt.delete(record_ids[:len(record_ids) // 2])
            self.CheckTree()

            transaction.cursor.rollback()

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            record_ids = self.mptt.search([])
            self.mptt.delete(record_ids)
            self.CheckTree()

            transaction.cursor.rollback()

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(MPTTTestCase)

if __name__ == '__main__':
    suite = suite()
    unittest.TextTestRunner(verbosity=2).run(suite)
