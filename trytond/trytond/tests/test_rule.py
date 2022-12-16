# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import json
import unittest

from trytond.model.exceptions import AccessError
from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction

_context = {'_check_access': True}


class ModelRuleTestCase(unittest.TestCase):
    "Test Model Rule"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction(context=_context)
    def test_perm_create_without_rule(self):
        "Test create without rule"
        pool = Pool()
        TestRule = pool.get('test.rule')

        test, = TestRule.create([{}])

    @with_transaction(context=_context)
    def test_perm_create_with_rule(self):
        "Test create with rule"
        pool = Pool()
        TestRule = pool.get('test.rule')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'name': "Field different from foo",
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

    @with_transaction(context=_context)
    def test_perm_create_with_rule_fail(self):
        "Test create with rule fail"
        pool = Pool()
        TestRule = pool.get('test.rule')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'name': "Field different from foo",
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

        with self.assertRaisesRegex(AccessError, "Field different from foo"):
            test, = TestRule.create([{'field': 'foo'}])

    @with_transaction(context=_context)
    def test_perm_create_with_default_rule_fail(self):
        "Test create with default rule fail"
        pool = Pool()
        TestRule = pool.get('test.rule')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'name': "Field different from foo",
                    'model': model.id,
                    'global_p': False,
                    'default_p': True,
                    'perm_read': False,
                    'perm_create': True,
                    'perm_write': False,
                    'perm_delete': False,
                    'rules': [('create', [{
                                    'domain': json.dumps(
                                        [('field', '!=', 'foo')]),
                                    }])],
                    }])

        with self.assertRaisesRegex(AccessError, "Field different from foo"):
            test, = TestRule.create([{'field': 'foo'}])

    @with_transaction(context=_context)
    def test_perm_write_without_rule(self):
        "Test write without rule"
        pool = Pool()
        TestRule = pool.get('test.rule')

        test, = TestRule.create([{}])

        TestRule.write([test], {'field': 'foo'})

    @with_transaction(context=_context)
    def test_perm_write_with_rule(self):
        "Test write with rule"
        pool = Pool()
        TestRule = pool.get('test.rule')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'name': "Field different from foo",
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

    @with_transaction(context=_context)
    def test_perm_write_with_rule_fail_before(self):
        "Test write with rule fail before"
        pool = Pool()
        TestRule = pool.get('test.rule')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'name': "Field different from foo",
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

        with self.assertRaisesRegex(AccessError, "Field different from foo"):
            TestRule.write([test], {'field': 'bar'})

    @with_transaction(context=_context)
    def test_perm_write_with_rule_fail_after(self):
        "Test write with rule fail after"
        pool = Pool()
        TestRule = pool.get('test.rule')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'name': "Field different from foo",
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

        with self.assertRaisesRegex(AccessError, "Field different from foo"):
            TestRule.write([test], {'field': 'foo'})

    @with_transaction(context=_context)
    def test_perm_delete_without_rule(self):
        "Test delete without rule"
        pool = Pool()
        TestRule = pool.get('test.rule')

        test, = TestRule.create([{}])

        TestRule.delete([test])

    @with_transaction(context=_context)
    def test_perm_delete_with_rule(self):
        "Test delete with rule"
        pool = Pool()
        TestRule = pool.get('test.rule')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'name': "Field different from foo",
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

    @with_transaction(context=_context)
    def test_perm_delete_with_rule_fail(self):
        "Test delete with rule fail"
        pool = Pool()
        TestRule = pool.get('test.rule')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'name': "Field different from foo",
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

        with self.assertRaisesRegex(AccessError, "Field different from foo"):
            TestRule.delete([test])

    @with_transaction(context=_context)
    def test_perm_read_without_rule(self):
        "Test read without rule"
        pool = Pool()
        TestRule = pool.get('test.rule')

        test, = TestRule.create([{'field': 'foo'}])

        TestRule.read([test.id], ['field'])

    @with_transaction(context=_context)
    def test_perm_read_with_rule(self):
        "Test read with rule"
        pool = Pool()
        TestRule = pool.get('test.rule')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'name': "Field different from foo",
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

        TestRule.read([test.id], ['field'])

    @with_transaction(context=_context)
    def test_perm_read_with_rule_fail(self):
        "Test read with rule fail"
        pool = Pool()
        TestRule = pool.get('test.rule')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'name': "Field different from foo",
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

        with self.assertRaisesRegex(AccessError, "Field different from foo"):
            TestRule.read([test.id], ['field'])

    @with_transaction(context=_context)
    def test_search_without_rule(self):
        "Test search without rule"
        pool = Pool()
        TestRule = pool.get('test.rule')

        test, = TestRule.create([{'field': 'foo'}])

        self.assertListEqual(TestRule.search([]), [test])

    @with_transaction(context=_context)
    def test_search_with_rule(self):
        "Test search with rule"
        pool = Pool()
        TestRule = pool.get('test.rule')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'name': "Field different from foo",
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

    @with_transaction(context=_context)
    def test_search_with_rule_match(self):
        "Test search with rule match"
        pool = Pool()
        TestRule = pool.get('test.rule')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'name': "Field different from foo",
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

    @with_transaction(context=_context)
    def test_write_field_no_rule(self):
        "Test _write field when there's no rule"
        pool = Pool()
        TestRule = pool.get('test.rule')
        writable, = TestRule.create([{'field': 'foo'}])

        value, = TestRule.read([writable.id], ['_write'])
        self.assertEqual(value['_write'], True)

    @with_transaction(context=_context)
    def test_write_field_rule_True(self):
        "Test _write field when there's a rule - True"
        pool = Pool()
        TestRule = pool.get('test.rule')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'name': "Field different from foo",
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
        writable, = TestRule.create([{'field': 'bar'}])

        value, = TestRule.read([writable.id], ['_write'])
        self.assertEqual(value['_write'], True)

    @with_transaction(context=_context)
    def test_write_field_rule_False(self):
        "Test _write field when there's a rule - False"
        pool = Pool()
        TestRule = pool.get('test.rule')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'name': "Field different from foo",
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
        non_writable, = TestRule.create([{'field': 'foo'}])

        value, = TestRule.read([non_writable.id], ['_write'])
        self.assertEqual(value['_write'], False)

    @with_transaction(context=_context)
    def test_write_field_relation_rule_True(self):
        "Test _write field when there's a rule with a relation - True"
        pool = Pool()
        TestRule = pool.get('test.rule')
        TestRuleRelation = pool.get('test.rule.relation')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'name': "Field different from foo",
                    'model': model.id,
                    'global_p': True,
                    'perm_read': False,
                    'perm_create': False,
                    'perm_write': True,
                    'perm_delete': False,
                    'rules': [('create', [{
                                    'domain': json.dumps(
                                        [('relation.field', '!=', 'foo')]),
                                    }])],
                    }])
        relation, = TestRuleRelation.create([{'field': 'bar'}])
        writable, = TestRule.create([{'relation': relation}])

        value, = TestRule.read([writable.id], ['_write'])
        self.assertEqual(value['_write'], True)

    @with_transaction(context=_context)
    def test_write_field_relation_rule_False(self):
        "Test _write field when there's a rule with a relation - False"
        pool = Pool()
        TestRule = pool.get('test.rule')
        TestRuleRelation = pool.get('test.rule.relation')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'name': "Field different from foo",
                    'model': model.id,
                    'global_p': True,
                    'perm_read': False,
                    'perm_create': False,
                    'perm_write': True,
                    'perm_delete': False,
                    'rules': [('create', [{
                                    'domain': json.dumps(
                                        [('relation.field', '!=', 'foo')]),
                                    }])],
                    }])
        relation, = TestRuleRelation.create([{'field': 'foo'}])
        non_writable, = TestRule.create([{'relation': relation}])

        value, = TestRule.read([non_writable.id], ['_write'])
        self.assertEqual(value['_write'], False)

    @with_transaction(context=_context)
    def test_delete_field_no_rule(self):
        "Test _delete field when there's no rule"
        pool = Pool()
        TestRule = pool.get('test.rule')
        deletable, = TestRule.create([{'field': 'foo'}])

        value, = TestRule.read([deletable.id], ['_delete'])
        self.assertEqual(value['_delete'], True)

    @with_transaction(context=_context)
    def test_delete_field_rule_True(self):
        "Test _delete field when there's a rule - True"
        pool = Pool()
        TestRule = pool.get('test.rule')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'name': "Field different from foo",
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
        deletable, = TestRule.create([{'field': 'bar'}])

        value, = TestRule.read([deletable.id], ['_delete'])
        self.assertEqual(value['_delete'], True)

    @with_transaction(context=_context)
    def test_delete_field_rule_False(self):
        "Test _delete field when there's a rule - False"
        pool = Pool()
        TestRule = pool.get('test.rule')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'name': "Field different from foo",
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
        non_deletable, = TestRule.create([{'field': 'foo'}])

        value, = TestRule.read([non_deletable.id], ['_delete'])
        self.assertEqual(value['_delete'], False)

    @with_transaction(context=_context)
    def test_delete_field_relation_rule_True(self):
        "Test _delete field when there's a rule with a relation - True"
        pool = Pool()
        TestRule = pool.get('test.rule')
        TestRuleRelation = pool.get('test.rule.relation')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'name': "Field different from foo",
                    'model': model.id,
                    'global_p': True,
                    'perm_read': False,
                    'perm_create': False,
                    'perm_write': False,
                    'perm_delete': True,
                    'rules': [('create', [{
                                    'domain': json.dumps(
                                        [('relation.field', '!=', 'foo')]),
                                    }])],
                    }])
        relation, = TestRuleRelation.create([{'field': 'bar'}])
        deletable, = TestRule.create([{'relation': relation}])

        value, = TestRule.read([deletable.id], ['_delete'])
        self.assertEqual(value['_delete'], True)

    @with_transaction(context=_context)
    def test_delete_field_relation_rule_False(self):
        "Test _delete field when there's a rule with a relation - False"
        pool = Pool()
        TestRule = pool.get('test.rule')
        TestRuleRelation = pool.get('test.rule.relation')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'name': "Field different from foo",
                    'model': model.id,
                    'global_p': True,
                    'perm_read': False,
                    'perm_create': False,
                    'perm_write': False,
                    'perm_delete': True,
                    'rules': [('create', [{
                                    'domain': json.dumps(
                                        [('relation.field', '!=', 'foo')]),
                                    }])],
                    }])
        relation, = TestRuleRelation.create([{'field': 'foo'}])
        non_deletable, = TestRule.create([{'relation': relation}])

        value, = TestRule.read([non_deletable.id], ['_delete'])
        self.assertEqual(value['_delete'], False)

    @with_transaction(context=_context)
    def test_model_with_rule(self):
        "Test model with rule"
        pool = Pool()
        TestRule = pool.get('test.rule')
        TestRuleModel = pool.get('test.rule.model')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'name': "Field different from foo",
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
        rule, = TestRule.create([{'field': 'bar'}])
        test, = TestRuleModel.create([{'rule': rule.id, 'name': 'foo'}])

        TestRuleModel.read([test.id], ['name'])

    @with_transaction(context=_context)
    def test_model_with_rule_fail(self):
        "Test model with rule fail"
        pool = Pool()
        TestRule = pool.get('test.rule')
        TestRuleModel = pool.get('test.rule.model')
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')

        model, = Model.search([('model', '=', 'test.rule')])
        rule_group, = RuleGroup.create([{
                    'name': "Field different from foo",
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
        rule, = TestRule.create([{'field': 'foo'}])
        test, = TestRuleModel.create([{'rule': rule.id, 'name': 'foo'}])

        with self.assertRaisesRegex(AccessError, "Field different from foo"):
            TestRuleModel.read([test.id], ['name'])


def suite():
    suite_ = unittest.TestSuite()
    suite_.addTests(
        unittest.TestLoader().loadTestsFromTestCase(ModelRuleTestCase))
    return suite_
