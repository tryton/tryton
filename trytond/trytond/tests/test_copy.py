# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from unittest.mock import patch

from trytond.model import fields
from trytond.model.exceptions import AccessError
from trytond.pool import Pool
from trytond.tests.test_tryton import (
    TestCase, activate_module, with_transaction)
from trytond.transaction import Transaction

from .test_modelsql import TranslationTestCase


class CopyTestCase(TestCase):
    'Test copy'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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
            self.assertEqual(data['id'], record.id)
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
    def test_one2many_readonly(self):
        "Test copy one2many readonly"
        pool = Pool()
        Model = pool.get('test.copy.one2many')
        Target = pool.get('test.copy.one2many.target')

        record = Model(name="Test")
        record.one2many = [Target(name="Target")]
        record.save()

        with patch.object(Model.one2many, 'readonly', True):
            copy, = Model.copy([record])

            self.assertEqual(copy.one2many, ())

    @with_transaction()
    def test_one2many_filter(self):
        "Test not copy one2many with filter"
        pool = Pool()
        Model = pool.get('test.copy.one2many')
        Target = pool.get('test.copy.one2many.target')

        record = Model(name="Test")
        record.one2many = [Target(name="Target")]
        record.save()

        try:
            Model.one2many.filter = [('name', '=', "Target")]
            copy, = Model.copy([record])

            self.assertEqual(copy.one2many, ())
        finally:
            Model.one2many.filter = None

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
    def test_many2many_readonly(self):
        "test copy many2many readonly"
        pool = Pool()
        Model = pool.get('test.copy.many2many')
        Target = pool.get('test.copy.many2many.target')

        record = Model(name="Test")
        record.many2many = [Target(name="Target")]
        record.save()

        with patch.object(Model.many2many, 'readonly', True):
            copy, = Model.copy([record])

            self.assertEqual(copy.many2many, ())

    @with_transaction()
    def test_many2many_filter(self):
        "Test not copy many2many with filter"
        pool = Pool()
        Model = pool.get('test.copy.many2many')
        Target = pool.get('test.copy.many2many.target')

        record = Model(name="Test")
        record.many2many = [Target(name="Target")]
        record.save()

        try:
            Model.many2many.filter = [('name', '=', "Target")]
            copy, = Model.copy([record])

            self.assertEqual(copy.many2many, ())
        finally:
            Model.many2many.filter = None

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

    @with_transaction()
    def test_binary(self):
        "Test copy binary"
        pool = Pool()
        Binary = pool.get('test.copy.binary')
        record = Binary(binary=fields.Binary.cast(b'data'))
        record.save()

        record_copy, = Binary.copy([record])

        self.assertEqual(record_copy.binary, record.binary)

    @with_transaction()
    def test_binary_file_id(self):
        "Test copy binary with file_id"
        pool = Pool()
        Binary = pool.get('test.copy.binary')
        record = Binary(binary_id=fields.Binary.cast(b'data'))
        record.save()

        record_copy, = Binary.copy([record])

        self.assertEqual(record_copy.file_id, record.file_id)
        self.assertEqual(record_copy.binary_id, record.binary_id)

    @with_transaction(context={'_check_access': True})
    def test_no_acccess_copy_with_custom_value(self):
        "Test copying field with no access and custom value"
        pool = Pool()
        FieldAccess = pool.get('ir.model.field.access')
        TestAccess = pool.get('test.copy.access')

        record, = TestAccess.create([{'name': 'foo'}])

        FieldAccess.create([{
                    'model': 'test.copy.access',
                    'field': 'name',
                    'group': None,
                    'perm_read': True,
                    'perm_write': False,
                    }])

        with self.assertRaises(AccessError):
            new_record, = TestAccess.copy([record])

    @with_transaction(context={'_check_access': True})
    def test_no_acccess_copy_with_default(self):
        "Test copying field with no access but default value"
        pool = Pool()
        FieldAccess = pool.get('ir.model.field.access')
        TestAccess = pool.get('test.copy.access')

        FieldAccess.create([{
                    'model': 'test.copy.access',
                    'field': 'name',
                    'group': None,
                    'perm_read': True,
                    'perm_write': False,
                    }])

        record, = TestAccess.create([{}])
        self.assertEqual(record.name, "Default")
        new_record, = TestAccess.copy([record])
        self.assertEqual(new_record.name, "Default")

    @with_transaction(context={'_check_access': True})
    def test_no_acccess_copy_with_defaults(self):
        "Test copying field with no access and defaults"
        pool = Pool()
        FieldAccess = pool.get('ir.model.field.access')
        TestAccess = pool.get('test.copy.access')

        record, = TestAccess.create([{}])

        FieldAccess.create([{
                    'model': 'test.copy.access',
                    'field': 'name',
                    'group': None,
                    'perm_read': True,
                    'perm_write': False,
                    }])

        with self.assertRaises(AccessError):
            new_record, = TestAccess.copy(
                [record], default={'name': 'nondefault'})

    @with_transaction(context={'_check_access': True})
    def test_copy_with_no_read_access(self):
        "Test copying field with no read access"
        pool = Pool()
        FieldAccess = pool.get('ir.model.field.access')
        TestAccess = pool.get('test.copy.access')

        record, = TestAccess.create([{}])

        FieldAccess.create([{
                    'model': 'test.copy.access',
                    'field': 'name',
                    'group': None,
                    'perm_read': False,
                    'perm_write': False,
                    }])

        new_record, = TestAccess.copy([record])
        self.assertNotEqual(new_record.id, record.id)

    @with_transaction()
    def test_copy_empty(self):
        "Test copy without records"
        pool = Pool()
        Copy = pool.get('test.copy')

        self.assertEqual(Copy.copy([]), [])


class CopyTranslationTestCase(TranslationTestCase):
    "Test copy translation"

    @with_transaction()
    def test_copy(self):
        "Test copy"
        pool = Pool()
        Translate = pool.get('test.copy.translate')

        with Transaction().set_context(language=self.default_language):
            record, = Translate.create([{'name': "Foo"}])
        with Transaction().set_context(language=self.other_language):
            Translate.write([record], {'name': "Bar"})

        record_copy, = Translate.copy([record])

        with Transaction().set_context(language=self.default_language):
            record_copy = Translate(record_copy.id)
            self.assertEqual(record_copy.name, "Foo")
        with Transaction().set_context(language=self.other_language):
            record_copy = Translate(record_copy.id)
            self.assertEqual(record_copy.name, "Bar")

    @with_transaction()
    def test_copy_multiple(self):
        "Test copy multiple"
        pool = Pool()
        Translate = pool.get('test.copy.translate')

        with Transaction().set_context(language=self.default_language):
            record, = Translate.create([{'name': "Foo"}])
        with Transaction().set_context(language=self.other_language):
            Translate.write([record], {'name': "Bar"})

        record_copies = Translate.copy([record, record])

        with Transaction().set_context(language=self.default_language):
            record_copies = Translate.browse(record_copies)
            self.assertEqual({r.name for r in record_copies}, {"Foo"})
        with Transaction().set_context(language=self.other_language):
            record_copies = Translate.browse(record_copies)
            self.assertEqual({r.name for r in record_copies}, {"Bar"})

    @with_transaction()
    def test_copy_empty(self):
        "Test copy without records"
        pool = Pool()
        Copy = pool.get('test.copy.translate')

        self.assertEqual(Copy.copy([]), [])
