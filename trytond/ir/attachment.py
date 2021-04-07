# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null
from sql.operators import Concat

from trytond.config import config
from trytond.i18n import lazy_gettext
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.tools import firstline
from trytond.transaction import Transaction
from .resource import ResourceMixin, resource_copy

__all__ = ['AttachmentCopyMixin']


if config.getboolean('attachment', 'filestore', default=True):
    file_id = 'file_id'
    store_prefix = config.get('attachment', 'store_prefix', default=None)
else:
    file_id = None
    store_prefix = None


class Attachment(ResourceMixin, ModelSQL, ModelView):
    "Attachment"
    __name__ = 'ir.attachment'
    name = fields.Char('Name', required=True)
    type = fields.Selection([
        ('data', 'Data'),
        ('link', 'Link'),
        ], 'Type', required=True)
    description = fields.Text('Description')
    summary = fields.Function(fields.Char('Summary'), 'on_change_with_summary')
    link = fields.Char('Link', states={
            'invisible': Eval('type') != 'link',
            }, depends=['type'])
    data = fields.Binary('Data', filename='name',
        file_id=file_id, store_prefix=store_prefix,
        states={
            'invisible': Eval('type') != 'data',
            }, depends=['type'])
    file_id = fields.Char('File ID', readonly=True)
    data_size = fields.Function(fields.Integer('Data size', states={
                'invisible': Eval('type') != 'data',
                }, depends=['type']), 'get_size')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order = [
            ('create_date', 'DESC'),
            ('id', 'DESC'),
            ]

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()

        super(Attachment, cls).__register__(module_name)

        table = cls.__table_handler__(module_name)
        attachment = cls.__table__()

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

        # Migration from 4.8: remove unique constraint
        table.drop_constraint('resource_name')

    @staticmethod
    def default_type():
        return 'data'

    def get_size(self, name):
        with Transaction().set_context({
                    '%s.%s' % (self.__name__, name): 'size',
                    }):
            record = self.__class__(self.id)
            return record.data

    @fields.depends('description')
    def on_change_with_summary(self, name=None):
        return firstline(self.description or '')

    @classmethod
    def fields_view_get(cls, view_id=None, view_type='form', level=None):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        if not view_id:
            if Transaction().context.get('preview'):
                view_id = ModelData.get_id(
                    'ir', 'attachment_view_form_preview')
        return super().fields_view_get(
            view_id=view_id, view_type=view_type, level=level)


class AttachmentCopyMixin(
        resource_copy(
            'ir.attachment', 'attachments',
            lazy_gettext('ir.msg_attachments'))):
    pass
