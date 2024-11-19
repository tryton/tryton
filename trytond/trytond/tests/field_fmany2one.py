# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, Unique, fields
from trytond.pool import Pool


class FMany2OneTarget(ModelSQL):
    __name__ = 'test.fmany2one_target'

    name = fields.Char("Name")
    children = fields.One2Many(
        'test.fmany2one_target.child', 'parent', "Children")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        table = cls.__table__()
        cls._sql_constraints += [
            ('name_unique', Unique(table, table.name),
                "The name must be unique."),
            ]


class FMany2OneTargetChild(
        fields.fmany2one(
            'parent', 'parent_name', 'test.fmany2one_target,name', "Parent"),
        ModelSQL):
    __name__ = 'test.fmany2one_target.child'

    name = fields.Char("Name")
    parent_name = fields.Char("Parent Name")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        table = cls.__table__()
        cls._sql_constraints += [
            ('name_parent_unique',
                Unique(table, table.name, table.parent_name),
                "The name and parent must be unique."),
            ]


class FMany2One(
        fields.fmany2one(
            'target', 'target_name', 'test.fmany2one_target,name', "Target"),
        fields.fmany2one(
            'child', 'child_name,target_name',
            'test.fmany2one_target.child,name,parent_name', "Child"),
        ModelSQL):
    __name__ = 'test.fmany2one'

    target_name = fields.Char("Target Name")
    child_name = fields.Char("Child Name")


class FMany2OneRequired(
        fields.fmany2one(
            'target', 'target_name', 'test.fmany2one_target,name', "Target",
            required=True),
        ModelSQL):
    __name__ = 'test.fmany2one_required'

    target_name = fields.Char("Target Name", required=True)


def register(module):
    Pool.register(
        FMany2OneTarget,
        FMany2OneTargetChild,
        FMany2One,
        FMany2OneRequired,
        module=module, type_='model')
