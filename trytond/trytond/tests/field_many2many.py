# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, fields
from trytond.pool import Pool
from trytond.transaction import Transaction


class Many2Many(ModelSQL):
    __name__ = 'test.many2many'
    targets = fields.Many2Many('test.many2many.relation', 'origin', 'target',
        'Targets')


class Many2ManyTarget(ModelSQL):
    __name__ = 'test.many2many.target'
    name = fields.Char('Name')


class Many2ManyRelation(ModelSQL):
    __name__ = 'test.many2many.relation'
    origin = fields.Many2One('test.many2many', 'Origin')
    target = fields.Many2One('test.many2many.target', 'Target')


class Many2ManyRequired(ModelSQL):
    __name__ = 'test.many2many_required'
    targets = fields.Many2Many('test.many2many_required.relation', 'origin',
        'target', 'Targets', required=True)


class Many2ManyRequiredTarget(ModelSQL):
    __name__ = 'test.many2many_required.target'
    name = fields.Char('Name')


class Many2ManyRequiredRelation(ModelSQL):
    __name__ = 'test.many2many_required.relation'
    origin = fields.Many2One('test.many2many_required', 'Origin')
    target = fields.Many2One('test.many2many_required.target', 'Target')


class Many2ManyReference(ModelSQL):
    __name__ = 'test.many2many_reference'
    targets = fields.Many2Many('test.many2many_reference.relation', 'origin',
        'target', 'Targets')


class Many2ManyReferenceTarget(ModelSQL):
    __name__ = 'test.many2many_reference.target'
    name = fields.Char('Name')


class Many2ManyReferenceRelation(ModelSQL):
    __name__ = 'test.many2many_reference.relation'
    origin = fields.Reference('Origin', [
            (None, ''),
            ('test.many2many_reference', 'Many2Many Reference'),
            ])
    target = fields.Many2One('test.many2many_reference.target',
        'Reference Target')


class Many2ManySize(ModelSQL):
    __name__ = 'test.many2many_size'
    targets = fields.Many2Many('test.many2many_size.relation', 'origin',
        'target', 'Targets', size=3)


class Many2ManySizeTarget(ModelSQL):
    __name__ = 'test.many2many_size.target'
    name = fields.Char('Name')


class Many2ManySizeRelation(ModelSQL):
    __name__ = 'test.many2many_size.relation'
    origin = fields.Many2One('test.many2many_size', 'Origin')
    target = fields.Many2One('test.many2many_size.target', 'Target')


class Many2ManyDomain(ModelSQL):
    __name__ = 'test.many2many_domain'
    targets = fields.Many2Many(
        'test.many2many_domain.relation', 'origin', 'target', "Targets",
        domain=[
            ('value', '=', 42),
            ])


class Many2ManyDomainTarget(ModelSQL):
    __name__ = 'test.many2many_domain.target'
    value = fields.Integer("Value")


class Many2ManyDomainRelation(ModelSQL):
    __name__ = 'test.many2many_domain.relation'
    origin = fields.Many2One('test.many2many_domain', "Origin")
    target = fields.Many2One('test.many2many_domain.target', "Target")


class Many2ManyFilter(ModelSQL):
    __name__ = 'test.many2many_filter'
    targets = fields.Many2Many('test.many2many_filter.relation', 'origin',
        'target', 'Targets')
    filtered_targets = fields.Many2Many('test.many2many_filter.relation',
        'origin', 'target', 'Targets',
        filter=[('value', '>', 2)])
    or_filtered_targets = fields.Many2Many('test.many2many_filter.relation',
        'origin', 'target', 'Targets',
        filter=['OR', ('value', '>', 2), ('value', '<', 0)])


class Many2ManyFilterTarget(ModelSQL):
    __name__ = 'test.many2many_filter.target'
    value = fields.Integer('Value')


class Many2ManyFilterRelation(ModelSQL):
    __name__ = 'test.many2many_filter.relation'
    origin = fields.Many2One('test.many2many_filter', 'Origin')
    target = fields.Many2One('test.many2many_filter.target', 'Target')


