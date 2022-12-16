# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, MultiValueMixin, ValueMixin, fields
from trytond.pool import Pool


class ModelMultiValue(ModelSQL, MultiValueMixin):
    "Model MultiValue"
    __name__ = 'test.model_multivalue'
    value = fields.MultiValue(fields.Char("Value"))
    value_default = fields.MultiValue(fields.Char("Value Default"))
    value_many2one = fields.MultiValue(
        fields.Many2One('test.model_multivalue.target', "Value Many2One"))
    value_multiselection = fields.MultiValue(
        fields.MultiSelection([
                ('foo', "Foo"),
                ('bar', "Bar"),
                ], "Value Multi Selection"))
    value_reference = fields.MultiValue(
        fields.Reference(
            "Value Reference",
            selection=[
                (None, ""),
                ('test.model_multivalue.target', "Target"),
                ]))
    values = fields.One2Many(
        'test.model_multivalue.value', 'record', "Values")

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        multivalue_fields = {
            'value',
            'value_default',
            'value_many2one',
            'value_multiselection',
            'value_reference'
            }
        if field in multivalue_fields:
            return pool.get('test.model_multivalue.value')
        return super().multivalue_model(field)

    @classmethod
    def default_value(cls, **pattern):
        return "default"

    @classmethod
    def default_value_default(cls, **pattern):
        return "other default"

    @classmethod
    def default_value_multiselection(cls, **pattern):
        return ('foo',)


class ModelValue(ModelSQL, ValueMixin):
    "Model Value"
    __name__ = 'test.model_multivalue.value'
    record = fields.Many2One(
        'test.model_multivalue', "Record")
    condition = fields.Char("Condition")
    value = fields.Char("Value")
    value_default = fields.Char("Value Default")
    value_many2one = fields.Many2One(
        'test.model_multivalue.target', "Value Many2One")
    value_multiselection = fields.MultiSelection([
            ('foo', "Foo"),
            ('bar', "Bar"),
            ], "Value Multi Selection")
    value_reference = fields.Reference(
        "Value Reference",
        selection=[
            (None, ""),
            ('test.model_multivalue.target', "Target"),
            ])


class ModelMultiValueTarget(ModelSQL):
    "Model MultiValue Target"
    __name__ = 'test.model_multivalue.target'
    name = fields.Char("Name")


def register(module):
    Pool.register(
        ModelMultiValue,
        ModelValue,
        ModelMultiValueTarget,
        module=module, type_='model')
