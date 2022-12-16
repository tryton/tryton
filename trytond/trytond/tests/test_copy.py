#!/usr/bin/env python
# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import unittest
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, \
        install_module
from trytond.transaction import Transaction


class CopyTestCase(unittest.TestCase):
    '''
    Test copy.
    '''

    def setUp(self):
        install_module('test')
        self.one2many = POOL.get('test.copy.one2many')
        self.one2many_target = POOL.get('test.copy.one2many.target')
        self.one2many_reference = POOL.get('test.copy.one2many_reference')
        self.one2many_reference_target = \
            POOL.get('test.copy.one2many_reference.target')

    def test0130one2many(self):
        '''
        Test one2many.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            for One2many, Target in (
                    (self.one2many, self.one2many_target),
                    (self.one2many_reference, self.one2many_reference_target),
                    ):
                one2many = One2many(name='Test')
                one2many.one2many = [
                    Target(name='Target 1'),
                    Target(name='Target 2'),
                    ]
                one2many.save()

                one2many_copy, = One2many.copy([one2many])

                self.assertNotEqual(one2many, one2many_copy)
                self.assertEqual(len(one2many.one2many),
                    len(one2many_copy.one2many))
                self.assertNotEqual(one2many.one2many, one2many_copy.one2many)
                self.assertEqual([x.name for x in one2many.one2many],
                    [x.name for x in one2many_copy.one2many])

            transaction.cursor.rollback()


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(CopyTestCase)

if __name__ == '__main__':
    suite = suite()
    unittest.TextTestRunner(verbosity=2).run(suite)
