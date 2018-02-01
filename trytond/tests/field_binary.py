# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, fields
from trytond.pool import Pool


class Binary(ModelSQL):
    'Binary'
    __name__ = 'test.binary'
    binary = fields.Binary('Binary')


class BinaryDefault(ModelSQL):
    'Binary Default'
    __name__ = 'test.binary_default'
    binary = fields.Binary('Binary Default')

    @staticmethod
    def default_binary():
        return b'default'


class BinaryRequired(ModelSQL):
    'Binary Required'
    __name__ = 'test.binary_required'
    binary = fields.Binary('Binary Required', required=True)


class BinaryFileStorage(ModelSQL):
    "Binary in FileStorage"
    __name__ = 'test.binary_filestorage'
    binary = fields.Binary('Binary', file_id='binary_id')
    binary_id = fields.Char('Binary ID')


def register(module):
    Pool.register(
        Binary,
        BinaryDefault,
        BinaryRequired,
        BinaryFileStorage,
        module=module, type_='model')
