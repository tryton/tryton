# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, fields
from trytond.pool import Pool
from trytond.transaction import Transaction


class Many2Many(ModelSQL):
    'Many2Many'
    __name__ = 'test.many2many'
    targets = fields.Many2Many('test.many2many.relation', 'origin', 'target',
        'Targets')


class Many2ManyTarget(ModelSQL):
    'Many2Many Target'
    __name__ = 'test.many2many.target'
    name = fields.Char('Name')


class Many2ManyRelation(ModelSQL):
    'Many2Many Relation'
    __name__ = 'test.many2many.relation'
    origin = fields.Many2One('test.many2many', 'Origin')
    target = fields.Many2One('test.many2many.target', 'Target')


class Many2ManyRequired(ModelSQL):
    'Many2Many Required'
    __name__ = 'test.many2many_required'
    targets = fields.Many2Many('test.many2many_required.relation', 'origin',
        'target', 'Targets', required=True)


class Many2ManyRequiredTarget(ModelSQL):
    'Many2Many Required Target'
    __name__ = 'test.many2many_required.target'
    name = fields.Char('Name')


class Many2ManyRequiredRelation(ModelSQL):
    'Many2Many Required Relation'
    __name__ = 'test.many2many_required.relation'
    origin = fields.Many2One('test.many2many_required', 'Origin')
    target = fields.Many2One('test.many2many_required.target', 'Target')


class Many2ManyReference(ModelSQL):
    'Many2Many Reference'
    __name__ = 'test.many2many_reference'
    targets = fields.Many2Many('test.many2many_reference.relation', 'origin',
        'target', 'Targets')


class Many2ManyReferenceTarget(ModelSQL):
    'Many2Many Reference Target'
    __name__ = 'test.many2many_reference.target'
    name = fields.Char('Name')


class Many2ManyReferenceRelation(ModelSQL):
    'Many2Many Relation'
    __name__ = 'test.many2many_reference.relation'
    origin = fields.Reference('Origin', [
            (None, ''),
            ('test.many2many_reference', 'Many2Many Reference'),
            ])
    target = fields.Many2One('test.many2many_reference.target',
        'Reference Target')


class Many2ManySize(ModelSQL):
    'Many2Many Size Relation'
    __name__ = 'test.many2many_size'
    targets = fields.Many2Many('test.many2many_size.relation', 'origin',
        'target', 'Targets', size=3)


class Many2ManySizeTarget(ModelSQL):
    'Many2Many Size Target'
    __name__ = 'test.many2many_size.target'
    name = fields.Char('Name')


class Many2ManySizeRelation(ModelSQL):
    'Many2Many Size Relation'
    __name__ = 'test.many2many_size.relation'
    origin = fields.Many2One('test.many2many_size', 'Origin')
    target = fields.Many2One('test.many2many_size.target', 'Target')


class Many2ManyFilter(ModelSQL):
    'Many2Many Filter Relation'
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
    'Many2Many Filter Target'
    __name__ = 'test.many2many_filter.target'
    value = fields.Integer('Value')


class Many2ManyFilterRelation(ModelSQL):
    'Many2Many Filter Relation'
    __name__ = 'test.many2many_filter.relation'
    origin = fields.Many2One('test.many2many_filter', 'Origin')
    target = fields.Many2One('test.many2many_filter.target', 'Target')


class Many2ManyFilterDomain(ModelSQL):
    'Many2Many Filter Domain Relation'
    __name__ = 'test.many2many_filter_domain'
    targets = fields.Many2Many('test.many2many_filter_domain.relation',
        'origin', 'target', 'Targets', domain=[('value', '<', 10)])
    filtered_targets = fields.Many2Many(
        'test.many2many_filter_domain.relation', 'origin', 'target', 'Targets',
        domain=[('value', '<', 10)], filter=[('value', '>', 2)])


class Many2ManyFilterDomainTarget(ModelSQL):
    'Many2Many Filter Domain Target'
    __name__ = 'test.many2many_filter_domain.target'
    value = fields.Integer('Value')


class Many2ManyFilterDomainRelation(ModelSQL):
    'Many2Many Filter Domain Relation'
    __name__ = 'test.many2many_filter_domain.relation'
    origin = fields.Many2One('test.many2many_filter_domain', 'Origin')
    target = fields.Many2One('test.many2many_filter.target', 'Target')


class Many2ManyTree(ModelSQL):
    'Many2Many Tree'
    __name__ = 'test.many2many_tree'
    parents = fields.Many2Many('test.many2many_tree.relation',
        'child', 'parent', 'Parents')
    children = fields.Many2Many('test.many2many_tree.relation',
        'parent', 'child', 'Children')


class Many2ManyTreeRelation(ModelSQL):
    'Many2Many Tree Relation'
    __name__ = 'test.many2many_tree.relation'
    parent = fields.Many2One('test.many2many_tree', 'Parent')
    child = fields.Many2One('test.many2many_tree', 'Child')


class Many2ManyContext(ModelSQL):
    "Many2Many Context"
    __name__ = 'test.many2many_context'
    targets = fields.Many2Many(
        'test.many2many_context.relation', 'origin', 'target', "Targets",
        context={'test': 'foo'})


class Many2ManyContextRelation(ModelSQL):
    "Many2Many Context Relation"
    __name__ = 'test.many2many_context.relation'
    origin = fields.Many2One('test.many2many_context', "Origin")
    target = fields.Many2One('test.many2many_context.target', "Target")


class Many2ManyContextTarget(ModelSQL):
    "Many2Many Context Target"
    __name__ = 'test.many2many_context.target'
    context = fields.Function(fields.Char("context"), 'get_context')

    def get_context(self, name):
        context = Transaction().context
        return context.get('test')


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
        module=module, type_='model')
