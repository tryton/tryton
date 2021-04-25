# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from trytond.model.exceptions import (
    RequiredValidationError, SizeValidationError)
from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction


class CommonTestCaseMixin:

    @with_transaction()
    def test_create(self):
        "Test create many2many"
        Many2Many = self.Many2Many()

        many2many, = Many2Many.create([{
                    'targets': [
                        ('create', [{
                                    'name': "Target",
                                    }]),
                        ],
                    }])

        self.assertEqual(len(many2many.targets), 1)

    @with_transaction()
    def test_search_equals(self):
        "Test search many2many equals"
        Many2Many = self.Many2Many()
        many2many, = Many2Many.create([{
                    'targets': [('create', [{'name': "Target"}])],
                    }])

        many2manys = Many2Many.search([
                ('targets', '=', "Target"),
                ])

        self.assertListEqual(many2manys, [many2many])

    @with_transaction()
    def test_search_equals_no_link(self):
        "Test search many2many equals without link"
        Many2Many = self.Many2Many()
        many2many, no_link = Many2Many.create([{
                    'targets': [('create', [{'name': "Target"}])],
                    }, {
                    }])

        many2manys = Many2Many.search([
                ('targets', '=', "Target"),
                ])

        self.assertListEqual(many2manys, [many2many])

    @with_transaction()
    def test_search_non_equals(self):
        "Test search many2many non equals"
        Many2Many = self.Many2Many()
        many2many, = Many2Many.create([{
                    'targets': [('create', [{'name': "Target"}])],
                    }])

        many2manys = Many2Many.search([
                ('targets', '!=', "Target"),
                ])

        self.assertListEqual(many2manys, [])

    @with_transaction()
    def test_search_equals_none(self):
        "Test search many2many equals None"
        Many2Many = self.Many2Many()
        many2many1, many2many2 = Many2Many.create([{
                    'targets': [('create', [{'name': "Target"}])],
                    }, {
                    'targets': None,
                    }])

        many2manys = Many2Many.search([
                ('targets', '=', None),
                ])

        self.assertListEqual(many2manys, [many2many2])

    @with_transaction()
    def test_search_non_equals_none(self):
        "Test search many2many non equals None"
        Many2Many = self.Many2Many()
        many2many1, many2many2 = Many2Many.create([{
                    'targets': [('create', [{'name': "Target"}])],
                    }, {
                    'targets': None,
                    }])

        many2manys = Many2Many.search([
                ('targets', '!=', None),
                ])

        self.assertListEqual(many2manys, [many2many1])

    @with_transaction()
    def test_search_non_equals_no_link(self):
        "Test search many2many non equals without link"
        Many2Many = self.Many2Many()
        many2many, no_link = Many2Many.create([{
                    'targets': [('create', [{'name': "Target"}])],
                    }, {
                    }])

        many2manys = Many2Many.search([
                ('targets', '!=', "Target"),
                ])

        self.assertListEqual(many2manys, [no_link])

    @with_transaction()
    def test_search_in(self):
        "Test search many2many in"
        Many2Many = self.Many2Many()
        many2many, = Many2Many.create([{
                    'targets': [('create', [{'name': "Target"}])],
                    }])
        target, = many2many.targets

        many2manys = Many2Many.search([
                ('targets', 'in', [target.id]),
                ])

        self.assertListEqual(many2manys, [many2many])

    @with_transaction()
    def test_search_in_0(self):
        "Test search many2many in [0]"
        Many2Many = self.Many2Many()
        many2many, = Many2Many.create([{
                    'targets': [('create', [{'name': "Target"}])],
                    }])

        many2manys = Many2Many.search([
                ('targets', 'in', [0]),
                ])

        self.assertListEqual(many2manys, [])

    @with_transaction()
    def test_search_in_empty(self):
        "Test search many2many in []"
        Many2Many = self.Many2Many()
        many2many, = Many2Many.create([{
                    'targets': [('create', [{'name': "Target"}])],
                    }])

        many2manys = Many2Many.search([
                ('targets', 'in', []),
                ])

        self.assertListEqual(many2manys, [])

    @with_transaction()
    def test_search_not_in(self):
        "Test search many2many not in"
        Many2Many = self.Many2Many()
        many2many, = Many2Many.create([{
                    'targets': [('create', [{'name': "Target"}])],
                    }])
        target, = many2many.targets

        many2manys = Many2Many.search([
                ('targets', 'not in', [target.id]),
                ])

        self.assertListEqual(many2manys, [])

    @with_transaction()
    def test_search_not_in_0(self):
        "Test search many2many not in [0]"
        Many2Many = self.Many2Many()
        many2many, = Many2Many.create([{
                    'targets': [('create', [{'name': "Target"}])],
                    }])

        many2manys = Many2Many.search([
                ('targets', 'not in', [0]),
                ])

        self.assertListEqual(many2manys, [many2many])

    @with_transaction()
    def test_search_not_in_empty(self):
        "Test search many2many not in []"
        Many2Many = self.Many2Many()
        many2many, = Many2Many.create([{
                    'targets': [('create', [{'name': "Target"}])],
                    }])

        many2manys = Many2Many.search([
                ('targets', 'not in', []),
                ])

        self.assertListEqual(many2manys, [many2many])

    @with_transaction()
    def test_search_join(self):
        "Test search many2many equals"
        Many2Many = self.Many2Many()
        many2many, = Many2Many.create([{
                    'targets': [('create', [{'name': "Target"}])],
                    }])

        many2manys = Many2Many.search([
                ('targets.name', '=', "Target"),
                ])

        self.assertListEqual(many2manys, [many2many])

    @with_transaction()
    def test_search_where(self):
        "Test search many2many where"
        Many2Many = self.Many2Many()
        many2many, = Many2Many.create([{
                    'targets': [('create', [{'name': "Target"}])],
                    }])

        many2manys = Many2Many.search([
                ('targets', 'where', [('name', '=', "Target")]),
                ])

        self.assertListEqual(many2manys, [many2many])

    @with_transaction()
    def test_search_not_where(self):
        "Test search many2many not where"
        Many2Many = self.Many2Many()
        many2many, = Many2Many.create([{
                    'targets': [('create', [{'name': "Target"}])],
                    }])

        many2manys = Many2Many.search([
                ('targets', 'not where', [('name', '=', "Target")]),
                ])

        self.assertListEqual(many2manys, [])

    @with_transaction()
    def test_write_write(self):
        "Test write many2many write"
        Many2Many = self.Many2Many()
        many2many, = Many2Many.create([{
                    'targets': [('create', [{'name': "Foo"}])],
                    }])
        target, = many2many.targets

        Many2Many.write([many2many], {
                'targets': [
                    ('write', [target.id], {
                            'name': "Bar",
                            }),
                    ],
                })

        self.assertEqual(target.name, "Bar")

    @with_transaction()
    def test_write_add(self):
        "Test write many2many add"
        Many2Many = self.Many2Many()
        Target = self.Many2ManyTarget()
        many2many, = Many2Many.create([{}])
        target, = Target.create([{}])

        Many2Many.write([many2many], {
                'targets': [
                    ('add', [target.id]),
                    ],
                })

        self.assertTupleEqual(many2many.targets, (target,))

    @with_transaction()
    def test_write_remove(self):
        "Test write many2many remove"
        Many2Many = self.Many2Many()
        Target = self.Many2ManyTarget()
        many2many, = Many2Many.create([{
                    'targets': [('create', [{'name': "Foo"}])],
                    }])
        target, = many2many.targets

        Many2Many.write([many2many], {
                'targets': [
                    ('remove', [target.id]),
                    ],
                })
        targets = Target.search([('id', '=', target.id)])

        self.assertTupleEqual(many2many.targets, ())
        self.assertListEqual(targets, [target])

    @with_transaction()
    def test_write_copy(self):
        "Test write many2many copy"
        Many2Many = self.Many2Many()
        Target = self.Many2ManyTarget()
        many2many, = Many2Many.create([{
                    'targets': [('create', [{'name': "Foo"}])],
                    }])
        target1, = many2many.targets

        Many2Many.write([many2many], {
                'targets': [
                    ('copy', [target1.id], {'name': "Bar"}),
                    ],
                })
        target2, = Target.search([('id', '!=', target1.id)])

        self.assertListEqual(
            sorted(many2many.targets), sorted((target1, target2)))

    @with_transaction()
    def test_write_delete(self):
        "Test write many2many delete"
        Many2Many = self.Many2Many()
        Target = self.Many2ManyTarget()
        many2many, = Many2Many.create([{
                    'targets': [(
                            'create', [{'name': "Foo"}, {'name': "Bar"}])],
                    }])
        target1, target2 = many2many.targets

        Many2Many.write([many2many], {
                'targets': [
                    ('delete', [target1.id]),
                    ],
                })
        targets = Target.search([])

        self.assertTupleEqual(many2many.targets, (target2,))
        self.assertListEqual(targets, [target2])

    @with_transaction()
    def test_write_not_readd(self):
        "Test write many2many do not re-add existing"
        pool = Pool()
        Many2Many = self.Many2Many()
        Relation = pool.get(Many2Many.targets.relation_name)
        many2many, = Many2Many.create([{
                    'targets': [('create', [{}])],
                    }])

        target, = many2many.targets

        Many2Many.write([many2many], {
                    'targets': [('add', {target.id})],
                    })

        relation, = Relation.search([])
        self.assertIsNone(relation.write_date)


