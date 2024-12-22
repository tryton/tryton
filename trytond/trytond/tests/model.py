# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import (
    ModelSingleton, ModelSQL, UnionMixin, fields, sequence_ordered)
from trytond.pool import Pool
from trytond.pyson import Eval


class Model(ModelSQL):
    __name__ = 'test.model'
    name = fields.Char('Name')
    selection = fields.Selection([
            ('foo', "Foo"),
            ('bar', "Bar"),
            (None, ""),
            ], "Selection")
    multiselection = fields.MultiSelection([
            ('foo', "Foo"),
            ('bar', "Bar"),
            ], "MultiSelection")


class ModelParent(Model):
    __name__ = 'test.model_parent'
    __string__ = None
    name = fields.Char("Name")
    children = fields.One2Many('test.model_child', 'parent', "Children")


class ModelChild(Model):
    __name__ = 'test.model_child'
    __string__ = None
    name = fields.Char("Name")
    parent = fields.Many2One('test.model_parent', "Parent")


class ModelChildChild(Model):
    __string__ = None
    __name__ = 'test.model_child_child'
    name = fields.Char("Name")
    parent = fields.Many2One('test.model_child', "Parent")


class ModelContext(Model):
    __name__ = 'test.model_context'
    __string__ = None
    name = fields.Char("Name")
    target = fields.Many2One(
        'test.model', "Target",
        context={
            'name': Eval('name'),
            })


class ModelContextParent(Model):
    __name__ = 'test.model_context_parent'
    __string__ = None
    parent = fields.Many2One('test.model', "Parent")
    target = fields.Many2One(
        'test.model', "Target",
        context={
            'name': Eval('_parent_parent', {}).get('name'),
            })


class ModelDefault(Model):
    __name__ = 'test.model.default'

    name = fields.Char("Name")
    description = fields.Char("Description")
    target = fields.Many2One('test.model', "Target")
    reference = fields.Reference("Reference", [
            ('test.model', "Model"),
            ])

    @classmethod
    def default_description(cls):
        return "Test"


class Singleton(ModelSingleton, ModelSQL):
    __name__ = 'test.singleton'
    name = fields.Char('Name')

    @staticmethod
    def default_name():
        return 'test'


class URLObject(ModelSQL):
    __name__ = 'test.urlobject'
    name = fields.Char('Name')


class Model4Union1(ModelSQL):
    __name__ = 'test.model.union1'
    name = fields.Char('Name')
    optional = fields.Char('Optional')


class Model4Union2(ModelSQL):
    __name__ = 'test.model.union2'
    name = fields.Char('Name')


class Model4Union3(ModelSQL):
    __name__ = 'test.model.union3'
    name = fields.Char('Name')


class Model4Union4(ModelSQL):
    __name__ = 'test.model.union4'
    name = fields.Char('Name')


class Union(UnionMixin, ModelSQL):
    __name__ = 'test.union'
    name = fields.Char('Name')
    optional = fields.Char('Optional')

    @staticmethod
    def union_models():
        return ['test.model.union%s' % i for i in range(1, 4)]


class UnionUnion(UnionMixin, ModelSQL):
    __name__ = 'test.union.union'
    name = fields.Char('Name')

    @staticmethod
    def union_models():
        return ['test.union', 'test.model.union4']


class Model4UnionTree1(ModelSQL):
    __name__ = 'test.model.union.tree1'
    name = fields.Char('Name')


class Model4UnionTree2(ModelSQL):
    __name__ = 'test.model.union.tree2'
    name = fields.Char('Name')
    parent = fields.Many2One('test.model.union.tree1', 'Parent')


class UnionTree(UnionMixin, ModelSQL):
    __name__ = 'test.union.tree'
    name = fields.Char('Name')
    parent = fields.Many2One('test.union.tree', 'Parent')
    childs = fields.One2Many('test.union.tree', 'parent', 'Childs')

    @staticmethod
    def union_models():
        return ['test.model.union.tree1', 'test.model.union.tree2']


class SequenceOrderedModel(sequence_ordered(), ModelSQL):
    __name__ = 'test.order.sequence'


def register(module):
    Pool.register(
        Model,
        ModelParent,
        ModelChild,
        ModelChildChild,
        ModelContext,
        ModelContextParent,
        ModelDefault,
        Singleton,
        URLObject,
        Model4Union1,
        Model4Union2,
        Model4Union3,
        Model4Union4,
        Union,
        UnionUnion,
        Model4UnionTree1,
        Model4UnionTree2,
        UnionTree,
        SequenceOrderedModel,
        module=module, type_='model')
