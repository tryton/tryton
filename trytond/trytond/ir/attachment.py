#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from __future__ import with_statement
import os
try:
    import hashlib
except ImportError:
    hashlib = None
    import md5
import base64
from trytond.model import ModelView, ModelSQL, fields
from trytond.config import CONFIG
from trytond.backend import TableHandler
from trytond.transaction import Transaction


class Attachment(ModelSQL, ModelView):
    "Attachment"
    _name = 'ir.attachment'
    _description = __doc__
    name = fields.Char('Attachment Name', required=True)
    datas = fields.Function(fields.Binary('Datas'), 'get_datas',
            setter='set_datas')
    description = fields.Text('Description')
    resource = fields.Reference('Resource', selection='models_get',
            select=1)
    link = fields.Char('Link')
    digest = fields.Char('Digest', size=32)
    collision = fields.Integer('Collision')
    datas_size = fields.Function(fields.Integer('Datas size'), 'get_datas')

    def __init__(self):
        super(Attachment, self).__init__()
        self._sql_constraints += [
            ('resource_name', 'UNIQUE(resource, name)',
                'The  names of attachments must be unique by resource!'),
        ]

    def init(self, module_name):
        super(Attachment, self).init(module_name)

        cursor = Transaction().cursor
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

    def default_resource(self):
        return Transaction().context.get('resource')

    def default_collision(self):
        return 0

    def models_get(self):
        model_obj = self.pool.get('ir.model')
        model_ids = model_obj.search([])
        res = []
        for model in model_obj.browse(model_ids):
            res.append([model.model, model.name])
        return res

    def get_datas(self, ids, name):
        res = {}
        db_name = Transaction().cursor.dbname
        for attachment in self.browse(ids):
            value = False
            if name == 'datas_size':
                value = 0
            if attachment.digest:
                filename = attachment.digest
                if attachment.collision:
                    filename = filename + '-' + str(attachment.collision)
                filename = os.path.join(CONFIG['data_path'], db_name,
                        filename[0:2], filename[2:4], filename)
                if name == 'datas_size':
                    try:
                        statinfo = os.stat(filename)
                        value = statinfo.st_size
                    except OSError:
                        pass
                else:
                    try:
                        file_p = open(filename, 'rb')
                        value = base64.encodestring(file_p.read())
                        file_p.close()
                    except IOError:
                        pass
            res[attachment.id] = value
        return res

    def set_datas(self, ids, name, value):
        if value is False or value is None:
            return
        cursor = Transaction().cursor
        db_name = cursor.dbname
        directory = os.path.join(CONFIG['data_path'], db_name)
        if not os.path.isdir(directory):
            os.makedirs(directory, 0770)
        data = base64.decodestring(value)
        if hashlib:
            digest = hashlib.md5(data).hexdigest()
        else:
            digest = md5.new(data).hexdigest()
        directory = os.path.join(directory, digest[0:2], digest[2:4])
        if not os.path.isdir(directory):
            os.makedirs(directory, 0770)
        filename = os.path.join(directory, digest)
        collision = 0
        if os.path.isfile(filename):
            file_p = open(filename, 'rb')
            data2 = file_p.read()
            file_p.close()
            if data != data2:
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
                        file_p = open(filename, 'rb')
                        data2 = file_p.read()
                        file_p.close()
                        if data == data2:
                            collision = collision2
                            break
                if collision == 0:
                    collision = collision2 + 1
                    filename = os.path.join(directory,
                            digest + '-' + str(collision))
                    file_p = open(filename, 'wb')
                    file_p.write(data)
                    file_p.close()
        else:
            file_p = open(filename, 'wb')
            file_p.write(data)
            file_p.close()
        self.write(ids, {
            'digest': digest,
            'collision': collision,
            })

    def check_access(self, ids, mode='read'):
        model_access_obj = self.pool.get('ir.model.access')
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

Attachment()
