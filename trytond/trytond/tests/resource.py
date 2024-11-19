# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.ir.note import NoteCopyMixin
from trytond.model import ModelSQL
from trytond.pool import Pool


class TestResource(ModelSQL, NoteCopyMixin):
    __name__ = 'test.resource'

    @classmethod
    def get_resources_to_copy(cls, name):
        return {'test.resource.other'}


class TestResourceOther(ModelSQL):
    __name__ = 'test.resource.other'


def register(module):
    Pool.register(
        TestResource,
        TestResourceOther,
        module=module, type_='model')
