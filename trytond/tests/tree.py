# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, tree, fields
from trytond.pool import Pool


class Tree(tree(separator=' / '), ModelSQL):
    "Tree"
    __name__ = 'test.tree'
    name = fields.Char("Name")
    parent = fields.Many2One('test.tree', "Parent")


class Polytree(tree(parent='parents'), ModelSQL):
    "PolyTree"
    __name__ = 'test.polytree'
    name = fields.Char("Name")
    parents = fields.Many2Many(
        'test.polytree.edge', 'parent', 'child', "Parents")


class PolytreeEdge(ModelSQL):
    "Polytree Edge"
    __name__ = 'test.polytree.edge'
    parent = fields.Many2One('test.polytree', "Parent")
    child = fields.Many2One('test.polytree', "Child")


def register(module):
    Pool.register(
        Tree,
        Polytree,
        PolytreeEdge,
        module=module, type_='model')
