# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, fields
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction


class One2Many(ModelSQL):
    'One2Many Relation'
    __name__ = 'test.one2many'
    targets = fields.One2Many('test.one2many.target', 'origin', 'Targets')


class One2ManyTarget(ModelSQL):
    'One2Many Target'
    __name__ = 'test.one2many.target'
    name = fields.Char('Name')
    origin = fields.Many2One('test.one2many', 'Origin')


class One2ManyRequired(ModelSQL):
    'One2Many Required'
    __name__ = 'test.one2many_required'
    targets = fields.One2Many('test.one2many_required.target', 'origin',
        'Targets', required=True)


class One2ManyRequiredTarget(ModelSQL):
    'One2Many Required Target'
    __name__ = 'test.one2many_required.target'
    name = fields.Char('Name')
    origin = fields.Many2One('test.one2many_required', 'Origin')


class One2ManyReference(ModelSQL):
    'One2Many Reference Relation'
    __name__ = 'test.one2many_reference'
    targets = fields.One2Many('test.one2many_reference.target', 'origin',
        'Targets')


class One2ManyReferenceTarget(ModelSQL):
    'One2Many Reference Target'
    __name__ = 'test.one2many_reference.target'
    name = fields.Char('Name')
    origin = fields.Reference('Origin', [
            (None, ''),
            ('test.one2many_reference', 'One2Many Reference'),
            ])


class One2ManySize(ModelSQL):
    'One2Many Size Relation'
    __name__ = 'test.one2many_size'
    targets = fields.One2Many('test.one2many_size.target', 'origin', 'Targets',
        size=3)


class One2ManySizeTarget(ModelSQL):
    'One2Many Size Target'
    __name__ = 'test.one2many_size.target'
    origin = fields.Many2One('test.one2many_size', 'Origin')


class One2ManySizePYSON(ModelSQL):
    'One2Many Size PYSON Relation'
    __name__ = 'test.one2many_size_pyson'
    limit = fields.Integer('Limit')
    targets = fields.One2Many('test.one2many_size_pyson.target', 'origin',
        'Targets', size=Eval('limit', 0))


class One2ManySizePYSONTarget(ModelSQL):
    'One2Many Size PYSON Target'
    __name__ = 'test.one2many_size_pyson.target'
    origin = fields.Many2One('test.one2many_size_pyson', 'Origin')


class One2ManyFilter(ModelSQL):
    'One2Many Filter Relation'
    __name__ = 'test.one2many_filter'
    targets = fields.One2Many('test.one2many_filter.target', 'origin',
        'Targets')
    filtered_targets = fields.One2Many('test.one2many_filter.target', 'origin',
        'Filtered Targets', filter=[('value', '>', 2)])


class One2ManyFilterTarget(ModelSQL):
    'One2Many Filter Target'
    __name__ = 'test.one2many_filter.target'
    origin = fields.Many2One('test.one2many_filter', 'Origin')
    value = fields.Integer('Value')


class One2ManyFilterDomain(ModelSQL):
    'One2Many Filter Relation'
    __name__ = 'test.one2many_filter_domain'
    targets = fields.One2Many('test.one2many_filter_domain.target', 'origin',
        'Targets', domain=[('value', '<', 10)])
    filtered_targets = fields.One2Many('test.one2many_filter_domain.target',
        'origin', 'Filtered Targets', domain=[('value', '<', 10)],
        filter=[('value', '>', 2)])


class One2ManyFilterDomainTarget(ModelSQL):
    'One2Many Filter Domain Target'
    __name__ = 'test.one2many_filter_domain.target'
    origin = fields.Many2One('test.one2many_filter_domain', 'Origin')
    value = fields.Integer('Value')


class One2ManyContext(ModelSQL):
    "One2Many Context"
    __name__ = 'test.one2many_context'
    targets = fields.One2Many(
        'test.one2many_context.target', 'origin', "Targets",
        context={'test': Eval('id')})


class One2ManyContextTarget(ModelSQL):
    "One2Many Context Target"
    __name__ = 'test.one2many_context.target'
    origin = fields.Many2One('test.one2many_context', "Origin")
    context = fields.Function(fields.Char("context"), 'get_context')

    def get_context(self, name):
        context = Transaction().context
        return context.get('test')


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
        One2ManyFilter,
        One2ManyFilterTarget,
        One2ManyFilterDomain,
        One2ManyFilterDomainTarget,
        One2ManyContext,
        One2ManyContextTarget,
        module=module, type_='model')
