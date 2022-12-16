# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields
from trytond.pool import Pool


class TestRule(ModelSQL):
    "Test Rule"
    __name__ = 'test.rule'
    field = fields.Char("Field")
    relation = fields.Many2One('test.rule.relation', "Relation")


class TestRuleRelation(ModelSQL):
    "Test Rule Relation"
    __name__ = 'test.rule.relation'
    field = fields.Char("Field")


class TestRuleModel(ModelSQL):
    "Test Rule from Model"
    __name__ = 'test.rule.model'
    __access__ = 'test.rule'

    name = fields.Char("Name")
    rule = fields.Many2One('test.rule', "Rule")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('rule')


def register(module):
    Pool.register(
        TestRule,
        TestRuleRelation,
        TestRuleModel,
        module=module, type_='model')
