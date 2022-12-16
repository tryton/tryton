# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal

from trytond.model import ModelSQL, fields
from trytond.pool import Pool
from trytond.pyson import Eval


class Numeric(ModelSQL):
    'Numeric'
    __name__ = 'test.numeric'
    numeric = fields.Numeric(string='Numeric', help='Test numeric',
            required=False)


class NumericDefault(ModelSQL):
    'Numeric Default'
    __name__ = 'test.numeric_default'
    numeric = fields.Numeric(string='Numeric', help='Test numeric',
            required=False)

    @staticmethod
    def default_numeric():
        return Decimal('5.5')


class NumericRequired(ModelSQL):
    'Numeric Required'
    __name__ = 'test.numeric_required'
    numeric = fields.Numeric(string='Numeric', help='Test numeric',
            required=True)


class NumericDigits(ModelSQL):
    'Numeric Digits'
    __name__ = 'test.numeric_digits'
    digits = fields.Integer('Digits')
    numeric = fields.Numeric(string='Numeric', help='Test numeric',
        required=False, digits=(16, Eval('digits', 2)),
        depends=['digits'])


def register(module):
    Pool.register(
        Numeric,
        NumericDefault,
        NumericRequired,
        NumericDigits,
        module=module, type_='model')
