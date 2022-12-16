#!/usr/bin/env python
# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import unittest
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, \
        install_module
from trytond.transaction import Transaction


class ModelInheritsTestCase(unittest.TestCase):
    '''
    Test ModelInheritSearch
    '''

    def setUp(self):
        install_module('test')
        self.parent = POOL.get('test.model_inherits')
        self.sub = POOL.get('test.submodel')
        self.subsub = POOL.get('test.subsubmodel')
        self.subsubsub = POOL.get('test.subsubsubmodel')
        self.overridden = POOL.get('test.overriddeninheritedfieldmodel')

    def create_data(self):
        parent_id = self.parent.create({'name': 'parent'})
        sub_id = self.sub.create({
                'name': 'sub',
                'subfield': 'level1',
            })
        subsub_id = self.subsub.create({
                'name': 'subsub',
                'subfield': 'level2',
                'subsubfield': 'ssfcontent',
            })
        subsubsub_id = self.subsubsub.create({
                'name': 'subsubsub',
                'subfield': 'level3',
                'subsubfield': 'ssfcontent2',
                'subsubsubfield': 'sssfcontent',
            })
        overridden_id = self.overridden.create({
                'name': 'overridden',
                'subfield': 3,
            })
        return (parent_id, sub_id, subsub_id, subsubsub_id, overridden_id)

    def test0010selfsearch(self):
        '''
        Test searching on own field
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:

            (_parent_id, _sub_id, _subsub_id, subsubsub_id, overridden_id) = \
                self.create_data()

            ids = self.subsubsub.search([
                    ('subsubsubfield', '=', 'sssfcontent'),
                    ])
            self.assertEqual(ids, [subsubsub_id])

            transaction.cursor.rollback()

    def test0020parentsearch(self):
        '''
        Test searching on parent field
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:

            (_parent_id, _sub_id, _subsub_id, subsubsub_id, overridden_id) = \
                self.create_data()

            ids = self.subsubsub.search([('subsubfield', '=', 'ssfcontent2')])
            self.assertEqual(ids, [subsubsub_id])

            ids = self.subsubsub.search([('subsubfield', '=', 'ssfcontent')])
            self.assertEqual(ids, [])

            transaction.cursor.rollback()

    def test0030granparentsearch(self):
        '''
        Test searching on granparent field
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:

            (_parent_id, _sub_id, _subsub_id, subsubsub_id, overridden_id) = \
                self.create_data()

            ids = self.subsubsub.search([('subfield', '=', 'level3')])
            self.assertEqual(ids, [subsubsub_id])

            ids = self.subsubsub.search([('subfield', '=', 'level1')])
            self.assertEqual(ids, [])

            transaction.cursor.rollback()

    def test0040greatgranparentsearch(self):
        '''
        Test searching on greatgranparent field
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:

            (_parent_id, _sub_id, _subsub_id, subsubsub_id, overridden_id) = \
                self.create_data()

            ids = self.subsubsub.search([('name', '=', 'subsubsub')])
            self.assertEqual(ids, [subsubsub_id])

            ids = self.subsubsub.search([('name', '=', 'parent')])
            self.assertEqual(ids, [])

            transaction.cursor.rollback()

    def test0050overriddenfieldsearch(self):
        '''
        Test searching on greatgranparent field
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:

            (_parent_id, _sub_id, _subsub_id, subsubsub_id, overridden_id) = \
                self.create_data()

            ids = self.overridden.search([('subfield', '=', 3)])
            self.assertEqual(ids, [overridden_id])

            transaction.cursor.rollback()


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ModelInheritsTestCase)

if __name__ == '__main__':
    suite = suite()
    unittest.TextTestRunner(verbosity=2).run(suite)
