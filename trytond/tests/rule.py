# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields
from trytond.pool import Pool


class TestRule(ModelSQL):
    "Test Rule"
    __name__ = 'test.rule'
    field = fields.Char("Field")


def register(module):
    Pool.register(
        TestRule,
        module=module, type_='model')
