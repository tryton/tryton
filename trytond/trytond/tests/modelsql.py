# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Literal
from sql.operators import Equal

from trytond.model import (
    Check, DeactivableMixin, Exclude, ModelSQL, Unique, fields)
from trytond.pool import Pool
from trytond.pyson import Eval


class ModelSQLRead(ModelSQL):
    "ModelSQL to test read"
    __name__ = 'test.modelsql.read'
    name = fields.Char("Name")
    target = fields.Many2One('test.modelsql.read.target', "Target")
    targets = fields.One2Many('test.modelsql.read.target', 'parent', "Targets")
    reference = fields.Reference(
        "Reference", [(None, ""), ('test.modelsql.read.target', "Target")])


class ModelSQLReadTarget(ModelSQL):
    "ModelSQL Target to test read"
    __name__ = 'test.modelsql.read.target'
    name = fields.Char("Name")
    parent = fields.Many2One('test.modelsql.read', "Parent")
    target = fields.Many2One('test.modelsql.read.target', "Target")


class ModelSQLReadContextID(ModelSQL):
    "ModelSQL to test read with ID in context"
    __name__ = 'test.modelsql.read.context_id'
    name = fields.Char("Name", context={
            'test': Eval('id'),
            })


class ModelSQLReadLimit(ModelSQL):
    "ModelSQL to test related limit"
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
    "ModelSQL to test related limit"
    __name__ = 'test.modelsql.read.limit.target'
    name = fields.Char("Name")
    integer = fields.Integer("Integer")
    parent = fields.Many2One('test.modelsql.read.limit', "Parent")


class ModelSQLRequiredField(ModelSQL):
    'model with a required field'
    __name__ = 'test.modelsql'

    integer = fields.Integer(string="integer", required=True)
    desc = fields.Char(string="desc", required=True)


class ModelSQLTimestamp(ModelSQL):
    'Model to test timestamp'
    __name__ = 'test.modelsql.timestamp'


class ModelSQLCreate(ModelSQL):
    "Model to test creation"
    __name__ = 'test.modelsql.create'

    char = fields.Char("Char")
    integer = fields.Integer("Integer")


class ModelSQLWrite(ModelSQL):
    "ModelSQL to test write"
    __name__ = 'test.modelsql.write'
    name = fields.Char("Name")


class ModelSQLDelete(ModelSQL):
    "ModelSQL to test delete"
    __name__ = 'test.modelsql.delete'
    name = fields.Char("Name")


class ModelSQLFieldSet(ModelSQL):
    'Model to test field set'
    __name__ = 'test.modelsql.field_set'

    field = fields.Function(fields.Integer('Field'),
        'get_field', setter='set_field')

    def get_field(self, name=None):
        return

    @classmethod
    def set_field(cls, records, name, value):
        pass


class ModelSQLOne2Many(ModelSQL):
    "ModelSQL One2Many"
    __name__ = 'test.modelsql.one2many'
    targets = fields.One2Many(
        'test.modelsql.one2many.target', 'origin', "Targets")


class ModelSQLOne2ManyTarget(ModelSQL):
    "ModelSQL One2Many Target"
    __name__ = 'test.modelsql.one2many.target'
    name = fields.Char("Name", required=True)
    origin = fields.Many2One('test.modelsql.one2many', "Origin")


class ModelSQLSearch(ModelSQL):
    "ModelSQL Search"
    __name__ = 'test.modelsql.search'
    name = fields.Char("Name")


class ModelSQLSearchOR2Union(ModelSQL):
    "ModelSQL Search OR to UNION optimization"
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
        table, _ = tables[None]
        return [table.integer + 1]


class ModelSQLSearchOR2UnionTarget(ModelSQL):
    "ModelSQL Target to test read"
    __name__ = 'test.modelsql.search.or2union.target'
    name = fields.Char("Name")
    parent = fields.Many2One('test.modelsql.search.or2union', "Parent")


class ModelSQLSearchOR2UnionOrder(ModelSQL):
    "ModelSQL Search OR to UNION optimization with class order"
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
    "ModelSQL Target to test read"
    __name__ = 'test.modelsql.search.or2union.class_order.target'
    name = fields.Char("Name")
    parent = fields.Many2One(
        'test.modelsql.search.or2union.class_order', "Parent")


class ModelSQLForeignKey(DeactivableMixin, ModelSQL):
    "ModelSQL Foreign Key"
    __name__ = 'test.modelsql.fk'

    target_cascade = fields.Many2One(
        'test.modelsql.fk.target', "Target", ondelete='CASCADE')
    target_null = fields.Many2One(
        'test.modelsql.fk.target', "Target", ondelete='SET NULL')
    target_restrict = fields.Many2One(
        'test.modelsql.fk.target', "Target", ondelete='RESTRICT')


class ModelSQLForeignKeyTarget(ModelSQL):
    "ModelSQL Foreign Key Target"
    __name__ = 'test.modelsql.fk.target'


class ModelSQLForeignKeyTree(ModelSQL):
    "ModelSQL Foreign Key Tree"
    __name__ = 'test.modelsql.fk.tree'

    parent_cascade = fields.Many2One(
        'test.modelsql.fk.tree', "Parent", ondelete='CASCADE')
    parent_null = fields.Many2One(
        'test.modelsql.fk.tree', "Parent", ondelete='SET NULL')
    parent_restrict = fields.Many2One(
        'test.modelsql.fk.tree', "Parent", ondelete='RESTRICT')


class NullOrder(ModelSQL):
    "Null Order"
    __name__ = 'test.modelsql.null_order'
    integer = fields.Integer('Integer')


class ModelTranslation(ModelSQL):
    "ModelSQL with translated field"
    __name__ = 'test.modelsql.translation'
    name = fields.Char("Name", translate=True)


class ModelCheck(ModelSQL):
    "ModelSQL with check constraint"
    __name__ = 'test.modelsql.check'
    value = fields.Integer("Value")

    @classmethod
    def __setup__(cls):
        super(ModelCheck, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('check', Check(t, (t.value > 42)), 'tests.msg_modelsql_check'),
            ]


class ModelUnique(ModelSQL):
    "ModelSQL with unique constraint"
    __name__ = 'test.modelsql.unique'
    value = fields.Integer("Value")

    @classmethod
    def __setup__(cls):
        super(ModelUnique, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('unique', Unique(t, t.value), 'tests.msg_modelsql_unique'),
            ]


class ModelExclude(ModelSQL):
    "ModelSQL with exclude constraint"
    __name__ = 'test.modelsql.exclude'
    value = fields.Integer("Value")
    condition = fields.Boolean("Condition")

    @classmethod
    def default_condition(cls):
        return True

    @classmethod
    def __setup__(cls):
        super(ModelExclude, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('exclude', Exclude(t, (t.value, Equal),
                    where=t.condition == Literal(True)),
                'tests.msg_modelsql_exclude'),
            ]


class ModelLock(ModelSQL):
    'Model to test lock'
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
        ModelCheck,
        ModelUnique,
        ModelExclude,
        ModelLock,
        module=module, type_='model')
