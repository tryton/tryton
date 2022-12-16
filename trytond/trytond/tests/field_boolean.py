# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, fields
from trytond.pool import Pool


class Boolean(ModelSQL):
    'Boolean'
    __name__ = 'test.boolean'
    boolean = fields.Boolean(string='Boolean', help='Test boolean')


class BooleanDefault(ModelSQL):
    'Boolean Default'
    __name__ = 'test.boolean_default'
    boolean = fields.Boolean(string='Boolean', help='Test boolean')

    @staticmethod
    def default_boolean():
        return True


def register(module):
    Pool.register(
        Boolean,
        BooleanDefault,
        module=module, type_='model')
