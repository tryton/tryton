# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null
from sql.operators import Concat

from ..model import ModelView, ModelSQL, fields, Unique
from .. import backend
from ..transaction import Transaction
from ..pyson import Eval
from .resource import ResourceMixin
from ..filestore import filestore

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
    file_id = fields.Char('File ID', readonly=True)
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

        # Migration from 4.0: merge digest and collision into file_id
        if table.column_exist('digest') and table.column_exist('collision'):
            cursor.execute(*attachment.update(
                    [attachment.file_id],
                    [attachment.digest],
                    where=(attachment.collision == 0)
                    | (attachment.collision == Null)))
            cursor.execute(*attachment.update(
                    [attachment.file_id],
                    [Concat(Concat(attachment.digest, '-'),
                            attachment.collision)],
                    where=(attachment.collision != 0)
                    & (attachment.collision != Null)))
            table.drop_column('digest')
            table.drop_column('collision')

    @staticmethod
    def default_type():
        return 'data'

    def get_data(self, name):
        db_name = Transaction().database.name
        format_ = Transaction().context.get(
            '%s.%s' % (self.__name__, name), '')
        value = None
        if name == 'data_size' or format_ == 'size':
            value = 0
        if self.file_id:
            if name == 'data_size' or format_ == 'size':
                try:
                    value = filestore.size(self.file_id, prefix=db_name)
                except OSError:
                    pass
            else:
                try:
                    value = fields.Binary.cast(
                        filestore.get(self.file_id, prefix=db_name))
                except IOError:
                    pass
        return value

    @classmethod
    def set_data(cls, attachments, name, value):
        if value is None:
            return
        transaction = Transaction()
        db_name = transaction.database.name
        file_id = filestore.set(value, prefix=db_name)
        cls.write(attachments, {
                'file_id': file_id,
                })

    @fields.depends('description')
    def on_change_with_summary(self, name=None):
        return firstline(self.description or '')
