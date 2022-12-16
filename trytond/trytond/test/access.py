#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields


class TestAccess(ModelSQL):
    'Test Access'
    _name = 'test.access'
    _description = __doc__

    field1 = fields.Char('Field 1')
    field2 = fields.Char('Field 2')

TestAccess()
