# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Query, Expression

from .field import Field, SQLType
from ...transaction import Transaction
from ... import backend


class Binary(Field):
    '''
    Define a binary field (``bytes``).
    '''
    _type = 'binary'
    cast = bytearray if bytes == str else bytes

    def __init__(self, string='', help='', required=False, readonly=False,
            domain=None, states=None, select=False, on_change=None,
            on_change_with=None, depends=None, filename=None, context=None,
            loading='lazy'):
        if filename is not None:
            self.filename = filename
            if depends is None:
                depends = [filename]
            else:
                depends.append(filename)
        super(Binary, self).__init__(string=string, help=help,
            required=required, readonly=readonly, domain=domain, states=states,
            select=select, on_change=on_change, on_change_with=on_change_with,
            depends=depends, context=context, loading=loading)

    @classmethod
    def get(cls, ids, model, name, values=None):
        '''
        Convert the binary value into ``bytes``

        :param ids: a list of ids
        :param model: a string with the name of the model
        :param name: a string with the name of the field
        :param values: a dictionary with the read values
        :return: a dictionary with ids as key and values as value
        '''
        if values is None:
            values = {}
        res = {}
        converter = cls.cast
        default = None
        format_ = Transaction().context.pop('%s.%s' % (model.__name__, name),
            '')
        if format_ == 'size':
            converter = len
            default = 0
        for i in values:
            value = i[name]
            if value:
                if isinstance(value, unicode):
                    value = value.encode('utf-8')
                value = converter(value)
            else:
                value = default
            res[i['id']] = value
        for i in ids:
            res.setdefault(i, default)
        return res

    @staticmethod
    def sql_format(value):
        if isinstance(value, (Query, Expression)):
            return value
        db_type = backend.name()
        if db_type == 'postgresql' and value is not None:
            import psycopg2
            return psycopg2.Binary(value)
        return value

    def sql_type(self):
        db_type = backend.name()
        if db_type == 'postgresql':
            return SQLType('BYTEA', 'BYTEA')
        elif db_type == 'mysql':
            return SQLType('LONGBLOB', 'LONGBLOB')
        return SQLType('BLOB', 'BLOB')
