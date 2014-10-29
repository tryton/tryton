# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.


from trytond.model import ModelView, fields


__all__ = [
    'ModelViewChangedValues',
    'ModelViewChangedValuesTarget',
    ]


class ModelViewChangedValues(ModelView):
    'ModelView Changed Values'
    __name__ = 'test.modelview.changed_values'
    name = fields.Char('Name')
    target = fields.Many2One('test.modelview.changed_values.target', 'Target')
    ref_target = fields.Reference('Target Reference', [
            ('test.modelview.changed_values.target', 'Target'),
            ])
    targets = fields.One2Many('test.modelview.changed_values.target', 'model',
        'Targets')
    m2m_targets = fields.Many2Many('test.modelview.changed_values.target',
        None, None, 'Targets')


class ModelViewChangedValuesTarget(ModelView):
    'ModelView Changed Values Target'
    __name__ = 'test.modelview.changed_values.target'
    name = fields.Char('Name')
    parent = fields.Many2One('test.modelview.changed_values', 'Parent')
