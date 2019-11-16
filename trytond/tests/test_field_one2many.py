# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from trytond.model.exceptions import (
    RequiredValidationError, SizeValidationError)
from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction


class CommonTestCaseMixin:

    @with_transaction()
    def test_set_reverse_field_instance(self):
        "Test reverse field is set on instance"
        One2Many = self.One2Many()
        Target = self.One2ManyTarget()

        record = One2Many()
        target = Target()
        record.targets = [target]

        self.assertEqual(target.origin, record)

    @with_transaction()
    def test_save_reverse_field(self):
        "Test save with reverse field set"
        One2Many = self.One2Many()
        Target = self.One2ManyTarget()

        record = One2Many()
        target = Target()
        record.targets = [target]

        record.save()

    @with_transaction()
    def test_save_reverse_field_saved(self):
        "Test save with reverse field set on saved"
        One2Many = self.One2Many()
        Target = self.One2ManyTarget()

        record = One2Many()
        target = Target()
        target.save()
        record.targets = [target]

        record.save()

    @with_transaction()
    def test_set_reverse_field_dict(self):
        "Test reverse field is set on dict"
        One2Many = self.One2Many()

        record = One2Many()
        record.targets = [{}]
        target, = record.targets

        self.assertEqual(target.origin, record)

    @with_transaction()
    def test_set_reverse_field_id(self):
        "Test reverse field is set on id"
        One2Many = self.One2Many()
        Target = self.One2ManyTarget()

        record = One2Many()
        target = Target()
        target.save()
        record.targets = [target.id]
        target, = record.targets

        self.assertEqual(target.origin, record)

    @with_transaction()
    def test_create(self):
        "Test create one2many"
        One2Many = self.One2Many()

        one2many, = One2Many.create([{
                    'targets': [
                        ('create', [{
                                    'name': "Target",
                                    }]),
                        ],
                    }])

        self.assertEqual(len(one2many.targets), 1)

    @with_transaction()
    def test_search_equals(self):
        "Test search one2many equals"
        One2Many = self.One2Many()
        one2many, = One2Many.create([{
                    'targets': [('create', [{'name': "Target"}])],
                    }])

        one2manys = One2Many.search([
                ('targets', '=', "Target"),
                ])

        self.assertListEqual(one2manys, [one2many])

    @with_transaction()
    def test_search_non_equals(self):
        "Test search one2many non equals"
        One2Many = self.One2Many()
        one2many, = One2Many.create([{
                    'targets': [('create', [{'name': "Target"}])],
                    }])

        one2manys = One2Many.search([
                ('targets', '!=', "Target"),
                ])

        self.assertListEqual(one2manys, [])

    @with_transaction()
    def test_search_equals_none(self):
        "Test search one2many equals None"
        One2Many = self.One2Many()
        one2many1, one2many2 = One2Many.create([{
                    'targets': [('create', [{'name': "Target"}])],
                    }, {
                    'targets': None,
                    }])

        one2manys = One2Many.search([
                ('targets', '=', None),
                ])

        self.assertListEqual(one2manys, [one2many2])

    @with_transaction()
    def test_search_non_equals_none(self):
        "Test search one2many non equals None"
        One2Many = self.One2Many()
        one2many1, one2many2 = One2Many.create([{
                    'targets': [('create', [{'name': "Target"}])],
                    }, {
                    'targets': None,
                    }])

        one2manys = One2Many.search([
                ('targets', '!=', None),
                ])

        self.assertListEqual(one2manys, [one2many1])

    @with_transaction()
    def test_search_in(self):
        "Test search one2many in"
        One2Many = self.One2Many()
        one2many, = One2Many.create([{
                    'targets': [('create', [{'name': "Target"}])],
                    }])
        target, = one2many.targets

        one2manys = One2Many.search([
                ('targets', 'in', [target.id]),
                ])

        self.assertListEqual(one2manys, [one2many])

    @with_transaction()
    def test_search_in_0(self):
        "Test search one2many in [0]"
        One2Many = self.One2Many()
        one2many, = One2Many.create([{
                    'targets': [('create', [{'name': "Target"}])],
                    }])

        one2manys = One2Many.search([
                ('targets', 'in', [0]),
                ])

        self.assertListEqual(one2manys, [])

    @with_transaction()
    def test_search_in_empty(self):
        "Test search one2many in []"
        One2Many = self.One2Many()
        one2many, = One2Many.create([{
                    'targets': [('create', [{'name': "Target"}])],
                    }])

        one2manys = One2Many.search([
                ('targets', 'in', []),
                ])

        self.assertListEqual(one2manys, [])

    @with_transaction()
    def test_search_not_in(self):
        "Test search one2many not in"
        One2Many = self.One2Many()
        one2many, = One2Many.create([{
                    'targets': [('create', [{'name': "Target"}])],
                    }])
        target, = one2many.targets

        one2manys = One2Many.search([
                ('targets', 'not in', [target.id]),
                ])

        self.assertListEqual(one2manys, [])

    @with_transaction()
    def test_search_not_in_0(self):
        "Test search one2many not in [0]"
        One2Many = self.One2Many()
        one2many, = One2Many.create([{
                    'targets': [('create', [{'name': "Target"}])],
                    }])

        one2manys = One2Many.search([
                ('targets', 'not in', [0]),
                ])

        self.assertListEqual(one2manys, [one2many])

    @with_transaction()
    def test_search_not_in_empty(self):
        "Test search one2many not in []"
        One2Many = self.One2Many()
        one2many, = One2Many.create([{
                    'targets': [('create', [{'name': "Target"}])],
                    }])

        one2manys = One2Many.search([
                ('targets', 'not in', []),
                ])

        self.assertListEqual(one2manys, [one2many])

    @with_transaction()
    def test_search_join(self):
        "Test search one2many equals"
        One2Many = self.One2Many()
        one2many, = One2Many.create([{
                    'targets': [('create', [{'name': "Target"}])],
                    }])

        one2manys = One2Many.search([
                ('targets.name', '=', "Target"),
                ])

        self.assertListEqual(one2manys, [one2many])

    @with_transaction()
    def test_search_where(self):
        "Test search one2many where"
        One2Many = self.One2Many()
        one2many, = One2Many.create([{
                    'targets': [('create', [{'name': "Target"}])],
                    }])

        one2manys = One2Many.search([
                ('targets', 'where', [('name', '=', "Target")]),
                ])

        self.assertListEqual(one2manys, [one2many])

    @with_transaction()
    def test_search_not_where(self):
        "Test search one2many not where"
        One2Many = self.One2Many()
        one2many, = One2Many.create([{
                    'targets': [('create', [{'name': "Target"}])],
                    }])

        one2manys = One2Many.search([
                ('targets', 'not where', [('name', '=', "Target")]),
                ])

        self.assertListEqual(one2manys, [])

    @with_transaction()
    def test_write_write(self):
        "Test write one2many write"
        One2Many = self.One2Many()
        one2many, = One2Many.create([{
                    'targets': [('create', [{'name': "Foo"}])],
                    }])
        target, = one2many.targets

        One2Many.write([one2many], {
                'targets': [
                    ('write', [target.id], {
                            'name': "Bar",
                            }),
                    ],
                })

        self.assertEqual(target.name, "Bar")

    @with_transaction()
    def test_write_add(self):
        "Test write one2many add"
        One2Many = self.One2Many()
        Target = self.One2ManyTarget()
        one2many, = One2Many.create([{}])
        target, = Target.create([{}])

        One2Many.write([one2many], {
                'targets': [
                    ('add', [target.id]),
                    ],
                })

        self.assertTupleEqual(one2many.targets, (target,))

    @with_transaction()
    def test_write_remove(self):
        "Test write one2many remove"
        One2Many = self.One2Many()
        Target = self.One2ManyTarget()
        one2many, = One2Many.create([{
                    'targets': [('create', [{'name': "Foo"}])],
                    }])
        target, = one2many.targets

        One2Many.write([one2many], {
                'targets': [
                    ('remove', [target.id]),
                    ],
                })
        targets = Target.search([('id', '=', target.id)])

        self.assertTupleEqual(one2many.targets, ())
        self.assertListEqual(targets, [target])

    @with_transaction()
    def test_write_copy(self):
        "Test write one2many copy"
        One2Many = self.One2Many()
        Target = self.One2ManyTarget()
        one2many, = One2Many.create([{
                    'targets': [('create', [{'name': "Foo"}])],
                    }])
        target1, = one2many.targets

        One2Many.write([one2many], {
                'targets': [
                    ('copy', [target1.id], {'name': "Bar"}),
                    ],
                })
        target2, = Target.search([('id', '!=', target1.id)])

        self.assertTupleEqual(one2many.targets, (target1, target2))

    @with_transaction()
    def test_write_delete(self):
        "Test write one2many delete"
        One2Many = self.One2Many()
        Target = self.One2ManyTarget()
        one2many, = One2Many.create([{
                    'targets': [(
                            'create', [{'name': "Foo"}, {'name': "Bar"}])],
                    }])
        target1, target2 = one2many.targets

        One2Many.write([one2many], {
                'targets': [
                    ('delete', [target1.id]),
                    ],
                })
        targets = Target.search([])

        self.assertTupleEqual(one2many.targets, (target2,))
        self.assertListEqual(targets, [target2])


