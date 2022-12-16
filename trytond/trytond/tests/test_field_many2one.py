# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from trytond.exceptions import UserError
from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction


class FieldMany2OneTestCase(unittest.TestCase):
    "Test Field Many2One"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_create_id(self):
        "Test create many2one with id"
        pool = Pool()
        Target = pool.get('test.many2one_target')
        Many2One = pool.get('test.many2one')
        target, = Target.create([{}])

        many2one, = Many2One.create([{
                    'many2one': target.id,
                    }])

        self.assertEqual(many2one.many2one, target)

    @with_transaction()
    def test_create_instance(self):
        "Test create many2one with instance"
        pool = Pool()
        Target = pool.get('test.many2one_target')
        Many2One = pool.get('test.many2one')
        target, = Target.create([{}])

        many2one, = Many2One.create([{
                    'many2one': target,
                    }])

        self.assertEqual(many2one.many2one, target)

    @with_transaction()
    def test_create_no_foreign_key(self):
        "Test create many2one without foreign key"
        pool = Pool()
        Target = pool.get('test.many2one_target_storage')
        Many2One = pool.get('test.many2one_no_foreign_key')

        many2one = Many2One(many2one=1)
        many2one.save()

        self.assertEqual(many2one.many2one, Target(1))

    @with_transaction()
    def test_create_with_domain_valid(self):
        "Test create many2one with valid domain"
        pool = Pool()
        Target = pool.get('test.many2one_target')
        Many2One = pool.get('test.many2one_domainvalidation')
        target, = Target.create([{'value': 6}])

        many2one, = Many2One.create([{
                    'many2one': target.id,
                    }])

        self.assertEqual(many2one.many2one, target)

    @with_transaction()
    def test_create_with_domain_invalid(self):
        "Test create many2one with invalid domain"
        pool = Pool()
        Target = pool.get('test.many2one_target')
        Many2One = pool.get('test.many2one_domainvalidation')
        target, = Target.create([{'value': 1}])

        with self.assertRaises(UserError):
            Many2One.create([{
                        'many2one': target.id,
                        }])

    @with_transaction()
    def test_create_with_domain_inactive(self):
        "Test create many2one with domain and inactive target"
        pool = Pool()
        Target = pool.get('test.many2one_target')
        Many2One = pool.get('test.many2one_domainvalidation')
        target, = Target.create([{'value': 6, 'active': False}])

        many2one, = Many2One.create([{
                    'many2one': target.id,
                    }])

        self.assertEqual(many2one.many2one, target)

    @with_transaction()
    def test_search_order_default(self):
        "Test search order by many2one default"
        pool = Pool()
        Target = pool.get('test.many2one_target')
        Many2One = pool.get('test.many2one')
        for value in [5, 3, 2]:
            target, = Target.create([{'value': value}])
            Many2One.create([{'many2one': target}])

        records = Many2One.search([], order=[('many2one', 'ASC')])
        values = [r.many2one.value for r in records]

        self.assertListEqual(values, [2, 3, 5])

    @with_transaction()
    def test_search_order_id(self):
        "Test search order by many2one id"
        pool = Pool()
        Target = pool.get('test.many2one_target')
        Many2One = pool.get('test.many2one')
        target_ids = []
        for value in [5, 3, 2]:
            target, = Target.create([{'value': value}])
            Many2One.create([{'many2one': target}])
            target_ids.append(target.id)
        target_ids.sort()

        records = Many2One.search([], order=[('many2one.id', 'ASC')])
        ids = [r.many2one.id for r in records]

        self.assertListEqual(ids, target_ids)

    @with_transaction()
    def test_search_order_value(self):
        "Test search order by many2one value"
        pool = Pool()
        Target = pool.get('test.many2one_target')
        Many2One = pool.get('test.many2one')
        for value in [5, 3, 2]:
            target, = Target.create([{'value': value}])
            Many2One.create([{'many2one': target}])

        records = Many2One.search([], order=[('many2one.value', 'ASC')])
        values = [r.many2one.value for r in records]

        self.assertListEqual(values, [2, 3, 5])

    @with_transaction()
    def _test_search_join(self, target_search):
        pool = Pool()
        Target = pool.get('test.many2one_target')
        Many2One = pool.get('test.many2one')
        target1, target2 = Target.create([
                {'value': 1},
                {'value': 2},
                ])
        many2one1, many2one2 = Many2One.create([
                {'many2one': target1},
                {'many2one': target2},
                ])

        def set_target_search(target_search):
            Many2One.many2one.target_search = target_search
        self.addCleanup(set_target_search, Many2One.many2one.target_search)
        set_target_search(target_search)

        many2ones = Many2One.search([
                ('many2one.value', '=', 1),
                ])

        self.assertListEqual(many2ones, [many2one1])

    def test_search_join(self):
        "Test search by many2one join"
        self._test_search_join('join')

    def test_search_subquery(self):
        "Test search by many2one subquery"
        self._test_search_join('subquery')

    def create_tree(self, Many2One):
        self.root1, self.root2 = Many2One.create([{}, {}])
        self.first1, self.first2, self.first3, self.first4 = Many2One.create([
                {'many2one': self.root1},
                {'many2one': self.root1},
                {'many2one': self.root2},
                {'many2one': self.root2},
                ])
        self.second1, self.second2, self.second3, self.second4 = (
            Many2One.create([
                {'many2one': self.first1},
                {'many2one': self.first1},
                {'many2one': self.first2},
                {'many2one': self.first2},
                ]))

    @with_transaction()
    def _test_search_child_of_root1(self, model_name):
        Many2One = Pool().get(model_name)
        self.create_tree(Many2One)

        result = Many2One.search([
                ('many2one', 'child_of', [self.root1.id]),
                ])

        self.assertListEqual(
            sorted(result),
            sorted([self.root1,
                    self.first1, self.first2,
                    self.second1, self.second2, self.second3, self.second4]))

    def test_search_tree_child_of_root1(self):
        "Test search many2one tree child of root1"
        self._test_search_child_of_root1('test.many2one_tree')

    def test_search_mptt_child_of_root1(self):
        "Test search many2one mptt child of root1"
        self._test_search_child_of_root1('test.many2one_mptt')

    @with_transaction()
    def _test_search_not_child_of_root1(self, model_name):
        Many2One = Pool().get(model_name)
        self.create_tree(Many2One)

        result = Many2One.search([
                ('many2one', 'not child_of', [self.root1.id]),
                ])

        self.assertListEqual(
            sorted(result),
            sorted([self.root2, self.first3, self.first4]))

    def test_search_tree_not_child_of_root1(self):
        "Test search many2one tree not child of root1"
        self._test_search_not_child_of_root1('test.many2one_tree')

    def test_search_mptt_not_child_of_root1(self):
        "Test search many2one mptt not child of root1"
        self._test_search_not_child_of_root1('test.many2one_mptt')

    @with_transaction()
    def _test_search_child_of_second1(self, model_name):
        Many2One = Pool().get(model_name)
        self.create_tree(Many2One)

        result = Many2One.search([
                ('many2one', 'child_of', [self.second1.id]),
                ])

        self.assertListEqual(result, [self.second1])

    def test_search_tree_child_of_second1(self):
        "Test search many2one tree child of second1"
        self._test_search_child_of_second1('test.many2one_tree')

    def test_search_mptt_child_of_second1(self):
        "Test search many2one mptt child of second1"
        self._test_search_child_of_second1('test.many2one_mptt')

    @with_transaction()
    def _test_search_not_child_of_second1(self, model_name):
        Many2One = Pool().get(model_name)
        self.create_tree(Many2One)

        result = Many2One.search([
                ('many2one', 'not child_of', [self.second1.id]),
                ])

        self.assertListEqual(
            sorted(result),
            sorted([self.root1, self.root2,
                    self.first1, self.first2, self.first3, self.first4,
                    self.second2, self.second3, self.second4]))

    def test_search_tree_not_child_of_second1(self):
        "Test search many2one tree not child of second1"
        self._test_search_not_child_of_second1('test.many2one_tree')

    def test_search_mptt_not_child_of_second1(self):
        "Test search many2one mptt not child of second1"
        self._test_search_not_child_of_second1('test.many2one_mptt')

    @with_transaction()
    def _test_search_child_of_empty(self, model_name):
        Many2One = Pool().get(model_name)
        self.create_tree(Many2One)

        result = Many2One.search([
                ('many2one', 'child_of', []),
                ])

        self.assertListEqual(result, [])

    def test_search_tree_child_of_empty(self):
        "Test search many2one tree child of empty"
        self._test_search_child_of_empty('test.many2one_tree')

    def test_search_mptt_child_of_empty(self):
        "Test search many2one mptt child of empty"
        self._test_search_child_of_empty('test.many2one_mptt')

    @with_transaction()
    def _test_search_not_child_of_empty(self, model_name):
        Many2One = Pool().get(model_name)
        self.create_tree(Many2One)

        result = Many2One.search([
                ('many2one', 'not child_of', []),
                ])

        self.assertListEqual(
            sorted(result),
            sorted([self.root1, self.root2,
                    self.first1, self.first2, self.first3, self.first4,
                    self.second1, self.second2, self.second3, self.second4]))

    def test_search_tree_not_child_of_empty(self):
        "Test search many2one tree not child of empty"
        self._test_search_not_child_of_empty('test.many2one_tree')

    def test_search_mptt_not_child_of_empty(self):
        "Test search many2one mptt not child of empty"
        self._test_search_not_child_of_empty('test.many2one_mptt')

    @with_transaction()
    def _test_search_child_of_none(self, model_name):
        Many2One = Pool().get(model_name)
        self.create_tree(Many2One)

        result = Many2One.search([
                ('many2one', 'child_of', [None]),
                ])

        self.assertListEqual(result, [])

    def test_search_tree_child_of_none(self):
        "Test search many2one tree child of None"
        self._test_search_child_of_none('test.many2one_tree')

    def test_search_mptt_child_of_none(self):
        "Test search many2one mptt child of None"
        self._test_search_child_of_none('test.many2one_mptt')

    @with_transaction()
    def _test_search_parent_of_root1(self, model_name):
        Many2One = Pool().get(model_name)
        self.create_tree(Many2One)

        result = Many2One.search([
                ('many2one', 'parent_of', [self.root1.id]),
                ])

        self.assertListEqual(result, [self.root1])

    def test_search_tree_parent_of_root1(self):
        "Test search many2one tree parent of root1"
        self._test_search_parent_of_root1('test.many2one_tree')

    def test_search_mptt_parent_of_root1(self):
        "Test search many2one mptt parent of root1"
        self._test_search_parent_of_root1('test.many2one_mptt')

    @with_transaction()
    def _test_search_not_parent_of_root1(self, model_name):
        Many2One = Pool().get(model_name)
        self.create_tree(Many2One)

        result = Many2One.search([
                ('many2one', 'not parent_of', [self.root1.id]),
                ])

        self.assertListEqual(
            sorted(result),
            sorted([self.root2,
                    self.first1, self.first2, self.first3, self.first4,
                    self.second1, self.second2, self.second3, self.second4]))

    def test_search_tree_not_parent_of_root1(self):
        "Test search many2one tree not parent of root1"
        self._test_search_not_parent_of_root1('test.many2one_tree')

    def test_search_mptt_not_parent_of_root1(self):
        "Test search many2one mptt not parent of root1"
        self._test_search_not_parent_of_root1('test.many2one_mptt')

    @with_transaction()
    def _test_search_parent_of_second4(self, model_name):
        Many2One = Pool().get(model_name)
        self.create_tree(Many2One)

        result = Many2One.search([
                ('many2one', 'parent_of', [self.second4.id]),
                ])

        self.assertListEqual(
            sorted(result),
            sorted([self.root1, self.first2, self.second4]))

    def test_search_tree_parent_of_second4(self):
        "Test search many2one tree parent of second4"
        self._test_search_parent_of_second4('test.many2one_tree')

    def test_search_mptt_parent_of_second4(self):
        "Test search many2one mptt parent of second4"
        self._test_search_parent_of_second4('test.many2one_mptt')

    @with_transaction()
    def _test_search_not_parent_of_second4(self, model_name):
        Many2One = Pool().get(model_name)
        self.create_tree(Many2One)

        result = Many2One.search([
                ('many2one', 'not parent_of', [self.second4.id]),
                ])

        self.assertListEqual(
            sorted(result),
            sorted([self.root2,
                    self.first1, self.first3, self.first4,
                    self.second1, self.second2, self.second3]))

    def test_search_tree_not_parent_of_second4(self):
        "Test search many2one tree not parent of second4"
        self._test_search_not_parent_of_second4('test.many2one_tree')

    def test_search_mptt_not_parent_of_second4(self):
        "Test search many2one mptt not parent of second4"
        self._test_search_not_parent_of_second4('test.many2one_mptt')

    @with_transaction()
    def _test_search_parent_of_empty(self, model_name):
        Many2One = Pool().get(model_name)
        self.create_tree(Many2One)

        result = Many2One.search([
                ('many2one', 'parent_of', []),
                ])

        self.assertListEqual(result, [])

    def test_search_tree_parent_of_empty(self):
        "Test search many2one tree parent of empty"
        self._test_search_parent_of_empty('test.many2one_tree')

    def test_search_mptt_parent_of_empty(self):
        "Test search many2one mptt parent of empty"
        self._test_search_parent_of_empty('test.many2one_mptt')

    @with_transaction()
    def _test_search_not_parent_of_empty(self, model_name):
        Many2One = Pool().get(model_name)
        self.create_tree(Many2One)

        result = Many2One.search([
                ('many2one', 'not parent_of', []),
                ])

        self.assertListEqual(
            sorted(result),
            sorted([self.root1, self.root2,
                    self.first1, self.first2, self.first3, self.first4,
                    self.second1, self.second2, self.second3, self.second4]))

    def test_search_tree_not_parent_of_empty(self):
        "Test search many2one tree not parent of empty"
        self._test_search_not_parent_of_empty('test.many2one_tree')

    def test_search_mptt_not_parent_of_empty(self):
        "Test search many2one mptt not parent of empty"
        self._test_search_not_parent_of_empty('test.many2one_mptt')


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(FieldMany2OneTestCase)
