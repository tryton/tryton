# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import logging

from sql import Column, Literal, Null
from sql.functions import CurrentTimestamp

from trytond.filestore import filestore
from trytond.pool import Pool
from trytond.tools import cached_property
from trytond.transaction import Transaction

from .field import SQL_OPERATORS, Field

logger = logging.getLogger(__name__)


def caster(d):
    if isinstance(d, bytes):
        return d
    elif isinstance(d, memoryview):
        return bytes(d)
    return bytes(d, encoding='utf8')


class Binary(Field):
    _type = 'binary'
    _sql_type = 'BLOB'
    _py_type = bytes
    cast = staticmethod(caster)

    def __init__(self, string='', help='', required=False, readonly=False,
            domain=None, states=None, on_change=None,
            on_change_with=None, depends=None, context=None, loading='lazy',
            filename=None, file_id=None, store_prefix=None):
        self.filename = filename
        self.file_id = file_id
        self.store_prefix = store_prefix
        super().__init__(string=string, help=help,
            required=required, readonly=readonly, domain=domain, states=states,
            on_change=on_change, on_change_with=on_change_with,
            depends=depends, context=context, loading=loading)

    @cached_property
    def display_depends(self):
        depends = super().display_depends
        if self.filename:
            depends.add(self.filename)
        return depends

    def get(self, ids, model, name, values=None):
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
        transaction = Transaction()
        res = {}
        converter = self.cast
        default = None
        format_ = Transaction().context.get(
            '%s.%s' % (model.__name__, name), '')
        if format_ == 'size':
            converter = len
            default = 0

        if self.file_id:
            table = model.__table__()
            cursor = transaction.connection.cursor()

            prefix = self.store_prefix
            if prefix is None:
                prefix = transaction.database.name

            if format_ == 'size':
                store_func = filestore.size
            else:
                def store_func(id, prefix):
                    return self.cast(filestore.get(id, prefix=prefix))

            cursor.execute(*table.select(
                    table.id, Column(table, self.file_id),
                    where=SQL_OPERATORS['in'](table.id, ids)
                    & (Column(table, self.file_id) != Null)
                    & (Column(table, self.file_id) != '')))
            for record_id, file_id in cursor:
                try:
                    res[record_id] = store_func(file_id, prefix)
                except (IOError, OSError):
                    logger.exception(
                        "failed to retrieve %r from filestore at %r",
                        file_id, prefix)

        for i in values:
            if i['id'] in res:
                continue
            value = i[name]
            if value:
                value = converter(value)
            else:
                value = default
            res[i['id']] = value
        for i in ids:
            res.setdefault(i, default)
        return res

    def queue_for_removal(self, Model, name, ids):
        pool = Pool()
        Queue = pool.get('ir.filestore.queue')
        queue = Queue.__table__()

        assert name == self.name

        if not self.file_id:
            return

        transaction = Transaction()
        table = Model.__table__()
        cursor = transaction.connection.cursor()

        prefix = self.store_prefix
        fileid_col = Column(table, self.file_id)
        cursor.execute(*queue.insert(
                [queue.create_date, queue.create_uid,
                    queue.file_id, queue.model,
                    queue.prefix, queue.field],
                table.select(
                    CurrentTimestamp(), Literal(transaction.user),
                    fileid_col, Literal(Model.__name__),
                    Literal(prefix), Literal(name),
                    where=(SQL_OPERATORS['in'](table.id, ids)
                        & (fileid_col != Null)))
                ))

    def set(self, Model, name, ids, value, *args):
        transaction = Transaction()
        table = Model.__table__()
        cursor = transaction.connection.cursor()

        prefix = self.store_prefix
        if prefix is None:
            prefix = transaction.database.name

        args = iter((ids, value) + args)
        for ids, value in zip(args, args):
            self.queue_for_removal(Model, name, ids)
            if self.file_id:
                columns = [Column(table, self.file_id), Column(table, name)]
                values = [
                    filestore.set(value, prefix) if value else None, None]
            else:
                columns = [Column(table, name)]
                values = [self.sql_format(value)]
            cursor.execute(*table.update(columns, values,
                    where=SQL_OPERATORS['in'](table.id, ids)))

    def definition(self, model, language):
        definition = super().definition(model, language)
        definition['searchable'] = False
        definition['filename'] = self.filename
        return definition
