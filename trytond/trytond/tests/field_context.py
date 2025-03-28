# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, fields
from trytond.pool import Pool
from trytond.pyson import Eval


class FieldContextParent(ModelSQL):
    __name__ = 'test.field_context.parent'
    name = fields.Char('Name')
    child = fields.Many2One('test.field_context.child', 'Child',
        context={
            'name': Eval('name'),
            'rec_name': Eval('rec_name'),
            },
        depends=['name'])


class FieldContextChild(ModelSQL):
    __name__ = 'test.field_context.child'


def register(module):
    Pool.register(
        FieldContextParent,
        FieldContextChild,
        module=module, type_='model')