class Many2ManyFilterDomain(ModelSQL):
    __name__ = 'test.many2many_filter_domain'
    targets = fields.Many2Many('test.many2many_filter_domain.relation',
        'origin', 'target', 'Targets', domain=[('value', '<', 10)])
    filtered_targets = fields.Many2Many(
        'test.many2many_filter_domain.relation', 'origin', 'target', 'Targets',
        domain=[('value', '<', 10)], filter=[('value', '>', 2)])


class Many2ManyFilterDomainTarget(ModelSQL):
    __name__ = 'test.many2many_filter_domain.target'
    value = fields.Integer('Value')


class Many2ManyFilterDomainRelation(ModelSQL):
    __name__ = 'test.many2many_filter_domain.relation'
    origin = fields.Many2One('test.many2many_filter_domain', 'Origin')
    target = fields.Many2One('test.many2many_filter.target', 'Target')


class Many2ManyTree(ModelSQL):
    __name__ = 'test.many2many_tree'
    parents = fields.Many2Many('test.many2many_tree.relation',
        'child', 'parent', 'Parents')
    children = fields.Many2Many('test.many2many_tree.relation',
        'parent', 'child', 'Children')


class Many2ManyTreeRelation(ModelSQL):
    __name__ = 'test.many2many_tree.relation'
    parent = fields.Many2One('test.many2many_tree', 'Parent')
    child = fields.Many2One('test.many2many_tree', 'Child')


class Many2ManyContext(ModelSQL):
    __name__ = 'test.many2many_context'
    targets = fields.Many2Many(
        'test.many2many_context.relation', 'origin', 'target', "Targets",
        context={'test': 'foo'})


class Many2ManyContextRelation(ModelSQL):
    __name__ = 'test.many2many_context.relation'
    origin = fields.Many2One('test.many2many_context', "Origin")
    target = fields.Many2One('test.many2many_context.target', "Target")


class Many2ManyContextTarget(ModelSQL):
    __name__ = 'test.many2many_context.target'
    context = fields.Function(fields.Char("context"), 'get_context')

    def get_context(self, name):
        context = Transaction().context
        return context.get('test')


class Many2ManyOrder(ModelSQL):
    __name__ = 'test.many2many_order'
    targets = fields.Many2Many(
        'test.many2many_order.relation', 'origin', 'target', "Targets")
    reversed_targets = fields.Many2Many(
        'test.many2many_order.relation', 'origin', 'target',
        "Reversed Targets",
        order=[('target', 'DESC')])


class Many2ManyOrderRelation(ModelSQL):
    __name__ = 'test.many2many_order.relation'
    origin = fields.Many2One('test.many2many_order', "Origin")
    target = fields.Many2One('test.many2many_order.target', "Target")


class Many2ManyOrderTarget(ModelSQL):
    __name__ = 'test.many2many_order.target'


def register(module):
    Pool.register(
        Many2Many,
        Many2ManyTarget,
        Many2ManyRelation,
        Many2ManyRequired,
        Many2ManyRequiredTarget,
        Many2ManyRequiredRelation,
        Many2ManyReference,
        Many2ManyReferenceTarget,
        Many2ManyReferenceRelation,
        Many2ManySize,
        Many2ManySizeTarget,
        Many2ManySizeRelation,
        Many2ManyDomain,
        Many2ManyDomainTarget,
        Many2ManyDomainRelation,
        Many2ManyFilter,
        Many2ManyFilterTarget,
        Many2ManyFilterRelation,
        Many2ManyFilterDomain,
        Many2ManyFilterDomainTarget,
        Many2ManyFilterDomainRelation,
        Many2ManyTree,
        Many2ManyTreeRelation,
        Many2ManyContext,
        Many2ManyContextTarget,
        Many2ManyContextRelation,
        Many2ManyOrder,
        Many2ManyOrderRelation,
        Many2ManyOrderTarget,
        module=module, type_='model')
