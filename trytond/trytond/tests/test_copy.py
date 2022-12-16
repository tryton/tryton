# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.pool import Pool


class CopyTestCase(unittest.TestCase):
    'Test copy'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_one2many(self):
        'Test copy one2many'
        pool = Pool()
        One2many_ = pool.get('test.copy.one2many')
        One2manyTarget = pool.get('test.copy.one2many.target')
        One2manyReference = pool.get('test.copy.one2many_reference')
        One2manyReferenceTarget = \
            pool.get('test.copy.one2many_reference.target')

        for One2many, Target in (
                (One2many_, One2manyTarget),
                (One2manyReference, One2manyReferenceTarget),
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

    @with_transaction()
    def test_many2many(self):
        'Test copy many2many'
        pool = Pool()
        Many2many_ = pool.get('test.copy.many2many')
        Many2manyTarget = pool.get('test.copy.many2many.target')
        Many2manyReference = pool.get('test.copy.many2many_reference')
        Many2manyReferenceTarget = \
            pool.get('test.copy.many2many_reference.target')

        for Many2many, Target in (
                (Many2many_, Many2manyTarget),
                (Many2manyReference, Many2manyReferenceTarget),
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
