# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from unittest.mock import Mock

from trytond.model import sort
from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction


class SequenceOrderedMixinTestCase(unittest.TestCase):
    'Test SequenceOrderedMixin'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_order(self):
        'Test order'
        pool = Pool()
        Order = pool.get('test.order.sequence')

        models = []
        for i in reversed(list(range(1, 4))):
            models.append(Order(sequence=i))
        Order.save(models)
        models.reverse()
        self.assertListEqual(Order.search([]), models)

        model = models.pop()
        model.sequence = None
        model.save()
        models.insert(0, model)

        self.assertListEqual(Order.search([]), models)

    def test_sort(self):
        "Test sort"
        record1 = Mock()
        record1.name = "foo"
        record2 = Mock()
        record2.name = "bar"

        self.assertListEqual(
            sort([record1, record2], [('name', 'ASC')]),
            [record2, record1])
        self.assertListEqual(
            sort([record1, record2], [('name', 'DESC')]),
            [record1, record2])

    def test_sort_multiple(self):
        "Test sort multiple"
        record1 = Mock()
        record1.name = "foo"
        record1.id = 1
        record2 = Mock()
        record2.name = "foo"
        record2.id = 2

        self.assertListEqual(
            sort([record1, record2], [('name', 'ASC'), ('id', 'DESC')]),
            [record2, record1])
        self.assertListEqual(
            sort([record1, record2], [('name', 'ASC'), ('id', 'ASC')]),
            [record1, record2])

    def test_sort_dot(self):
        "Test sort with dot"
        record1 = Mock()
        record1.ref = Mock()
        record1.ref.name = "foo"
        record2 = Mock()
        record2.ref = Mock()
        record2.ref.name = "bar"

        self.assertListEqual(
            sort([record1, record2], [('ref.name', 'ASC')]),
            [record2, record1])
        self.assertListEqual(
            sort([record1, record2], [('ref.name', 'DESC')]),
            [record1, record2])

    def test_sort_nulls(self):
        "Test sort nulls"
        record1 = Mock()
        record1.name = "foo"
        record2 = Mock()
        record2.name = None

        self.assertListEqual(
            sort([record1, record2], [('name', 'ASC NULLS FIRST')]),
            [record2, record1])
        self.assertListEqual(
            sort([record1, record2], [('name', 'DESC NULLS FIRST')]),
            [record2, record1])
        self.assertListEqual(
            sort([record1, record2], [('name', 'ASC NULLS LAST')]),
            [record1, record2])
        self.assertListEqual(
            sort([record1, record2], [('name', 'DESC NULLS LAST')]),
            [record1, record2])
