#!/usr/bin/env python
# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import unittest
from trytond.tests.test_tryton import POOL, DB, USER, CONTEXT, install_module


class MPTTTestCase(unittest.TestCase):
    '''
    Test Modified Preorder Tree Traversal.
    '''

    def setUp(self):
        install_module('test')
        self.mptt = POOL.get('test.mptt')

    def CheckTree(self, cursor, parent_id=False, left=0, right=0):
        child_ids = self.mptt.search(cursor, USER, [
            ('parent', '=', parent_id),
            ], 0, None, None, CONTEXT)
        childs = self.mptt.read(cursor, USER, child_ids, ['left', 'right'],
                CONTEXT)
        childs.sort(lambda x, y: cmp(child_ids.index(x['id']),
            child_ids.index(y['id'])))
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
            self.CheckTree(cursor, child['id'], left=child['left'],
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


    def ReParent(self, cursor, parent_id=False):
        record_ids = self.mptt.search(cursor, USER, [
            ('parent', '=', parent_id),
            ], 0, None, None, CONTEXT)
        if not record_ids:
            return
        for record_id in record_ids:
            for record2_id in record_ids:
                if record_id != record2_id:
                    self.mptt.write(cursor, USER, record_id, {
                        'parent': record2_id,
                        }, CONTEXT)
                    self.mptt.write(cursor, USER, record_id, {
                        'parent': parent_id,
                        }, CONTEXT)
        for record_id in record_ids:
            self.ReParent(cursor, record_id)

    def ReOrder(self, cursor, parent_id=False):
        record_ids = self.mptt.search(cursor, USER, [
            ('parent', '=', parent_id),
            ], 0, None, None, CONTEXT)
        if not record_ids:
            return
        i = len(record_ids)
        for record_id in record_ids:
            self.mptt.write(cursor, USER, record_id, {
                'sequence': i,
                }, CONTEXT)
            i -= 1
        i = 0
        for record_id in record_ids:
            self.mptt.write(cursor, USER, record_id, {
                'sequence': i,
                }, CONTEXT)
            i += 1
        for record_id in record_ids:
            self.ReOrder(cursor, record_id)

        record_ids = self.mptt.search(cursor, USER, [], 0, None, None, CONTEXT)
        self.mptt.write(cursor, USER, record_ids, {
            'sequence': 0,
            }, CONTEXT)

    def test0010create(self):
        '''
        Create tree.
        '''
        cursor = DB.cursor()

        new_records = [False]
        for j in range(3):
            parent_records = new_records
            new_records = []
            k = 0
            for parent_record in parent_records:
                for i in range(3):
                    record_id = self.mptt.create(cursor, USER, {
                        'name': 'Test %d %d %d' % (j, k, i),
                        'parent': parent_record,
                        }, CONTEXT)
                    new_records.append(record_id)
                k += 1
        self.CheckTree(cursor)

        cursor.commit()
        cursor.close()

    def test0020reorder(self):
        '''
        Re-order.
        '''
        cursor = DB.cursor()

        self.ReOrder(cursor)

        cursor.rollback()
        cursor.close()

    def test0030reparent(self):
        '''
        Re-parent.
        '''
        cursor = DB.cursor()

        self.ReParent(cursor)

        cursor.rollback()
        cursor.close()

    def test0040active(self):
        cursor = DB.cursor()

        record_ids = self.mptt.search(cursor, USER, [], 0, None, None, CONTEXT)
        for record_id in record_ids:
            if record_id % 2:
                self.mptt.write(cursor, USER, record_id, {
                        'active': False
                        }, CONTEXT)
        self.CheckTree(cursor)
        self.ReParent(cursor)
        self.CheckTree(cursor)
        self.ReOrder(cursor)
        self.CheckTree(cursor)

        cursor.rollback()
        cursor.close()
        cursor = DB.cursor()

        record_ids = self.mptt.search(cursor, USER, [], 0, None, None, CONTEXT)
        self.mptt.write(cursor, USER, record_ids[:len(record_ids)/2], {
                'active': False
                }, CONTEXT)
        self.CheckTree(cursor)

        cursor.rollback()
        cursor.close()
        cursor = DB.cursor()

        record_ids = self.mptt.search(cursor, USER, [], 0, None, None, CONTEXT)
        self.mptt.write(cursor, USER, record_ids, {
                'active': False
                }, CONTEXT)
        self.ReParent(cursor)
        self.CheckTree(cursor)
        self.ReOrder(cursor)
        self.CheckTree(cursor)

        cursor.rollback()
        cursor.close()

    def test0050delete(self):
        '''
        Delete.
        '''
        cursor = DB.cursor()

        record_ids = self.mptt.search(cursor, USER, [], 0, None, None, CONTEXT)
        for record_id in record_ids:
            if record_id % 2:
                self.mptt.delete(cursor, USER, record_id, CONTEXT)
        self.CheckTree(cursor)

        cursor.rollback()
        cursor.close()
        cursor = DB.cursor()

        record_ids = self.mptt.search(cursor, USER, [], 0, None, None, CONTEXT)
        self.mptt.delete(cursor, USER, record_ids[:len(record_ids)/2], CONTEXT)
        self.CheckTree(cursor)

        cursor.rollback()
        cursor.close()
        cursor = DB.cursor()

        record_ids = self.mptt.search(cursor, USER, [], 0, None, None, CONTEXT)
        self.mptt.delete(cursor, USER, record_ids, CONTEXT)
        self.CheckTree(cursor)

        cursor.rollback()
        cursor.close()

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(MPTTTestCase)

if __name__ == '__main__':
    suite = suite()
    unittest.TextTestRunner(verbosity=2).run(suite)
