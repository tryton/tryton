# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import sys
import unittest
from unittest.mock import patch

from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.transaction import inactive_records

from .test_tree import TreeTestCaseMixin


class MPTTTestCase(TreeTestCaseMixin, unittest.TestCase):
    'Test Modified Preorder Tree Traversal'
    model_name = 'test.mptt'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    def check_tree(self, parent_id=None, left=-1, right=sys.maxsize):
        pool = Pool()
        Mptt = pool.get(self.model_name)

        with inactive_records():
            childs = Mptt.search([
                    ('parent', '=', parent_id),
                    ], order=[('left', 'ASC')])
        for child in childs:
            self.assertGreater(child.left, left,
                msg='%s: left %d <= parent left %d' % (
                    child, child.left, left))
            self.assertLess(child.left, child.right,
                msg='%s: left %d >= right %d' % (
                    child, child.left, child.right))
            self.assertLess(child.right, right,
                msg='%s: right %d >= parent right %d' % (
                    child, child.right, right))
            self.check_tree(child.id, left=child.left,
                right=child.right)
        next_left = -1
        for child in childs:
            self.assertGreater(child.left, next_left,
                msg='%s: left %d <= next left %d' % (
                    child, child.left, next_left))
            next_left = child.right
        childs.reverse()
        previous_right = sys.maxsize
        for child in childs:
            self.assertLess(child.right, previous_right,
                msg='%s: right %d >= previous right %d' % (
                    child, child.right, previous_right))
            previous_right = child.left

    def rebuild(self):
        pool = Pool()
        Mptt = pool.get(self.model_name)
        Mptt._rebuild_tree('parent', None, 0)

    @with_transaction()
    def test_update_only_if_parent_is_modified(self):
        'The left and right fields must only be updated if parent is modified'
        pool = Pool()
        Mptt = pool.get('test.mptt')

        self.create()

        records = Mptt.search([
                ('parent', '=', None),
                ])
        with patch.object(Mptt, '_update_tree') as update, \
                patch.object(Mptt, '_rebuild_tree') as rebuild:
            Mptt.write(records, {'name': 'Parent Records'})
            self.assertFalse(update.called)
            self.assertFalse(rebuild.called)

            first_parent, second_parent = records[:2]
            Mptt.write(list(first_parent.childs), {
                    'parent': second_parent.id,
                    })

            self.assertTrue(update.called or rebuild.called)

    @with_transaction()
    def test_nested_create(self):
        pool = Pool()
        Mptt = pool.get('test.mptt')

        record, = Mptt.create([{
                    'name': 'Test nested create 1',
                    'childs': [('create', [{
                                    'name': 'Test nested create 1 1',
                                    }])],
                    }])
        self.check_tree()
