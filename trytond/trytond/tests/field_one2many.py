# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, fields
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction


class One2Many(ModelSQL):
    __name__ = 'test.one2many'
    targets = fields.One2Many('test.one2many.target', 'origin', 'Targets')


class One2ManyTarget(ModelSQL):
    __name__ = 'test.one2many.target'
    name = fields.Char('Name')
    origin = fields.Many2One('test.one2many', 'Origin')


class One2ManyRequired(ModelSQL):
    __name__ = 'test.one2many_required'
    targets = fields.One2Many('test.one2many_required.target', 'origin',
        'Targets', required=True)


class One2ManyRequiredTarget(ModelSQL):
    __name__ = 'test.one2many_required.target'
    name = fields.Char('Name')
    origin = fields.Many2One('test.one2many_required', 'Origin')


class One2ManyReference(ModelSQL):
    __name__ = 'test.one2many_reference'
    targets = fields.One2Many('test.one2many_reference.target', 'origin',
        'Targets')


class One2ManyReferenceTarget(ModelSQL):
    __name__ = 'test.one2many_reference.target'
    name = fields.Char('Name')
    origin = fields.Reference('Origin', [
            (None, ''),
            ('test.one2many_reference', 'One2Many Reference'),
            ])


class One2ManySize(ModelSQL):
    __name__ = 'test.one2many_size'
    targets = fields.One2Many('test.one2many_size.target', 'origin', 'Targets',
        size=3)


class One2ManySizeTarget(ModelSQL):
    __name__ = 'test.one2many_size.target'
    origin = fields.Many2One('test.one2many_size', 'Origin')


class One2ManySizePYSON(ModelSQL):
    __name__ = 'test.one2many_size_pyson'
    limit = fields.Integer('Limit')
    targets = fields.One2Many('test.one2many_size_pyson.target', 'origin',
        'Targets', size=Eval('limit', 0))


class One2ManySizePYSONTarget(ModelSQL):
    __name__ = 'test.one2many_size_pyson.target'
    origin = fields.Many2One('test.one2many_size_pyson', 'Origin')


class One2ManyDomain(ModelSQL):
    __name__ = 'test.one2many_domain'
    targets = fields.One2Many(
        'test.one2many_domain.target', 'origin', "Targets",
        domain=[
            ('value', '=', 42),
            ])


class One2ManyDomainTarget(ModelSQL):
    __name__ = 'test.one2many_domain.target'
    origin = fields.Many2One('test.one2many_domain', "Origin")
    value = fields.Integer("Value")


class One2ManyFilter(ModelSQL):
    __name__ = 'test.one2many_filter'
    targets = fields.One2Many('test.one2many_filter.target', 'origin',
        'Targets')
    filtered_targets = fields.One2Many('test.one2many_filter.target', 'origin',
        'Filtered Targets', filter=[('value', '>', 2)])


class One2ManyFilterTarget(ModelSQL):
    __name__ = 'test.one2many_filter.target'
    origin = fields.Many2One('test.one2many_filter', 'Origin')
    value = fields.Integer('Value')


class One2ManyFilterDomain(ModelSQL):
    __name__ = 'test.one2many_filter_domain'
    targets = fields.One2Many('test.one2many_filter_domain.target', 'origin',
        'Targets', domain=[('value', '<', 10)])
    filtered_targets = fields.One2Many('test.one2many_filter_domain.target',
        'origin', 'Filtered Targets', domain=[('value', '<', 10)],
        filter=[('value', '>', 2)])


class One2ManyFilterDomainTarget(ModelSQL):
    __name__ = 'test.one2many_filter_domain.target'
    origin = fields.Many2One('test.one2many_filter_domain', 'Origin')
    value = fields.Integer('Value')


class One2ManyContext(ModelSQL):
    __name__ = 'test.one2many_context'
    targets = fields.One2Many(
        'test.one2many_context.target', 'origin', "Targets",
        context={'test': Eval('id')})


class One2ManyContextTarget(ModelSQL):
    __name__ = 'test.one2many_context.target'
    origin = fields.Many2One('test.one2many_context', "Origin")
    context = fields.Function(fields.Integer("context"), 'get_context')

    def get_context(self, name):
        context = Transaction().context
        return context.get('test')


class One2ManyOrder(ModelSQL):
    __name__ = 'test.one2many_order'
    targets = fields.One2Many(
        'test.one2many_order.target', 'origin', "Targets")
    reversed_targets = fields.One2Many(
        'test.one2many_order.target', 'origin', "Reversed Targets",
        order=[('id', 'ASC')])


class One2ManyOrderTarget(ModelSQL):
    __name__ = 'test.one2many_order.target'
    origin = fields.Many2One('test.one2many_order', "Origin")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order = [('id', 'DESC')]


def register(module):
    Pool.register(
        One2Many,
        One2ManyTarget,
        One2ManyRequired,
        One2ManyRequiredTarget,
        One2ManyReference,
        One2ManyReferenceTarget,
        One2ManySize,
        One2ManySizeTarget,
        One2ManySizePYSON,
        One2ManySizePYSONTarget,
        One2ManyDomain,
        One2ManyDomainTarget,
        One2ManyFilter,
        One2ManyFilterTarget,
        One2ManyFilterDomain,
        One2ManyFilterDomainTarget,
        One2ManyContext,
        One2ManyContextTarget,
        One2ManyOrder,
        One2ManyOrderTarget,
        module=module, type_='model')
