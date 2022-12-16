# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, fields
from trytond.pool import Pool
from trytond.pyson import Eval


class Float(ModelSQL):
    'Float'
    __name__ = 'test.float'
    float = fields.Float(string='Float', help='Test float',
            required=False)


class FloatDefault(ModelSQL):
    'Float Default'
    __name__ = 'test.float_default'
    float = fields.Float(string='Float', help='Test float',
            required=False)

    @staticmethod
    def default_float():
        return 5.5


class FloatRequired(ModelSQL):
    'Float Required'
    __name__ = 'test.float_required'
    float = fields.Float(string='Float', help='Test float',
            required=True)


class FloatDigits(ModelSQL):
    'Float Digits'
    __name__ = 'test.float_digits'
    digits = fields.Integer('Digits')
    float = fields.Float(string='Float', help='Test float',
        required=False, digits=(16, Eval('digits', 2)),
        depends=['digits'])


def register(module):
    Pool.register(
        Float,
        FloatDefault,
        FloatRequired,
        FloatDigits,
        module=module, type_='model')
