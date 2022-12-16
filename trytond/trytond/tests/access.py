# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields
from trytond.pool import Pool


class TestAccess(ModelSQL):
    'Test Access'
    __name__ = 'test.access'
    field1 = fields.Char('Field 1')
    field2 = fields.Char('Field 2')
    relate = fields.Many2One('test.access.relate', "Relate")
    reference = fields.Reference("Reference", [
            (None, ""),
            ('test.access.relate', "Reference"),
            ])
    dict_ = fields.Dict(None, "Dict")


class TestAccessRelate(ModelSQL):
    "Test Access"
    __name__ = 'test.access.relate'
    value = fields.Integer("Value")
    parent = fields.Many2One('test.access.relate', "Parent")


class TestAccessModel(TestAccess):
    "Test Access from Model"
    __name__ = 'test.access.model'
    access = fields.Many2One('test.access', "Access")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('access')


def register(module):
    Pool.register(
        TestAccess,
        TestAccessRelate,
        TestAccessModel,
        module=module, type_='model')
