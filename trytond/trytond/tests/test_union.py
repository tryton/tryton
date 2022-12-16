# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.pool import Pool


class UnionMixinTestCase(unittest.TestCase):
    'Test UnionMixin'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_union(self):
        'Test union'
        pool = Pool()
        Union = pool.get('test.union')

        for i in range(1, 4):
            Model = pool.get('test.model.union%s' % i)
            for j in range(3):
                model = Model(name='%s - %s' % (i, j))
                if hasattr(Model, 'optional'):
                    model.optional = 'optional'
                model.save()

        self.assertEqual(len(Union.search([])), 9)
        record, = Union.search([
                ('name', '=', '2 - 2'),
                ])
        self.assertEqual(record.name, '2 - 2')
        self.assertEqual(record.optional, None)

        record, = Union.search([
                ('optional', '=', 'optional'),
                ], limit=1)
        self.assertEqual(record.optional, 'optional')

    @with_transaction()
    def test_union_union(self):
        'Test union of union'
        pool = Pool()
        Union = pool.get('test.union.union')

        for i in range(1, 5):
            Model = pool.get('test.model.union%s' % i)
            for j in range(3):
                model = Model(name='%s - %s' % (i, j))
                model.save()

        self.assertEqual(len(Union.search([])), 12)
        record, = Union.search([
                ('name', '=', '2 - 2'),
                ])
        self.assertEqual(record.name, '2 - 2')
        record, = Union.search([
                ('name', '=', '4 - 1'),
                ])
        self.assertEqual(record.name, '4 - 1')

    @with_transaction()
    def test_union_tree(self):
        'Test union tree'
        pool = Pool()
        Union = pool.get('test.union.tree')
        Model1 = pool.get('test.model.union.tree1')
        Model2 = pool.get('test.model.union.tree2')

        roots = Model1.create([{
                    'name': 'Root1',
                    }, {
                    'name': 'Root2',
                    }, {
                    'name': 'Root3',
                    }])

        Model2.create([{
                    'name': 'Not child',  # To shift ids
                    }, {
                    'name': 'Child1',
                    'parent': roots[1].id,
                    }, {
                    'name': 'Child2',
                    'parent': roots[1].id,
                    }, {
                    'name': 'Child3',
                    'parent': roots[2].id,
                    }])

        uroots = Union.search([('parent', '=', None)],
            order=[('name', 'ASC')])

        self.assertEqual(len(uroots), 4)
        names = [r.name for r in uroots]
        self.assertEqual(names, ['Not child', 'Root1', 'Root2', 'Root3'])
        childs = [len(r.childs) for r in uroots]
        self.assertEqual(childs, [0, 0, 2, 1])
        child_names = sorted((r.name for r in uroots[2].childs))
        self.assertEqual(child_names, ['Child1', 'Child2'])
        self.assertEqual(uroots[3].childs[0].name, 'Child3')


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(UnionMixinTestCase)
