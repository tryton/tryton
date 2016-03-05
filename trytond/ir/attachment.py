# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import hashlib
from sql.operators import Concat

from ..model import ModelView, ModelSQL, fields, Unique
from ..config import config
from .. import backend
from ..transaction import Transaction
from ..pyson import Eval
from .resource import ResourceMixin

__all__ = [
    'Attachment',
    ]


def firstline(description):
    try:
        return (x for x in description.splitlines() if x.strip()).next()
    except StopIteration:
        return ''


class Attachment(ResourceMixin, ModelSQL, ModelView):
    "Attachment"
    __name__ = 'ir.attachment'
    name = fields.Char('Name', required=True)
    type = fields.Selection([
        ('data', 'Data'),
        ('link', 'Link'),
        ], 'Type', required=True)
    data = fields.Function(fields.Binary('Data', filename='name', states={
                'invisible': Eval('type') != 'data',
                }, depends=['type']), 'get_data', setter='set_data')
    description = fields.Text('Description')
    summary = fields.Function(fields.Char('Summary'), 'on_change_with_summary')
    link = fields.Char('Link', states={
            'invisible': Eval('type') != 'link',
            }, depends=['type'])
    digest = fields.Char('Digest', size=32)
    collision = fields.Integer('Collision')
    data_size = fields.Function(fields.Integer('Data size', states={
                'invisible': Eval('type') != 'data',
                }, depends=['type']), 'get_data')

    @classmethod
    def __setup__(cls):
        super(Attachment, cls).__setup__()
        table = cls.__table__()
        cls._sql_constraints += [
            ('resource_name',
                Unique(table, table.resource, table.name),
                'The names of attachments must be unique by resource.'),
        ]

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()

        super(Attachment, cls).__register__(module_name)

        table = TableHandler(cls, module_name)
        attachment = cls.__table__()

        # Migration from 1.4 res_model and res_id merged into resource
        # Reference
        if table.column_exist('res_model') and \
                table.column_exist('res_id'):
            table.drop_constraint('res_model_res_id_name')
            cursor.execute(*attachment.update(
                    [attachment.resource],
                    [Concat(Concat(attachment.resource, ','),
                            attachment.res_id)]))
            table.drop_column('res_model')
            table.drop_column('res_id')

    @staticmethod
    def default_type():
        return 'data'

    @staticmethod
    def default_collision():
        return 0

    def get_data(self, name):
        db_name = Transaction().database.name
        format_ = Transaction().context.get(
            '%s.%s' % (self.__name__, name), '')
        value = None
        if name == 'data_size' or format_ == 'size':
            value = 0
        if self.digest:
            filename = self.digest
            if self.collision:
                filename = filename + '-' + str(self.collision)
            filename = os.path.join(config.get('database', 'path'), db_name,
                    filename[0:2], filename[2:4], filename)
            if name == 'data_size' or format_ == 'size':
                try:
                    statinfo = os.stat(filename)
                    value = statinfo.st_size
                except OSError:
                    pass
            else:
                try:
                    with open(filename, 'rb') as file_p:
                        value = fields.Binary.cast(file_p.read())
                except IOError:
                    pass
        return value

    @classmethod
    def set_data(cls, attachments, name, value):
        if value is None:
            return
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        table = cls.__table__()
        db_name = transaction.database.name
        directory = os.path.join(config.get('database', 'path'), db_name)
        if not os.path.isdir(directory):
            os.makedirs(directory, 0770)
        digest = hashlib.md5(value).hexdigest()
        directory = os.path.join(directory, digest[0:2], digest[2:4])
        if not os.path.isdir(directory):
            os.makedirs(directory, 0770)
        filename = os.path.join(directory, digest)
        collision = 0
        if os.path.isfile(filename):
            with open(filename, 'rb') as file_p:
                data = file_p.read()
            if value != data:
                cursor.execute(*table.select(table.collision,
                        where=(table.digest == digest)
                        & (table.collision != 0),
                        group_by=table.collision,
                        order_by=table.collision))
                collision2 = 0
                for row in cursor.fetchall():
                    collision2 = row[0]
                    filename = os.path.join(directory,
                            digest + '-' + str(collision2))
                    if os.path.isfile(filename):
                        with open(filename, 'rb') as file_p:
                            data = file_p.read()
                        if value == data:
                            collision = collision2
                            break
                if collision == 0:
                    collision = collision2 + 1
                    filename = os.path.join(directory,
                            digest + '-' + str(collision))
                    with open(filename, 'wb') as file_p:
                        file_p.write(value)
        else:
            with open(filename, 'wb') as file_p:
                file_p.write(value)
        cls.write(attachments, {
            'digest': digest,
            'collision': collision,
            })

    @fields.depends('description')
    def on_change_with_summary(self, name=None):
        return firstline(self.description or '')
