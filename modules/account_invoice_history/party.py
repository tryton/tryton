# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.transaction import Transaction


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'
    _history = True


class Address(metaclass=PoolMeta):
    __name__ = 'party.address'
    _history = True


class Identifier(metaclass=PoolMeta):
    __name__ = 'party.identifier'
    _history = True

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        table = cls.__table_history__()
        table_h = cls.__table_handler__(module_name=module_name, history=True)

        fill_code_compact = (
            table_h.column_exist('code')
            and not table_h.column_exist('code_compact'))

        super().__register__(module_name)

        # Migration from 7.8: Fill code_compact
        if fill_code_compact:
            cursor.execute(*table.update([table.code_compact], [table.code]))
