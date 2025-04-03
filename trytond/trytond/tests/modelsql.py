# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Literal
from sql.operators import Equal

from trytond.model import (
    Check, DeactivableMixin, Exclude, ModelSQL, Unique, fields)
from trytond.pool import Pool
from trytond.pyson import Eval


class ModelSQLRead(ModelSQL):
    __name__ = 'test.modelsql.read'
    name = fields.Char("Name")
    target = fields.Many2One('test.modelsql.read.target', "Target")
    targets = fields.One2Many('test.modelsql.read.target', 'parent', "Targets")
    reference = fields.Reference(
        "Reference", [(None, ""), ('test.modelsql.read.target', "Target")])


class ModelSQLReadTarget(ModelSQL):
    __name__ = 'test.modelsql.read.target'
    name = fields.Char("Name")
    parent = fields.Many2One('test.modelsql.read', "Parent")
    target = fields.Many2One('test.modelsql.read.target', "Target")


class ModelSQLReadContextID(ModelSQL):
    __name__ = 'test.modelsql.read.context_id'
    name = fields.Char("Name", context={
            'test': Eval('id'),
            })


class ModelSQLReadLimit(ModelSQL):
    __name__ = 'test.modelsql.read.limit'
    name = fields.Char("Name")
    targets = fields.One2Many(
        'test.modelsql.read.limit.target', 'parent', "Targets")
    sum_targets = fields.Function(
        fields.Integer("Sum of Targets"), 'on_change_with_sum_targets')

    @fields.depends('targets')
    def on_change_with_sum_targets(self, name=None):
        return sum(t.integer for t in self.targets)


class ModelSQLReadLimitTarget(ModelSQL):
    __name__ = 'test.modelsql.read.limit.target'
    name = fields.Char("Name")
    integer = fields.Integer("Integer")
    parent = fields.Many2One('test.modelsql.read.limit', "Parent")


class ModelSQLRequiredField(ModelSQL):
    __name__ = 'test.modelsql'

    integer = fields.Integer(string="integer", required=True)
    desc = fields.Char(string="desc", required=True)


class ModelSQLTimestamp(ModelSQL):
    __name__ = 'test.modelsql.timestamp'


class ModelSQLCreate(ModelSQL):
    __name__ = 'test.modelsql.create'

    char = fields.Char("Char")
    integer = fields.Integer("Integer")


class ModelSQLWrite(ModelSQL):
    __name__ = 'test.modelsql.write'
    name = fields.Char("Name")


class ModelSQLDelete(ModelSQL):
    __name__ = 'test.modelsql.delete'
    name = fields.Char("Name")


class ModelSQLFieldSet(ModelSQL):
    __name__ = 'test.modelsql.field_set'

    field = fields.Function(fields.Integer('Field'),
        'get_field', setter='set_field')

    def get_field(self, name=None):
        return

    @classmethod
    def set_field(cls, records, name, value):
        pass


class ModelSQLOne2Many(ModelSQL):
    __name__ = 'test.modelsql.one2many'
    targets = fields.One2Many(
        'test.modelsql.one2many.target', 'origin', "Targets")


class ModelSQLOne2ManyTarget(ModelSQL):
    __name__ = 'test.modelsql.one2many.target'
    name = fields.Char("Name", required=True)
    origin = fields.Many2One('test.modelsql.one2many', "Origin")


class ModelSQLSearch(ModelSQL):
    __name__ = 'test.modelsql.search'
    name = fields.Char("Name")


class ModelSQLSearchOR2Union(ModelSQL):
    __name__ = 'test.modelsql.search.or2union'
    name = fields.Char("Name")
    target = fields.Many2One('test.modelsql.search.or2union.target', "Target")
    targets = fields.One2Many(
        'test.modelsql.search.or2union.target', 'parent', "Targets")
    reference = fields.Reference(
        "Reference",
        [
            (None, ""),
            ('test.modelsql.search.or2union.target', "Target"),
            ])
    integer = fields.Integer("Integer")

    @classmethod
    def order_integer(cls, tables):
        pool = Pool()
        Target = pool.get('test.modelsql.search.or2union.target')
        target = Target.__table__()

        table, _ = tables[None]
        tables['target'] = {
            None: (target, (target.id == table.target)),
            }
        return [table.integer + target.id]

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            ('name',) + clause[1:],
            ('targets.name',) + clause[1:],
            ]


