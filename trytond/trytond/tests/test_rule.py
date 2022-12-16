# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import json
import unittest

from trytond.exceptions import UserError
from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction


class ModelRuleTestCase(unittest.TestCase):
    "Test Model Rule"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_perm_create_without_rule(self):
        "Test create without rule"
        pool = Pool()
        TestRule = pool.get('test.rule')

        test, = TestRule.create([{}])

    @with_transaction()
    def test_perm_create_with_rule(self):
        "Test create with rule"
        pool = Pool()
        TestRule = pool.get('test.rule')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'model': model.id,
                    'global_p': True,
                    'perm_read': False,
                    'perm_create': True,
                    'perm_write': False,
                    'perm_delete': False,
                    'rules': [('create', [{
                                    'domain': json.dumps(
                                        [('field', '!=', 'foo')]),
                                    }])],
                    }])

        test, = TestRule.create([{'field': 'bar'}])

    @with_transaction()
    def test_perm_create_with_rule_fail(self):
        "Test create with rule fail"
        pool = Pool()
        TestRule = pool.get('test.rule')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'model': model.id,
                    'global_p': True,
                    'perm_read': False,
                    'perm_create': True,
                    'perm_write': False,
                    'perm_delete': False,
                    'rules': [('create', [{
                                    'domain': json.dumps(
                                        [('field', '!=', 'foo')]),
                                    }])],
                    }])

        with self.assertRaises(UserError):
            test, = TestRule.create([{'field': 'foo'}])

    @with_transaction()
    def test_perm_write_without_rule(self):
        "Test write without rule"
        pool = Pool()
        TestRule = pool.get('test.rule')

        test, = TestRule.create([{}])

        TestRule.write([test], {'field': 'foo'})

    @with_transaction()
    def test_perm_write_with_rule(self):
        "Test write with rule"
        pool = Pool()
        TestRule = pool.get('test.rule')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'model': model.id,
                    'global_p': True,
                    'perm_read': False,
                    'perm_create': False,
                    'perm_write': True,
                    'perm_delete': False,
                    'rules': [('create', [{
                                    'domain': json.dumps(
                                        [('field', '!=', 'foo')]),
                                    }])],
                    }])
        test, = TestRule.create([{'field': 'test'}])

        TestRule.write([test], {'field': 'bar'})

    @with_transaction()
    def test_perm_write_with_rule_fail_before(self):
        "Test write with rule fail before"
        pool = Pool()
        TestRule = pool.get('test.rule')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'model': model.id,
                    'global_p': True,
                    'perm_read': False,
                    'perm_create': False,
                    'perm_write': True,
                    'perm_delete': False,
                    'rules': [('create', [{
                                    'domain': json.dumps(
                                        [('field', '!=', 'foo')]),
                                    }])],
                    }])
        test, = TestRule.create([{'field': 'foo'}])

        with self.assertRaises(UserError):
            TestRule.write([test], {'field': 'bar'})

    @with_transaction()
    def test_perm_write_with_rule_fail_after(self):
        "Test write with rule fail after"
        pool = Pool()
        TestRule = pool.get('test.rule')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'model': model.id,
                    'global_p': True,
                    'perm_read': False,
                    'perm_create': False,
                    'perm_write': True,
                    'perm_delete': False,
                    'rules': [('create', [{
                                    'domain': json.dumps(
                                        [('field', '!=', 'foo')]),
                                    }])],
                    }])
        test, = TestRule.create([{'field': 'bar'}])

        with self.assertRaises(UserError):
            TestRule.write([test], {'field': 'foo'})

    @with_transaction()
    def test_perm_delete_without_rule(self):
        "Test delete without rule"
        pool = Pool()
        TestRule = pool.get('test.rule')

        test, = TestRule.create([{}])

        TestRule.delete([test])

    @with_transaction()
    def test_perm_delete_with_rule(self):
        "Test delete with rule"
        pool = Pool()
        TestRule = pool.get('test.rule')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'model': model.id,
                    'global_p': True,
                    'perm_read': False,
                    'perm_create': False,
                    'perm_write': False,
                    'perm_delete': True,
                    'rules': [('create', [{
                                    'domain': json.dumps(
                                        [('field', '!=', 'foo')]),
                                    }])],
                    }])
        test, = TestRule.create([{'field': 'bar'}])

        TestRule.delete([test])

    @with_transaction()
    def test_perm_delete_with_rule_fail(self):
        "Test delete with rule fail"
        pool = Pool()
        TestRule = pool.get('test.rule')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'model': model.id,
                    'global_p': True,
                    'perm_read': False,
                    'perm_create': False,
                    'perm_write': False,
                    'perm_delete': True,
                    'rules': [('create', [{
                                    'domain': json.dumps(
                                        [('field', '!=', 'foo')]),
                                    }])],
                    }])
        test, = TestRule.create([{'field': 'foo'}])

        with self.assertRaises(UserError):
            TestRule.delete([test])

    @with_transaction()
    def test_perm_read_without_rule(self):
        "Test read without rule"
        pool = Pool()
        TestRule = pool.get('test.rule')

        test, = TestRule.create([{'field': 'foo'}])

        TestRule.read([test.id])

    @with_transaction()
    def test_perm_read_with_rule(self):
        "Test read with rule"
        pool = Pool()
        TestRule = pool.get('test.rule')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'model': model.id,
                    'global_p': True,
                    'perm_read': True,
                    'perm_create': False,
                    'perm_write': False,
                    'perm_delete': False,
                    'rules': [('create', [{
                                    'domain': json.dumps(
                                        [('field', '!=', 'foo')]),
                                    }])],
                    }])
        test, = TestRule.create([{'field': 'bar'}])

        TestRule.read([test.id])

    @with_transaction()
    def test_perm_read_with_rule_fail(self):
        "Test read with rule fail"
        pool = Pool()
        TestRule = pool.get('test.rule')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'model': model.id,
                    'global_p': True,
                    'perm_read': True,
                    'perm_create': False,
                    'perm_write': False,
                    'perm_delete': False,
                    'rules': [('create', [{
                                    'domain': json.dumps(
                                        [('field', '!=', 'foo')]),
                                    }])],
                    }])
        test, = TestRule.create([{'field': 'foo'}])

        with self.assertRaises(UserError):
            TestRule.read([test.id])

    @with_transaction()
    def test_search_without_rule(self):
        "Test search without rule"
        pool = Pool()
        TestRule = pool.get('test.rule')

        test, = TestRule.create([{'field': 'foo'}])

        self.assertListEqual(TestRule.search([]), [test])

    @with_transaction()
    def test_search_with_rule(self):
        "Test search with rule"
        pool = Pool()
        TestRule = pool.get('test.rule')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'model': model.id,
                    'global_p': True,
                    'perm_read': True,
                    'perm_create': False,
                    'perm_write': False,
                    'perm_delete': False,
                    'rules': [('create', [{
                                    'domain': json.dumps(
                                        [('field', '!=', 'foo')]),
                                    }])],
                    }])
        test, = TestRule.create([{'field': 'bar'}])

        self.assertListEqual(TestRule.search([]), [test])

    @with_transaction()
    def test_search_with_rule_match(self):
        "Test search with rule match"
        pool = Pool()
        TestRule = pool.get('test.rule')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'model': model.id,
                    'global_p': True,
                    'perm_read': True,
                    'perm_create': False,
                    'perm_write': False,
                    'perm_delete': False,
                    'rules': [('create', [{
                                    'domain': json.dumps(
                                        [('field', '!=', 'foo')]),
                                    }])],
                    }])
        test, = TestRule.create([{'field': 'foo'}])

        self.assertListEqual(TestRule.search([]), [])


def suite():
    suite_ = unittest.TestSuite()
    suite_.addTests(
        unittest.TestLoader().loadTestsFromTestCase(ModelRuleTestCase))
    return suite_
