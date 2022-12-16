# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, ModelStorage, DeactivableMixin, fields
from trytond.pool import Pool


class Many2OneTarget(DeactivableMixin, ModelSQL):
    "Many2One Domain Validation Target"
    __name__ = 'test.many2one_target'
    _order_name = 'value'

    value = fields.Integer('Value')


class Many2One(ModelSQL):
    "Many2One"
    __name__ = 'test.many2one'
    many2one = fields.Many2One('test.many2one_target', 'many2one')


class Many2OneDomainValidation(ModelSQL):
    "Many2One Domain Validation"
    __name__ = 'test.many2one_domainvalidation'
    many2one = fields.Many2One('test.many2one_target',
        'many2one',
        domain=[
            ('value', '>', 5),
            ])
    dummy = fields.Char('Dummy')


class Many2OneNoForeignKey(ModelSQL):
    "Many2One No Foreign Key"
    __name__ = 'test.many2one_no_foreign_key'
    many2one = fields.Many2One('test.many2one_target_storage', 'many2one')


class Many2OneTargetStorage(ModelStorage):
    "Many2One Target Storage"
    __name__ = 'test.many2one_target_storage'


class Many2OneTree(ModelSQL):
    'Many2One Tree'
    __name__ = 'test.many2one_tree'
    many2one = fields.Many2One('test.many2one_tree', 'many2one')


class Many2OneMPTT(ModelSQL):
    'Many2One MPTT'
    __name__ = 'test.many2one_mptt'
    many2one = fields.Many2One('test.many2one_mptt', 'many2one',
        left='left', right='right')
    left = fields.Integer('Left', required=True)
    right = fields.Integer('Right', required=True)

    @classmethod
    def default_left(cls):
        return 0

    @classmethod
    def default_right(cls):
        return 0


def register(module):
    Pool.register(
        Many2OneTarget,
        Many2One,
        Many2OneDomainValidation,
        Many2OneNoForeignKey,
        Many2OneTargetStorage,
        Many2OneTree,
        Many2OneMPTT,
        module=module, type_='model')
