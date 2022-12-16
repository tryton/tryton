# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, MultiValueMixin, ValueMixin, fields
from trytond.pool import Pool


class ModelMultiValue(ModelSQL, MultiValueMixin):
    "Model MultiValue"
    __name__ = 'test.model_multivalue'
    value = fields.MultiValue(fields.Char("Value"))
    values = fields.One2Many(
        'test.model_multivalue.value', 'record', "Values")

    @classmethod
    def default_value(cls, **pattern):
        return "default"


class ModelValue(ModelSQL, ValueMixin):
    "Model Value"
    __name__ = 'test.model_multivalue.value'
    record = fields.Many2One(
        'test.model_multivalue', "Record")
    condition = fields.Char("Condition")
    value = fields.Char("Value")


def register(module):
    Pool.register(
        ModelMultiValue,
        ModelValue,
        module=module, type_='model')
