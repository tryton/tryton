# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, MultiValueMixin, ValueMixin, fields
from trytond.pool import Pool


class ModelMultiValue(ModelSQL, MultiValueMixin):
    "Model MultiValue"
    __name__ = 'test.model_multivalue'
    value = fields.MultiValue(fields.Char("Value"))
    value_default = fields.MultiValue(fields.Char("Value Default"))
    values = fields.One2Many(
        'test.model_multivalue.value', 'record', "Values")

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'value_default':
            return pool.get('test.model_multivalue.value')
        return super().multivalue_model(field)

    @classmethod
    def default_value(cls, **pattern):
        return "default"

    @classmethod
    def default_value_default(cls, **pattern):
        return "other default"


class ModelValue(ModelSQL, ValueMixin):
    "Model Value"
    __name__ = 'test.model_multivalue.value'
    record = fields.Many2One(
        'test.model_multivalue', "Record")
    condition = fields.Char("Condition")
    value = fields.Char("Value")
    value_default = fields.Char("Value Default")


def register(module):
    Pool.register(
        ModelMultiValue,
        ModelValue,
        module=module, type_='model')
