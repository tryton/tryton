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
    def test_copy(self):
        "Test copy"
        pool = Pool()
        Copy = pool.get('test.copy')
        record = Copy(name="Name")
        record.save()

        record_copy, = Copy.copy([record])

        self.assertNotEqual(record_copy.id, record.id)
        self.assertEqual(record_copy.name, record.name)

    @with_transaction()
    def test_copy_default(self):
        "Test copy with default value"
        pool = Pool()
        Copy = pool.get('test.copy')
        record = Copy(name="Name")
        record.save()

        record_copy, = Copy.copy([record], default={'name': "New name"})

        self.assertNotEqual(record_copy.id, record.id)
        self.assertEqual(record_copy.name, "New name")

    @with_transaction()
    def test_copy_default_callable(self):
        "Test copy with default callable"
        pool = Pool()
        Copy = pool.get('test.copy')
        record = Copy(name="Name")
        record.save()

        def default_name(data):
            assert data['id'] == record.id
            return data['name'] + " bis"

        record_copy, = Copy.copy([record], default={'name': default_name})

        self.assertNotEqual(record_copy.id, record.id)
        self.assertEqual(record_copy.name, "Name bis")

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
    def test_one2many_default(self):
        "Test copy one2many with default"
        pool = Pool()
        One2many = pool.get('test.copy.one2many')
        Target = pool.get('test.copy.one2many.target')

        record = One2many(name="Test")
        record.save()
        target = Target(name="Target")
        target.save()

        record_copy, = One2many.copy(
            [record], default={'one2many': [target.id]})

        self.assertListEqual(
            [x.name for x in record_copy.one2many], [target.name])

    @with_transaction()
    def test_one2many_default_nested(self):
        "Test copy one2many with default nested"
        pool = Pool()
        One2many = pool.get('test.copy.one2many')
        Target = pool.get('test.copy.one2many.target')

        record = One2many(name="Test")
        record.one2many = [Target(name="Target")]
        record.save()

        record_copy, = One2many.copy(
            [record], default={'one2many.name': "New Target"})

        self.assertListEqual(
            [x.name for x in record_copy.one2many], ["New Target"])

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

    @with_transaction()
    def test_many2many_default(self):
        "Test copy many2many with default"
        pool = Pool()
        Many2many = pool.get('test.copy.many2many')
        Target = pool.get('test.copy.many2many.target')

        record = Many2many(name="Test")
        record.save()
        target = Target(name="Target")
        target.save()

        record_copy, = Many2many.copy(
            [record], default={'many2many': [target.id]})

        self.assertSequenceEqual(record_copy.many2many, [target])


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(CopyTestCase)
