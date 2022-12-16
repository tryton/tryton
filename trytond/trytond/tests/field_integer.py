# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, fields
from trytond.pool import Pool


class Integer(ModelSQL):
    'Integer'
    __name__ = 'test.integer'
    integer = fields.Integer(string='Integer', help='Test integer',
            required=False)


class IntegerDefault(ModelSQL):
    'Integer Default'
    __name__ = 'test.integer_default'
    integer = fields.Integer(string='Integer', help='Test integer',
            required=False)

    @staticmethod
    def default_integer():
        return 5


class IntegerRequired(ModelSQL):
    'Integer Required'
    __name__ = 'test.integer_required'
    integer = fields.Integer(string='Integer', help='Test integer',
            required=True)


class IntegerDomain(ModelSQL):
    'Integer Domain'
    __name__ = 'test.integer_domain'
    integer = fields.Integer('Integer', domain=[('integer', '>', 42)])


def register(module):
    Pool.register(
        Integer,
        IntegerDefault,
        IntegerRequired,
        IntegerDomain,
        module=module, type_='model')