class ModelSQLSearchOR2UnionTarget(ModelSQL):
    __name__ = 'test.modelsql.search.or2union.target'
    name = fields.Char("Name")
    parent = fields.Many2One('test.modelsql.search.or2union', "Parent")


class ModelSQLSearchOR2UnionOrder(ModelSQL):
    __name__ = 'test.modelsql.search.or2union.class_order'
    name = fields.Char("Name")
    reference = fields.Reference("Reference", [
            (None, ''),
            ('test.modelsql.search.or2union.class_order.target', "Target"),
            ])
    targets = fields.One2Many(
        'test.modelsql.search.or2union.class_order.target', 'parent',
        "Targets")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order = [('reference', 'DESC')]


class ModelSQLSearchOR2UnionOrderTarget(ModelSQL):
    __name__ = 'test.modelsql.search.or2union.class_order.target'
    name = fields.Char("Name")
    parent = fields.Many2One(
        'test.modelsql.search.or2union.class_order', "Parent")


class ModelSQLForeignKey(DeactivableMixin, ModelSQL):
    __name__ = 'test.modelsql.fk'

    target_cascade = fields.Many2One(
        'test.modelsql.fk.target', "Target", ondelete='CASCADE')
    target_null = fields.Many2One(
        'test.modelsql.fk.target', "Target", ondelete='SET NULL')
    target_restrict = fields.Many2One(
        'test.modelsql.fk.target', "Target", ondelete='RESTRICT')


class ModelSQLForeignKeyTarget(ModelSQL):
    __name__ = 'test.modelsql.fk.target'


class ModelSQLForeignKeyTree(ModelSQL):
    __name__ = 'test.modelsql.fk.tree'

    parent_cascade = fields.Many2One(
        'test.modelsql.fk.tree', "Parent", ondelete='CASCADE')
    parent_null = fields.Many2One(
        'test.modelsql.fk.tree', "Parent", ondelete='SET NULL')
    parent_restrict = fields.Many2One(
        'test.modelsql.fk.tree', "Parent", ondelete='RESTRICT')


class NullOrder(ModelSQL):
    __name__ = 'test.modelsql.null_order'
    integer = fields.Integer('Integer')


class ModelTranslation(ModelSQL):
    __name__ = 'test.modelsql.translation'
    name = fields.Char("Name", translate=True)


class ModelTranslationName(ModelSQL):
    __name__ = 'test.modelsql.name_translated'

    name = fields.Char("Name", translate=True, help="Name help")


class ModelCheck(ModelSQL):
    __name__ = 'test.modelsql.check'
    value = fields.Integer("Value")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('check', Check(t, (t.value > 42)), 'tests.msg_modelsql_check'),
            ]


class ModelUnique(ModelSQL):
    __name__ = 'test.modelsql.unique'
    value = fields.Integer("Value")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('unique', Unique(t, t.value), 'tests.msg_modelsql_unique'),
            ]


class ModelExclude(ModelSQL):
    __name__ = 'test.modelsql.exclude'
    value = fields.Integer("Value")
    condition = fields.Boolean("Condition")

    @classmethod
    def default_condition(cls):
        return True

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('exclude', Exclude(t, (t.value, Equal),
                    where=t.condition == Literal(True)),
                'tests.msg_modelsql_exclude'),
            ]


class ModelLock(ModelSQL):
    __name__ = 'test.modelsql.lock'


def register(module):
    Pool.register(
        ModelSQLRead,
        ModelSQLReadTarget,
        ModelSQLReadContextID,
        ModelSQLReadLimit,
        ModelSQLReadLimitTarget,
        ModelSQLRequiredField,
        ModelSQLTimestamp,
        ModelSQLCreate,
        ModelSQLWrite,
        ModelSQLDelete,
        ModelSQLFieldSet,
        ModelSQLOne2Many,
        ModelSQLOne2ManyTarget,
        ModelSQLSearch,
        ModelSQLSearchOR2Union,
        ModelSQLSearchOR2UnionTarget,
        ModelSQLSearchOR2UnionOrder,
        ModelSQLSearchOR2UnionOrderTarget,
        ModelSQLForeignKey,
        ModelSQLForeignKeyTarget,
        ModelSQLForeignKeyTree,
        NullOrder,
        ModelTranslation,
        ModelTranslationName,
        ModelCheck,
        ModelUnique,
        ModelExclude,
        ModelLock,
        module=module, type_='model')
