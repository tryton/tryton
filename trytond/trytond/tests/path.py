# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import DeactivableMixin, ModelSQL, fields, tree
from trytond.pool import Pool


class Path(DeactivableMixin, tree(), ModelSQL):
    "Path"
    __name__ = 'test.path'
    name = fields.Char("Name", required=True)
    parent = fields.Many2One('test.path', "Parent", path='path')
    path = fields.Char("Path")
    children = fields.One2Many('test.path', 'parent', "Children")


def register(module):
    Pool.register(
        Path,
        module=module, type_='model')
