#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import os
import hashlib
from sql.operators import Concat

from ..model import ModelView, ModelSQL, fields
from ..config import config
from .. import backend
from ..transaction import Transaction
from ..pyson import Eval
from ..pool import Pool

__all__ = [
    'Attachment',
    ]


def firstline(description):
    try:
        return (x for x in description.splitlines() if x.strip()).next()
    except StopIteration:
        return ''


class Attachment(ModelSQL, ModelView):
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
    resource = fields.Reference('Resource', selection='models_get',
        select=True)
    link = fields.Char('Link', states={
            'invisible': Eval('type') != 'link',
            }, depends=['type'])
    digest = fields.Char('Digest', size=32)
    collision = fields.Integer('Collision')
    data_size = fields.Function(fields.Integer('Data size', states={
                'invisible': Eval('type') != 'data',
                }, depends=['type']), 'get_data')
    last_modification = fields.Function(fields.DateTime('Last Modification'),
        'get_last_modification')
    last_user = fields.Function(fields.Char('Last User'),
        'get_last_user')

    @classmethod
    def __setup__(cls):
        super(Attachment, cls).__setup__()
        cls._sql_constraints += [
            ('resource_name', 'UNIQUE(resource, name)',
                'The  names of attachments must be unique by resource!'),
        ]

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor

        super(Attachment, cls).__register__(module_name)

        table = TableHandler(cursor, cls, module_name)
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
    def default_resource():
        return Transaction().context.get('resource')

    @staticmethod
    def default_collision():
        return 0

    @staticmethod
    def models_get():
        pool = Pool()
        Model = pool.get('ir.model')
        ModelAccess = pool.get('ir.model.access')
        models = Model.search([])
        access = ModelAccess.get_access([m.model for m in models])
        res = []
        for model in models:
            if access[model.model]['read']:
                res.append([model.model, model.name])
        return res

    def get_data(self, name):
        db_name = Transaction().cursor.dbname
        format_ = Transaction().context.pop('%s.%s'
            % (self.__name__, name), '')
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
                        value = buffer(file_p.read())
                except IOError:
                    pass
        return value

    @classmethod
    def set_data(cls, attachments, name, value):
        if value is None:
            return
        cursor = Transaction().cursor
        table = cls.__table__()
        db_name = cursor.dbname
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

    def get_last_modification(self, name):
        return (self.write_date if self.write_date else self.create_date
            ).replace(microsecond=0)

    def get_last_user(self, name):
        return (self.write_uid.rec_name if self.write_uid
            else self.create_uid.rec_name)

    @classmethod
    def check_access(cls, ids, mode='read'):
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')
        if ((Transaction().user == 0)
                or not Transaction().context.get('_check_access')):
            return
        model_names = set()
        with Transaction().set_context(_check_access=False):
            for attachment in cls.browse(ids):
                if attachment.resource:
                    model_names.add(attachment.resource.__name__)
        for model_name in model_names:
            ModelAccess.check(model_name, mode=mode)

    @classmethod
    def read(cls, ids, fields_names=None):
        cls.check_access(ids, mode='read')
        return super(Attachment, cls).read(ids, fields_names=fields_names)

    @classmethod
    def delete(cls, attachments):
        cls.check_access([a.id for a in attachments], mode='delete')
        super(Attachment, cls).delete(attachments)

    @classmethod
    def write(cls, attachments, values, *args):
        all_attachments = []
        actions = iter((attachments, values) + args)
        for records, _ in zip(actions, actions):
            all_attachments += records
        cls.check_access([a.id for a in all_attachments], mode='write')
        super(Attachment, cls).write(attachments, values, *args)
        cls.check_access(all_attachments, mode='write')

    @classmethod
    def create(cls, vlist):
        attachments = super(Attachment, cls).create(vlist)
        cls.check_access([a.id for a in attachments], mode='create')
        return attachments

    @classmethod
    def view_header_get(cls, value, view_type='form'):
        pool = Pool()
        Model = pool.get('ir.model')
        value = super(Attachment, cls).view_header_get(value,
                view_type=view_type)
        resource = Transaction().context.get('resource')
        if resource:
            model_name, record_id = resource.split(',', 1)
            ir_model, = Model.search([('model', '=', model_name)])
            Resource = pool.get(model_name)
            record = Resource(int(record_id))
            value = '%s - %s - %s' % (ir_model.name, record.rec_name, value)
        return value
