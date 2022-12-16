#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import os
try:
    import hashlib
except ImportError:
    hashlib = None
    import md5
from trytond.model import ModelView, ModelSQL, fields
from trytond.config import CONFIG
from trytond.backend import TableHandler
from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.pool import Pool

def firstline(description):
    try:
        return (x for x in description.splitlines() if x.strip()).next()
    except StopIteration:
        return ''


class Attachment(ModelSQL, ModelView):
    "Attachment"
    _name = 'ir.attachment'
    _description = __doc__
    name = fields.Char('Name', required=True)
    type = fields.Selection([
        ('data', 'Data'),
        ('link', 'Link'),
        ], 'Type', required=True)
    data = fields.Function(fields.Binary('Data', filename='name', states={
                'invisible': Eval('type') != 'data',
                }, depends=['type']), 'get_data', setter='set_data')
    description = fields.Text('Description')
    summary = fields.Function(fields.Char('Summary',
        on_change_with=['description']), 'get_summary')
    resource = fields.Reference('Resource', selection='models_get', select=1)
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

    def __init__(self):
        super(Attachment, self).__init__()
        self._sql_constraints += [
            ('resource_name', 'UNIQUE(resource, name)',
                'The  names of attachments must be unique by resource!'),
        ]

    def init(self, module_name):
        cursor = Transaction().cursor

        super(Attachment, self).init(module_name)

        table = TableHandler(cursor, self, module_name)

        # Migration from 1.4 res_model and res_id merged into resource
        # Reference
        if table.column_exist('res_model') and \
                table.column_exist('res_id'):
            table.drop_constraint('res_model_res_id_name')
            cursor.execute('UPDATE "%s" '
            'SET "resource" = "res_model"||\',\'||"res_id"' % self._table)
            table.drop_column('res_model')
            table.drop_column('res_id')

    def default_type(self):
        return 'data'

    def default_resource(self):
        return Transaction().context.get('resource')

    def default_collision(self):
        return 0

    def models_get(self):
        pool = Pool()
        model_obj = pool.get('ir.model')
        model_ids = model_obj.search([])
        res = []
        for model in model_obj.browse(model_ids):
            res.append([model.model, model.name])
        return res

    def get_data(self, ids, name):
        res = {}
        db_name = Transaction().cursor.dbname
        format_ = Transaction().context.pop('%s.%s' % (self._name, name), '')
        for attachment in self.browse(ids):
            value = False
            if name == 'data_size' or format_ == 'size':
                value = 0
            if attachment.digest:
                filename = attachment.digest
                if attachment.collision:
                    filename = filename + '-' + str(attachment.collision)
                filename = os.path.join(CONFIG['data_path'], db_name,
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
            res[attachment.id] = value
        return res

    def set_data(self, ids, name, value):
        if value is False or value is None:
            return
        cursor = Transaction().cursor
        db_name = cursor.dbname
        directory = os.path.join(CONFIG['data_path'], db_name)
        if not os.path.isdir(directory):
            os.makedirs(directory, 0770)
        if hashlib:
            digest = hashlib.md5(value).hexdigest()
        else:
            digest = md5.new(value).hexdigest()
        directory = os.path.join(directory, digest[0:2], digest[2:4])
        if not os.path.isdir(directory):
            os.makedirs(directory, 0770)
        filename = os.path.join(directory, digest)
        collision = 0
        if os.path.isfile(filename):
            with open(filename, 'rb') as file_p:
                data = file_p.read()
            if value != data:
                cursor.execute('SELECT DISTINCT(collision) FROM ir_attachment ' \
                        'WHERE digest = %s ' \
                            'AND collision != 0 ' \
                        'ORDER BY collision', (digest,))
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
        self.write(ids, {
            'digest': digest,
            'collision': collision,
            })

    def get_summary(self, ids, name):
        return dict((x.id, firstline(x.description or ''))
            for x in self.browse(ids))

    def on_change_with_summary(self, values):
        return firstline(values.get('description') or '')

    def get_last_modification(self, ids, name):
        return dict((x.id, (x.write_date if x.write_date else x.create_date
            ).replace(microsecond=0))
            for x in self.browse(ids))

    def get_last_user(self, ids, name):
        with Transaction().set_user(0):
            return dict( (x.id, x.write_uid.rec_name if x.write_uid
                else x.create_uid.rec_name) for x in self.browse(ids))


    def check_access(self, ids, mode='read'):
        pool = Pool()
        model_access_obj = pool.get('ir.model.access')
        if Transaction().user == 0:
            return
        if not ids:
            return
        if isinstance(ids, (int, long)):
            ids = [ids]
        model_names = set()
        with Transaction().set_user(0):
            for attachment in self.browse(ids):
                if attachment.resource:
                    model_names.add(attachment.resource.split(',')[0])
        for model_name in model_names:
            model_access_obj.check(model_name, mode=mode)

    def read(self, ids, fields_names=None):
        self.check_access(ids, mode='read')
        return super(Attachment, self).read(ids, fields_names=fields_names)

    def delete(self, ids):
        self.check_access(ids, mode='delete')
        return super(Attachment, self).delete(ids)

    def write(self, ids, vals):
        self.check_access(ids, mode='write')
        res = super(Attachment, self).write(ids, vals)
        self.check_access(ids, mode='write')
        return res

    def create(self, vals):
        res = super(Attachment, self).create(vals)
        self.check_access(res, mode='create')
        return res

    def view_header_get(self, value, view_type='form'):
        pool = Pool()
        ir_model_obj = pool.get('ir.model')
        value = super(Attachment, self).view_header_get(value,
                view_type=view_type)
        resource = Transaction().context.get('resource')
        if resource:
            model_name, record_id = resource.split(',', 1)
            ir_model_id, = ir_model_obj.search([('model', '=', model_name)])
            ir_model = ir_model_obj.browse(ir_model_id)
            model_obj = pool.get(model_name)
            record = model_obj.browse(int(record_id))
            value = '%s - %s - %s' % (ir_model.name, record.rec_name, value)
        return value

Attachment()
