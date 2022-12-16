# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import (ModelSingleton, ModelSQL, UnionMixin, fields,
    sequence_ordered)
from trytond.pool import Pool


class Model(ModelSQL):
    'Model'
    __name__ = 'test.model'
    name = fields.Char('Name')


class ModelParent(Model):
    "Model Parent"
    __name__ = 'test.model_parent'
    name = fields.Char("Name")


class ModelChild(Model):
    "Model Child"
    __name__ = 'test.model_child'
    name = fields.Char("Name")
    parent = fields.Many2One('test.model_parent', "Parent")


class ModelChildChild(Model):
    "Model Child Child"
    __name__ = 'test.model_child_child'
    name = fields.Char("Name")
    parent = fields.Many2One('test.model_child', "Parent")


class Singleton(ModelSingleton, ModelSQL):
    'Singleton'
    __name__ = 'test.singleton'
    name = fields.Char('Name')

    @staticmethod
    def default_name():
        return 'test'


class URLObject(ModelSQL):
    'URLObject'
    __name__ = 'test.urlobject'
    name = fields.Char('Name')


class Model4Union1(ModelSQL):
    'Model for union 1'
    __name__ = 'test.model.union1'
    name = fields.Char('Name')
    optional = fields.Char('Optional')


class Model4Union2(ModelSQL):
    'Model for union 2'
    __name__ = 'test.model.union2'
    name = fields.Char('Name')


class Model4Union3(ModelSQL):
    'Model for union 3'
    __name__ = 'test.model.union3'
    name = fields.Char('Name')


class Model4Union4(ModelSQL):
    'Model for union 4'
    __name__ = 'test.model.union4'
    name = fields.Char('Name')


class Union(UnionMixin, ModelSQL):
    'Union'
    __name__ = 'test.union'
    name = fields.Char('Name')
    optional = fields.Char('Optional')

    @staticmethod
    def union_models():
        return ['test.model.union%s' % i for i in range(1, 4)]


class UnionUnion(UnionMixin, ModelSQL):
    'Union of union'
    __name__ = 'test.union.union'
    name = fields.Char('Name')

    @staticmethod
    def union_models():
        return ['test.union', 'test.model.union4']


class Model4UnionTree1(ModelSQL):
    'Model for union tree 1'
    __name__ = 'test.model.union.tree1'
    name = fields.Char('Name')


class Model4UnionTree2(ModelSQL):
    'Model for union tree 2'
    __name__ = 'test.model.union.tree2'
    name = fields.Char('Name')
    parent = fields.Many2One('test.model.union.tree1', 'Parent')


class UnionTree(UnionMixin, ModelSQL):
    'Union tree'
    __name__ = 'test.union.tree'
    name = fields.Char('Name')
    parent = fields.Many2One('test.union.tree', 'Parent')
    childs = fields.One2Many('test.union.tree', 'parent', 'Childs')

    @staticmethod
    def union_models():
        return ['test.model.union.tree1', 'test.model.union.tree2']


class SequenceOrderedModel(sequence_ordered(), ModelSQL):
    'Sequence Ordered Model'
    __name__ = 'test.order.sequence'


def register(module):
    Pool.register(
        Model,
        ModelParent,
        ModelChild,
        ModelChildChild,
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
