# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, \
        install_module
from trytond.transaction import Transaction


class CopyTestCase(unittest.TestCase):
    'Test copy'

    def setUp(self):
        install_module('tests')
        self.one2many = POOL.get('test.copy.one2many')
        self.one2many_target = POOL.get('test.copy.one2many.target')
        self.one2many_reference = POOL.get('test.copy.one2many_reference')
        self.one2many_reference_target = \
            POOL.get('test.copy.one2many_reference.target')
        self.many2many = POOL.get('test.copy.many2many')
        self.many2many_target = POOL.get('test.copy.many2many.target')
        self.many2many_reference = POOL.get('test.copy.many2many_reference')
        self.many2many_reference_target = \
            POOL.get('test.copy.many2many_reference.target')

    def test0130one2many(self):
        'Test one2many'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT):
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

    def test0140many2many(self):
        'Test many2many'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT):
            for Many2many, Target in (
                    (self.many2many, self.many2many_target),
                    (self.many2many_reference,
                        self.many2many_reference_target),
                    ):
                many2many = Many2many(name='Test')
                many2many.many2many = [
                    Target(name='Target 1'),
                    Target(name='Target 2'),
                    ]
                many2many.save()

                many2many_copy, = Many2many.copy([many2many])

                self.assertNotEqual(many2many, many2many_copy)
                self.assertEqual(len(many2many.many2many),
                    len(many2many_copy.many2many))
                self.assertEqual(many2many.many2many, many2many_copy.many2many)
                self.assertEqual([x.name for x in many2many.many2many],
                    [x.name for x in many2many_copy.many2many])


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(CopyTestCase)