class FieldOne2ManyTestCase(unittest.TestCase, CommonTestCaseMixin):
    "Test Field One2Many"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    def One2Many(self):
        return Pool().get('test.one2many')

    def One2ManyTarget(self):
        return Pool().get('test.one2many.target')

    @with_transaction()
    def test_create_required_with_value(self):
        "Test create one2many required with value"
        One2Many = Pool().get('test.one2many_required')

        one2many, = One2Many.create([{
                    'targets': [
                        ('create', [{
                                    'name': "Target",
                                    }]),
                        ],
                    }])

        self.assertEqual(len(one2many.targets), 1)

    @with_transaction()
    def test_create_required_without_value(self):
        "Test create one2many required without value"
        One2Many = Pool().get('test.one2many_required')

        with self.assertRaises(RequiredValidationError):
            One2Many.create([{}])

    @with_transaction()
    def test_create_size_valid(self):
        "Test create one2many size valid"
        One2Many = Pool().get('test.one2many_size')

        one2many, = One2Many.create([{
                    'targets': [
                        ('create', [{}] * 3),
                        ],
                    }])

        self.assertEqual(len(one2many.targets), 3)

    @with_transaction()
    def test_create_size_invalid(self):
        "Test create one2many size invalid"
        One2Many = Pool().get('test.one2many_size')

        with self.assertRaises(SizeValidationError):
            One2Many.create([{
                        'targets': [
                            ('create', [{}] * 4),
                            ],
                        }])

    @with_transaction()
    def test_create_size_pyson_valid(self):
        "Test create one2many size pyson valid"
        One2Many = Pool().get('test.one2many_size_pyson')

        one2many, = One2Many.create([{
                    'limit': 4,
                    'targets': [
                        ('create', [{}] * 4),
                        ],
                    }])

        self.assertEqual(len(one2many.targets), 4)

    @with_transaction()
    def test_create_size_pyson_invalid(self):
        "Test create one2many size pyson invalid"
        One2Many = Pool().get('test.one2many_size_pyson')

        with self.assertRaises(SizeValidationError):
            One2Many.create([{
                        'limit': 3,
                        'targets': [
                            ('create', [{}] * 4),
                            ],
                        }])

    @with_transaction()
    def test_create_filter(self):
        "Test create one2many with filter"
        One2Many = Pool().get('test.one2many_filter')

        filtered, = One2Many.create([{
                    'targets': [
                        ('create', [{'value': x} for x in range(4)])],
                    }])
        filtered_target, = filtered.filtered_targets

        self.assertEqual(len(filtered.targets), 4)
        self.assertEqual(filtered_target.value, 3)

    @with_transaction()
    def test_create_filter_domain(self):
        "Test create one2many with filter and domain"
        One2Many = Pool().get('test.one2many_filter_domain')

        filtered, = One2Many.create([{
                    'targets': [
                        ('create', [{'value': x} for x in range(4)])],
                    }])
        filtered_target, = filtered.filtered_targets

        self.assertEqual(len(filtered.targets), 4)
        self.assertEqual(filtered_target.value, 3)

    @with_transaction()
    def test_search_non_equals_filter(self):
        "Test search one2many non equals with filter"
        One2Many = Pool().get('test.one2many_filter')
        one2many, = One2Many.create([{
                    'targets': [('create', [{'value': -1}])],
                    }])

        one2manys = One2Many.search([('targets', '!=', None)])
        one2manys_filtered = One2Many.search(
            [('filtered_targets', '!=', None)])

        self.assertListEqual(one2manys, [one2many])
        self.assertListEqual(one2manys_filtered, [])

    @with_transaction()
    def test_search_join_filter(self):
        "Test search one2many join with filter"
        One2Many = Pool().get('test.one2many_filter')
        one2many, = One2Many.create([{
                    'targets': [('create', [{'value': -1}])],
                    }])

        one2manys = One2Many.search([('targets.value', '=', -1)])
        one2manys_filtered = One2Many.search(
            [('filtered_targets.value', '=', -1)])

        self.assertListEqual(one2manys, [one2many])
        self.assertListEqual(one2manys_filtered, [])

    @with_transaction()
    def test_context_attribute(self):
        "Test context on one2many attribute"
        pool = Pool()
        Many2One = pool.get('test.one2many_context')

        record, = Many2One.create([{
                    'targets': [('create', [{}])],
                    }])

        self.assertEqual(record.targets[0].context, record.id)

    @with_transaction()
    def test_context_read(self):
        "Test context on one2many read"
        pool = Pool()
        Many2One = pool.get('test.one2many_context')

        record, = Many2One.create([{
                    'targets': [('create', [{}])],
                    }])
        data, = Many2One.read([record.id], ['targets.context'])

        self.assertEqual(data['targets.'][0]['context'], record.id)

    @with_transaction()
    def test_context_read_multi(self):
        "Test context on one2many read multiple records"
        pool = Pool()
        Many2One = pool.get('test.one2many_context')

        records = Many2One.create([{
                    'targets': [('create', [{}])],
                    }, {
                    'targets': [('create', [{}])],
                    }])
        data = Many2One.read([r.id for r in records], ['targets.context'])

        self.assertEqual(data[0]['targets.'][0]['context'], records[0].id)
        self.assertEqual(data[1]['targets.'][0]['context'], records[1].id)

    @with_transaction()
    def test_context_set(self):
        "Test context on one2many set"
        pool = Pool()
        Many2One = pool.get('test.one2many_context')
        Target = pool.get('test.one2many_context.target')

        target, = Target.create([{}])
        record = Many2One(targets=[target.id])

        self.assertEqual(record.targets[0].context, record.id)


class FieldOne2ManyReferenceTestCase(unittest.TestCase, CommonTestCaseMixin):
    "Test Field One2Many Reference"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    def One2Many(self):
        return Pool().get('test.one2many_reference')

    def One2ManyTarget(self):
        return Pool().get('test.one2many_reference.target')


def suite():
    suite_ = unittest.TestSuite()
    loader = unittest.TestLoader()
    suite_.addTests(loader.loadTestsFromTestCase(FieldOne2ManyTestCase))
    suite_.addTests(
        loader.loadTestsFromTestCase(FieldOne2ManyReferenceTestCase))
    return suite_
