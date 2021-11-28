# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, fields
from trytond.pool import Pool
from trytond.transaction import Transaction


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


class FunctionGetterContext(ModelSQL):
    "Function Getter Context"
    __name__ = 'test.function.getter_context'

    function_with_context = fields.Function(
        fields.Char("Function"),
        'getter', getter_with_context=True)
    function_without_context = fields.Function(
        fields.Char("Function"),
        'getter', getter_with_context=False)

    def getter(self, name):
        context = Transaction().context
        return '%s - %s' % (
            context.get('language', 'empty'), context.get('test', 'empty'))


def register(module):
    Pool.register(
        FunctionAccessor,
        FunctionAccessorTarget,
        FunctionGetterContext,
        module=module, type_='model')
