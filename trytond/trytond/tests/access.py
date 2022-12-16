# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields

__all__ = [
    'TestAccess',
    ]


class TestAccess(ModelSQL):
    'Test Access'
    __name__ = 'test.access'
    field1 = fields.Char('Field 1')
    field2 = fields.Char('Field 2')