class FieldMany2ManyTestCase(unittest.TestCase, CommonTestCaseMixin):
    "Test Field Many2Many"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    def Many2Many(self):
        return Pool().get('test.many2many')

    def Many2ManyTarget(self):
        return Pool().get('test.many2many.target')

    @with_transaction()
    def test_create_required_with_value(self):
        "Test create many2many required with value"
        Many2Many = Pool().get('test.many2many_required')

        many2many, = Many2Many.create([{
                    'targets': [
                        ('create', [{
                                    'name': "Target",
                                    }]),
                        ],
                    }])

        self.assertEqual(len(many2many.targets), 1)

    @with_transaction()
    def test_create_required_without_value(self):
        "Test create many2many required without value"
        Many2Many = Pool().get('test.many2many_required')

        with self.assertRaises(RequiredValidationError):
            Many2Many.create([{}])

    @with_transaction()
    def test_create_size_valid(self):
        "Test create many2many size valid"
        Many2Many = Pool().get('test.many2many_size')

        many2many, = Many2Many.create([{
                    'targets': [
                        ('create', [{}] * 3),
                        ],
                    }])

        self.assertEqual(len(many2many.targets), 3)

    @with_transaction()
    def test_create_size_invalid(self):
        "Test create many2many size invalid"
        Many2Many = Pool().get('test.many2many_size')

        with self.assertRaises(SizeValidationError):
            Many2Many.create([{
                        'targets': [
                            ('create', [{}] * 4),
                            ],
                        }])

    @with_transaction()
    def test_create_filter(self):
        "Test create many2many with filter"
        Many2Many = Pool().get('test.many2many_filter')

        filtered, = Many2Many.create([{
                    'targets': [
                        ('create', [{'value': x} for x in range(4)])],
                    }])
        filtered_target, = filtered.filtered_targets

        self.assertEqual(len(filtered.targets), 4)
        self.assertEqual(filtered_target.value, 3)

    @with_transaction()
    def test_create_filter_domain(self):
        "Test create many2many with filter and domain"
        Many2Many = Pool().get('test.many2many_filter_domain')

        filtered, = Many2Many.create([{
                    'targets': [
                        ('create', [{'value': x} for x in range(4)])],
                    }])
        filtered_target, = filtered.filtered_targets

        self.assertEqual(len(filtered.targets), 4)
        self.assertEqual(filtered_target.value, 3)

    @with_transaction()
    def test_search_non_equals_filter(self):
        "Test search many2many non equals with filter"
        Many2Many = Pool().get('test.many2many_filter')
        many2many, = Many2Many.create([{
                    'targets': [('create', [{'value': -1}])],
                    }])

        many2manys = Many2Many.search([('targets', '!=', None)])
        many2manys_filtered = Many2Many.search(
            [('filtered_targets', '!=', None)])

        self.assertListEqual(many2manys, [many2many])
        self.assertListEqual(many2manys_filtered, [])

    @with_transaction()
    def test_search_join_filter(self):
        "Test search many2many join with filter"
        Many2Many = Pool().get('test.many2many_filter')
        many2many, = Many2Many.create([{
                    'targets': [('create', [{'value': -1}])],
                    }])

        many2manys = Many2Many.search([('targets.value', '=', -1)])
        many2manys_filtered = Many2Many.search(
            [('filtered_targets.value', '=', -1)])

        self.assertListEqual(many2manys, [many2many])
        self.assertListEqual(many2manys_filtered, [])

    def create_tree(self, Many2Many):
        self.second1, self.second2, self.second3, self.second4 = (
            Many2Many.create([
                    {},
                    {},
                    {},
                    {},
                    ]))
        self.first1, self.first2, self.first3, self.first4 = Many2Many.create([
                {'children': [('add', [self.second1.id, self.second2.id])]},
                {'children': [('add', [self.second1.id, self.second2.id])]},
                {'children': [('add', [self.second3.id, self.second4.id])]},
                {'children': [('add', [self.second4.id])]},
                ])
        self.root1, self.root2 = Many2Many.create([
                {'children': [
                        ('add', [
                                self.first1.id, self.first2.id,
                                self.second1.id])]},
                {'children': [('add', [self.first3.id, self.first4.id])]},
                ])

    @with_transaction()
    def test_search_child_of_root1(self):
        "Test search many2many child of root1"
        Many2Many = Pool().get('test.many2many_tree')
        self.create_tree(Many2Many)

        result = Many2Many.search([
                ('parents', 'child_of', [self.root1.id]),
                ])

        self.assertListEqual(
            sorted(result),
            sorted([self.root1,
                    self.first1, self.first2,
                    self.second1, self.second2]))

    @with_transaction()
    def test_search_not_child_of_root1(self):
        "Test search many2many not child of root1"
        Many2Many = Pool().get('test.many2many_tree')
        self.create_tree(Many2Many)

        result = Many2Many.search([
                ('parents', 'not child_of', [self.root1.id]),
                ])

        self.assertListEqual(
            sorted(result),
            sorted([self.root2,
                    self.first3, self.first4,
                    self.second3, self.second4]))

    @with_transaction()
    def test_search_child_of_second1(self):
        "Test search many2many child of second1"
        Many2Many = Pool().get('test.many2many_tree')
        self.create_tree(Many2Many)

        result = Many2Many.search([
                ('parents', 'child_of', [self.second1.id]),
                ])

        self.assertListEqual(result, [self.second1])

    @with_transaction()
    def test_search_not_child_of_second1(self):
        "Test search many2many not child of second1"
        Many2Many = Pool().get('test.many2many_tree')
        self.create_tree(Many2Many)

        result = Many2Many.search([
                ('parents', 'not child_of', [self.second1.id]),
                ])

        self.assertListEqual(
            sorted(result),
            sorted([self.root1, self.root2,
                    self.first1, self.first2, self.first3, self.first4,
                    self.second2, self.second3, self.second4]))

    @with_transaction()
    def test_search_child_of_empty(self):
        "Test search many2many child of empty"
        Many2Many = Pool().get('test.many2many_tree')
        self.create_tree(Many2Many)

        result = Many2Many.search([
                ('parents', 'child_of', []),
                ])

        self.assertListEqual(result, [])

    @with_transaction()
    def test_search_not_child_of_empty(self):
        "Test search many2many not child of empty"
        Many2Many = Pool().get('test.many2many_tree')
        self.create_tree(Many2Many)

        result = Many2Many.search([
                ('parents', 'not child_of', []),
                ])

        self.assertListEqual(
            sorted(result),
            sorted([self.root1, self.root2,
                    self.first1, self.first2, self.first3, self.first4,
                    self.second1, self.second2, self.second3, self.second4]))

    @with_transaction()
    def test_search_parent_of_root1(self):
        "Test search many2many parent of root1"
        Many2Many = Pool().get('test.many2many_tree')
        self.create_tree(Many2Many)

        result = Many2Many.search([
                ('parents', 'parent_of', [self.root1.id]),
                ])

        self.assertListEqual(result, [self.root1])

    @with_transaction()
    def test_search_not_parent_of_root1(self):
        "Test search many2many not parent of root1"
        Many2Many = Pool().get('test.many2many_tree')
        self.create_tree(Many2Many)

        result = Many2Many.search([
                ('parents', 'not parent_of', [self.root1.id]),
                ])

        self.assertListEqual(
            sorted(result),
            sorted([self.root2,
                    self.first1, self.first2, self.first3, self.first4,
                    self.second1, self.second2, self.second3, self.second4]))

    @with_transaction()
    def test_search_parent_of_second4(self):
        "Test search many2many parent of second4"
        Many2Many = Pool().get('test.many2many_tree')
        self.create_tree(Many2Many)

        result = Many2Many.search([
                ('parents', 'parent_of', [self.second4.id]),
                ])

        self.assertListEqual(
            sorted(result),
            sorted([self.root2, self.first3, self.first4, self.second4]))

    @with_transaction()
    def test_search_not_parent_of_second4(self):
        "Test search many2many not parent of second4"
        Many2Many = Pool().get('test.many2many_tree')
        self.create_tree(Many2Many)

        result = Many2Many.search([
                ('parents', 'not parent_of', [self.second4.id]),
                ])

        self.assertListEqual(
            sorted(result),
            sorted([self.root1,
                    self.first1, self.first2,
                    self.second1, self.second2, self.second3]))

    @with_transaction()
    def test_search_parent_of_empty(self):
        "Test search many2many parent of empty"
        Many2Many = Pool().get('test.many2many_tree')
        self.create_tree(Many2Many)

        result = Many2Many.search([
                ('parents', 'parent_of', []),
                ])

        self.assertListEqual(result, [])

    @with_transaction()
    def test_search_not_parent_of_empty(self):
        "Test search many2many not parent of empty"
        Many2Many = Pool().get('test.many2many_tree')
        self.create_tree(Many2Many)

        result = Many2Many.search([
                ('parents', 'not parent_of', []),
                ])

        self.assertListEqual(
            sorted(result),
            sorted([self.root1, self.root2,
                    self.first1, self.first2, self.first3, self.first4,
                    self.second1, self.second2, self.second3, self.second4]))

    @with_transaction()
    def test_context_attribute(self):
        "Test context on many2many attribute"
        pool = Pool()
        Many2Many = pool.get('test.many2many_context')

        record, = Many2Many.create([{
                    'targets': [('create', [{}])],
                    }])

        self.assertEqual(record.targets[0].context, 'foo')

    @with_transaction()
    def test_context_read(self):
        "Test context on many2many read"
        pool = Pool()
        Many2Many = pool.get('test.many2many_context')

        record, = Many2Many.create([{
                    'targets': [('create', [{}])],
                    }])
        data, = Many2Many.read([record.id], ['targets.context'])

        self.assertEqual(data['targets.'][0]['context'], 'foo')

    @with_transaction()
    def test_context_set(self):
        "Test context on many2many set"
        pool = Pool()
        Many2Many = pool.get('test.many2many_context')
        Target = pool.get('test.many2many_context.target')

        target, = Target.create([{}])
        record = Many2Many(targets=[target.id])

        self.assertEqual(record.targets[0].context, 'foo')


class FieldMany2ManyReferenceTestCase(unittest.TestCase, CommonTestCaseMixin):
    "Test Field Many2Many Reference"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    def Many2Many(self):
        return Pool().get('test.many2many_reference')

    def Many2ManyTarget(self):
        return Pool().get('test.many2many_reference.target')


def suite():
    suite_ = unittest.TestSuite()
    loader = unittest.TestLoader()
    suite_.addTests(loader.loadTestsFromTestCase(FieldMany2ManyTestCase))
    suite_.addTests(
        loader.loadTestsFromTestCase(FieldMany2ManyReferenceTestCase))
    return suite_
