# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"Test for Tree"
from sql import Null
from sql.conditionals import Case

from trytond.model import DeactivableMixin, ModelSQL, ModelView, fields, tree
from trytond.pool import Pool


class MPTT(DeactivableMixin, tree(), ModelSQL, ModelView):
    'Modified Preorder Tree Traversal'
    __name__ = 'test.mptt'
    name = fields.Char('Name', required=True)
    parent = fields.Many2One('test.mptt', "Parent", left="left", right="right")
    left = fields.Integer('Left', required=True)
    right = fields.Integer('Right', required=True)
    childs = fields.One2Many('test.mptt', 'parent', 'Children')

    @staticmethod
    def order_sequence(tables):
        table, _ = tables[None]
        return [Case((table.sequence == Null, 0), else_=1), table.sequence]

    @staticmethod
    def default_left():
        return 0

    @staticmethod
    def default_right():
        return 0


def register(module):
    Pool.register(
        MPTT,
        module=module, type_='model')
