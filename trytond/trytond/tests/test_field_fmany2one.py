# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from trytond.tests.test_tryton import (
    TestCase, activate_module, with_transaction)


class FieldFMany2OneTestCase(TestCase):
    "Test Field fmany2one"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        activate_module('tests')

    @with_transaction()
    def test_create(self):
        "Test create fmany2one"
        pool = Pool()
        Target = pool.get('test.fmany2one_target')
        FMany2One = pool.get('test.fmany2one')
        target, = Target.create([{'name': "Foo"}])

        fmany2one, = FMany2One.create([{
                    'target': target.id,
                    }])

        self.assertEqual(fmany2one.target, target)
        self.assertEqual(fmany2one.target_name, "Foo")

    @with_transaction()
    def test_create_composed_key(self):
        "Test create fmany2one with composed key"
        pool = Pool()
        Target = pool.get('test.fmany2one_target')
        TargetChild = pool.get('test.fmany2one_target.child')
        FMany2One = pool.get('test.fmany2one')
        target, = Target.create([{'name': "Foo"}])
        target_child, = TargetChild.create(
            [{'name': "Bar", 'parent': target.id}])

        fmany2one, = FMany2One.create([{
                    'target': target.id,
                    'child': target_child.id,
                    }])

        self.assertEqual(fmany2one.target, target)
        self.assertEqual(fmany2one.target_name, "Foo")
        self.assertEqual(fmany2one.child, target_child)
        self.assertEqual(fmany2one.child_name, "Bar")

    @with_transaction()
    def test_create_required(self):
        "Test create fmany2one required"
        pool = Pool()
        Target = pool.get('test.fmany2one_target')
        FMany2One = pool.get('test.fmany2one_required')
        target, = Target.create([{'name': "Foo"}])

        fmany2one, = FMany2One.create([{
                    'target': target.id,
                    }])

        self.assertEqual(fmany2one.target, target)
        self.assertEqual(fmany2one.target_name, "Foo")

    @with_transaction()
    def test_write(self):
        "Test write fmany2one"
        pool = Pool()
        Target = pool.get('test.fmany2one_target')
        FMany2One = pool.get('test.fmany2one')
        target, = Target.create([{'name': "Foo"}])

        fmany2one, = FMany2One.create([{}])
        FMany2One.write([fmany2one], {
                'target': target.id,
                })

        self.assertEqual(fmany2one.target, target)
        self.assertEqual(fmany2one.target_name, "Foo")

    @with_transaction()
    def test_write_composed_key(self):
        "Test create fmany2one with composed key"
        pool = Pool()
        Target = pool.get('test.fmany2one_target')
        TargetChild = pool.get('test.fmany2one_target.child')
        FMany2One = pool.get('test.fmany2one')
        target, _ = Target.create([{'name': "Foo"}, {'name': "Baz"}])
        target_child, = TargetChild.create(
            [{'name': "Bar", 'parent': target.id}])

        fmany2one, = FMany2One.create([{'target_name': "Baz"}])
        FMany2One.write([fmany2one], {
                'child': target_child.id,
                'target': target.id,
                })

        self.assertEqual(fmany2one.target, target)
        self.assertEqual(fmany2one.target_name, "Foo")
        self.assertEqual(fmany2one.child, target_child)
        self.assertEqual(fmany2one.child_name, "Bar")

    @with_transaction()
    def test_search_id(self):
        "Test search on fmany2one with id"
        pool = Pool()
        Target = pool.get('test.fmany2one_target')
        FMany2One = pool.get('test.fmany2one')
        target, = Target.create([{'name': "Foo"}])
        fmany2one, = FMany2One.create([{
                    'target': target.id,
                    }])

        result = FMany2One.search([('target', '=', target.id)])

        self.assertEqual(result, [fmany2one])

    @with_transaction()
    def test_search_string(self):
        "Test search on fmany2one with string"
        pool = Pool()
        Target = pool.get('test.fmany2one_target')
        FMany2One = pool.get('test.fmany2one')
        target, = Target.create([{'name': "Foo"}])
        fmany2one, = FMany2One.create([{
                    'target': target.id,
                    }])

        result = FMany2One.search([('target', '=', "Foo")])

        self.assertEqual(result, [fmany2one])

    @with_transaction()
    def test_search_nested(self):
        "Test search on fmany2one with nested clause"
        pool = Pool()
        Target = pool.get('test.fmany2one_target')
        FMany2One = pool.get('test.fmany2one')
        target, = Target.create([{'name': "Foo"}])
        fmany2one, = FMany2One.create([{
                    'target': target.id,
                    }])

        result = FMany2One.search([('target.name', '=', "Foo")])

        self.assertEqual(result, [fmany2one])

    @with_transaction()
    def test_search_composed_key(self):
        "Test search on fmany2one with composed key"
        pool = Pool()
        Target = pool.get('test.fmany2one_target')
        TargetChild = pool.get('test.fmany2one_target.child')
        FMany2One = pool.get('test.fmany2one')
        target, = Target.create([{'name': "Foo"}])
        target_child, = TargetChild.create(
            [{'name': "Bar", 'parent': target.id}])
        fmany2one, = FMany2One.create([{
                    'target': target.id,
                    'child': target_child.id,
                    }])

        result = FMany2One.search([
                ('child', '=', target_child.id),
                ])

        self.assertEqual(result, [fmany2one])
