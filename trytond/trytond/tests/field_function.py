# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, fields
from trytond.pool import Pool


class FunctionAccessor(ModelSQL):
    "Function Accessor"
    __name__ = 'test.function.accessor'

    target = fields.Many2One('test.function.accessor.target', "Target")
    function = fields.Function(
        fields.Many2One('test.function.accessor.target', "Function"),
        'on_change_with_function')

    @fields.depends('target')
    def on_change_with_function(self, name=None):
        if self.target:
            return self.target.id


class FunctionAccessorTarget(ModelSQL):
    "Function Accessor Target"
    __name__ = 'test.function.accessor.target'


def register(module):
    Pool.register(
        FunctionAccessor,
        FunctionAccessorTarget,
        module=module, type_='model')
