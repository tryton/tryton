# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import Check, ModelSQL, fields
from trytond.pool import Pool


class Binary(ModelSQL):
    __name__ = 'test.binary'
    binary = fields.Binary('Binary')


class BinaryDefault(ModelSQL):
    __name__ = 'test.binary_default'
    binary = fields.Binary('Binary Default')

    @staticmethod
    def default_binary():
        return b'default'


class BinaryRequired(ModelSQL):
    __name__ = 'test.binary_required'
    binary = fields.Binary('Binary Required', required=True)


class BinaryRequiredSQLConstraint(ModelSQL):
    __name__ = 'test.binary_required_sql_constraint'
    binary = fields.Binary('Binary Required', required=True)
    constraint = fields.Boolean("Constraint")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints.append(
            ('constraint', Check(t, t.constraint),
                'tests.msg_binary_required_sql_constraint'))


class BinaryFileStorage(ModelSQL):
    __name__ = 'test.binary_filestorage'
    binary = fields.Binary('Binary', file_id='binary_id')
    binary_id = fields.Char('Binary ID')


def register(module):
    Pool.register(
        Binary,
        BinaryDefault,
        BinaryRequired,
        BinaryRequiredSQLConstraint,
        BinaryFileStorage,
        module=module, type_='model')
