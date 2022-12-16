#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"model"
from trytond.osv import fields, OSV
from trytond.tools import Cache
import time


class Model(OSV):
    "Model"
    _name = 'ir.model'
    _description = __doc__
    name = fields.Char('Model Description', translate=True)
    model = fields.Char('Model Name', required=True)
    info = fields.Text('Information')
    module = fields.Char('Module',
       help="Module in which this model is defined")
    fields = fields.One2Many('ir.model.field', 'model', 'Fields',
       required=True)

    def __init__(self):
        super(Model, self).__init__()
        self._sql_constraints += [
            ('model_uniq', 'UNIQUE(model)',
                'The model must be unique!'),
        ]

Model()

class ModelField(OSV):
    "Model field"
    _name = 'ir.model.field'
    _description = __doc__
    name = fields.Char('Name', required=True)
    relation = fields.Char('Model Relation')
    model = fields.Many2One('ir.model', 'Model', required=True,
       select=1, ondelete='cascade')
    field_description = fields.Char('Field Description',
       translate=True)
    ttype = fields.Char('Field Type')
    groups = fields.Many2Many('res.group', 'ir_model_field_group_rel',
       'field_id', 'group_id', 'Groups')
    help = fields.Text('Help', translate=True)
    module = fields.Char('Module',
       help="Module in which this field is defined")

    def __init__(self):
        super(ModelField, self).__init__()
        self._sql_constraints += [
            ('name_model_uniq', 'UNIQUE(name, model)',
                'The field name in model must be unique!'),
        ]

    def default_name(self, cursor, user, context=None):
        return 'No Name'

    def default_field_description(self, cursor, user, context=None):
        return 'No description available'

ModelField()


class ModelAccess(OSV):
    "Model access"
    _name = 'ir.model.access'
    _description = __doc__
    _rec_name = 'model'
    model = fields.Many2One('ir.model', 'Model', required=True,
            ondelete="CASCADE")
    group = fields.Many2One('res.group', 'Group',
            ondelete="CASCADE")
    perm_read = fields.Boolean('Read Access')
    perm_write = fields.Boolean('Write Access')
    perm_create = fields.Boolean('Create Access')
    perm_delete = fields.Boolean('Delete Permission')
    description = fields.Text('Description')

    def __init__(self):
        super(ModelAccess, self).__init__()
        self._sql_constraints += [
            ('model_group_uniq', 'UNIQUE("model", "group")',
                'Only on record by model and group is allowed!'),
        ]
        self._error_messages.update({
            'read': 'You can not read this document! (%s)',
            'write': 'You can not write in this document! (%s)',
            'create': 'You can not create this kind of document! (%s)',
            'delete': 'You can not delete this document! (%s)',
            })

    def check_xml_record(self, cursor, user, ids, values, context=None):
        return True

    def default_perm_read(self, cursor, user, context=None):
        return False

    def default_perm_write(self, cursor, user, context=None):
        return False

    def default_perm_create(self, cursor, user, context=None):
        return False

    def default_perm_delete(self, cursor, user, context=None):
        return False

    def check(self, cursor, user, model_name, mode='read',
            raise_exception=True, context=None):
        assert mode in ['read', 'write', 'create', 'delete'], \
                'Invalid access mode for security'
        if user == 0:
            return True
        cursor.execute('SELECT MAX(CASE WHEN perm_'+mode+' THEN 1 else 0 END) '
            'FROM ir_model_access a '
                'JOIN ir_model m '
                    'ON (a.model = m.id) '
                'JOIN res_group_user_rel gu '
                    'ON (gu.gid = a.group) '
            'WHERE m.model = %s AND gu.uid = %s', (model_name, user,))
        row = cursor.fetchall()
        if row[0][0] is None:
            cursor.execute('SELECT ' \
                        'MAX(CASE WHEN perm_' + mode + ' THEN 1 else 0 END) ' \
                    'FROM ir_model_access a ' \
                    'JOIN ir_model m ' \
                        'ON (a.model = m.id) ' \
                    'WHERE a.group IS NULL AND m.model = %s', (model_name,))
            row = cursor.fetchall()
            if row[0][0] is None:
                return True

        if not row[0][0]:
            if raise_exception:
                self.raise_user_error(cursor, mode, model_name,
                        context=context)
            else:
                return False
        return True

    check = Cache('ir_model_access.check')(check)

    # Methods to clean the cache on the Check Method.
    def write(self, cursor, user, ids, vals, context=None):
        res = super(ModelAccess, self).write(cursor, user, ids, vals,
                context=context)
        self.check(cursor.dbname)
        # Restart the cache
        for model in self.pool.object_name_list():
            try:
                self.pool.get(model).fields_view_get(cursor.dbname)
            except:
                pass
        return res

    def create(self, cursor, user, vals, context=None):
        res = super(ModelAccess, self).create(cursor, user, vals,
                context=context)
        self.check(cursor.dbname)
        # Restart the cache
        for model in self.pool.object_name_list():
            try:
                self.pool.get(model).fields_view_get(cursor.dbname)
            except:
                pass
        return res

    def delete(self, cursor, user, ids, context=None):
        res = super(ModelAccess, self).delete(cursor, user, ids,
                context=context)
        self.check(cursor.dbname)
        # Restart the cache
        for model in self.pool.object_name_list():
            try:
                self.pool.get(model).fields_view_get(cursor.dbname)
            except:
                pass
        return res

ModelAccess()


class ModelData(OSV):
    "Model data"
    _name = 'ir.model.data'
    _description = __doc__
    fs_id = fields.Char('Identifier on File System', required=True,
            help="The id of the record as known on the file system.",
            select=1)
    model = fields.Char('Model', required=True, select=1)
    module = fields.Char('Module', required=True, select=1)
    db_id = fields.Integer('Resource ID',
       help="The id of the record in the database.", select=1)
    date_update = fields.DateTime('Update Date')
    date_init = fields.DateTime('Init Date')
    values = fields.Text('Values')
    inherit = fields.Boolean('Inherit')

    def __init__(self):
        super(ModelData, self).__init__()
        self._sql_constraints = [
            ('fs_id_module_model_uniq', 'UNIQUE("fs_id", "module", "model")',
                'The triple (fs_id, module, model) must be unique!'),
        ]

    def default_date_init(self, cursor, user, context=None):
        return time.strftime('%Y-%m-%d %H:%M:%S')

    def default_inherit(self, cursor, user, context=None):
        return False

    def get_id(self, cursor, user, module, fs_id):
        """
        Return for an fs_id the corresponding db_id.

        :param cursor: the database cursor
        :param user: the user id
        :param module: the module name
        :param fs_id: the id in the xml file

        :return: the database id
        """
        ids = self.search(cursor, user, [
            ('module', '=', module),
            ('fs_id', '=', fs_id),
            ('inherit', '=', False),
            ])
        if not ids:
            raise Exception("Reference to %s not found" % \
                                ".".join([module,fs_id]))
        return self.read(cursor, user, ids[0], ['db_id'])['db_id']

ModelData()
