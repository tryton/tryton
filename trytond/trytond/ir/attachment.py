# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import trytond.config as config
from trytond.i18n import lazy_gettext
from trytond.model import ModelSQL, ModelView, fields
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
    __name__ = 'ir.attachment'
    name = fields.Char('Name', required=True)
    type = fields.Selection([
        ('data', 'Data'),
        ('link', 'Link'),
        ], 'Type', required=True)
    description = fields.Text('Description')
    summary = fields.Function(
        fields.Char('Summary'), 'on_change_with_summary',
        searcher='search_summary')
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

    @staticmethod
    def default_type():
        return 'data'

    def get_size(self, name):
        with Transaction().set_context({
                    '%s.%s' % (self.__name__, name[:-len('_size')]): 'size',
                    }):
            record = self.__class__(self.id)
            return record.data

    @fields.depends('description')
    def on_change_with_summary(self, name=None):
        return firstline(self.description or '')

    @classmethod
    def search_summary(cls, name, clause):
        return [('description', *clause[1:])]

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
