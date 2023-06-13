# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, Unique, fields
from trytond.pool import Pool


class One2One(ModelSQL):
    'One2One'
    __name__ = 'test.one2one'
    one2one = fields.One2One('test.one2one.relation', 'origin', 'target',
            string='One2One', help='Test one2one', required=False)


class One2OneTarget(ModelSQL):
    'One2One Target'
    __name__ = 'test.one2one.target'
    name = fields.Char('Name')


class One2OneRelation(ModelSQL):
    'One2One Relation'
    __name__ = 'test.one2one.relation'
    origin = fields.Many2One('test.one2one', 'Origin')
    target = fields.Many2One('test.one2one.target', 'Target')

    @classmethod
    def __setup__(cls):
        super(One2OneRelation, cls).__setup__()
        table = cls.__table__()
        cls._sql_constraints += [
            ('origin_unique', Unique(table, table.origin),
                'tests.msg_one2one_relation_origin_unique'),
            ('target_unique', Unique(table, table.target),
                'tests.msg_one2one_relation_target_unique'),
            ]


class One2OneRequired(ModelSQL):
    'One2One'
    __name__ = 'test.one2one_required'
    one2one = fields.One2One('test.one2one_required.relation', 'origin',
        'target', string='One2One', help='Test one2one', required=True)


class One2OneRequiredRelation(ModelSQL):
    'One2One Relation'
    __name__ = 'test.one2one_required.relation'
    origin = fields.Many2One('test.one2one_required', 'Origin')
    target = fields.Many2One('test.one2one.target', 'Target')

    @classmethod
    def __setup__(cls):
        super(One2OneRequiredRelation, cls).__setup__()
        table = cls.__table__()
        cls._sql_constraints += [
            ('origin_unique', Unique(table, table.origin),
                'Origin must be unique'),
            ('target_unique', Unique(table, table.target),
                'Target must be unique'),
            ]


class One2OneDomain(ModelSQL):
    'One2One'
    __name__ = 'test.one2one_domain'
    one2one = fields.One2One('test.one2one_domain.relation', 'origin',
        'target', string='One2One', help='Test one2one',
        domain=[('name', '=', 'domain')])


class One2OneDomainRelation(ModelSQL):
    'One2One Relation'
    __name__ = 'test.one2one_domain.relation'
    origin = fields.Many2One('test.one2one_domain', 'Origin')
    target = fields.Many2One('test.one2one.target', 'Target')

    @classmethod
    def __setup__(cls):
        super(One2OneDomainRelation, cls).__setup__()
        table = cls.__table__()
        cls._sql_constraints += [
            ('origin_unique', Unique(table, table.origin),
                'Origin must be unique'),
            ('target_unique', Unique(table, table.target),
                'Target must be unique'),
            ]


def register(module):
    Pool.register(
        One2One,
        One2OneTarget,
        One2OneRelation,
        One2OneRequired,
        One2OneRequiredRelation,
        One2OneDomain,
        One2OneDomainRelation,
        module=module, type_='model')
