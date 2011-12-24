#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime
import base64
import re
from trytond.model import ModelView, ModelSQL, fields
from trytond.report import Report
from trytond.wizard import Wizard
from trytond.transaction import Transaction
from trytond.cache import Cache
IDENTIFIER = re.compile(r'^[a-zA-z_][a-zA-Z0-9_]*$')


class Model(ModelSQL, ModelView):
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
        self._constraints += [
            ('check_module', 'invalid_module'),
        ]
        self._error_messages.update({
            'invalid_module': 'Module Name must be a python identifier!',
        })
        self._order.insert(0, ('model', 'ASC'))

    def check_module(self, ids):
        '''
        Check module
        '''
        for model in self.browse(ids):
            if model.module and not IDENTIFIER.match(model.module):
                return False
        return True

    def create(self, vals):
        property_obj = self.pool.get('ir.property')
        res = super(Model, self).create(vals)
        # Restart the cache of models_get
        property_obj.models_get.reset()
        return res

    def write(self, ids, vals):
        property_obj = self.pool.get('ir.property')
        res = super(Model, self).write(ids, vals)
        # Restart the cache of models_get
        property_obj.models_get.reset()
        return res

    def delete(self, ids):
        property_obj = self.pool.get('ir.property')
        res = super(Model, self).delete(ids)
        # Restart the cache of models_get
        property_obj.models_get.reset()
        return res

Model()


class ModelField(ModelSQL, ModelView):
    "Model field"
    _name = 'ir.model.field'
    _description = __doc__
    name = fields.Char('Name', required=True)
    relation = fields.Char('Model Relation')
    model = fields.Many2One('ir.model', 'Model', required=True,
       select=1, ondelete='CASCADE')
    field_description = fields.Char('Field Description', translate=True)
    ttype = fields.Char('Field Type')
    groups = fields.Many2Many('ir.model.field-res.group', 'field_id',
            'group_id', 'Groups')
    help = fields.Text('Help', translate=True)
    module = fields.Char('Module',
       help="Module in which this field is defined")

    def __init__(self):
        super(ModelField, self).__init__()
        self._sql_constraints += [
            ('name_model_uniq', 'UNIQUE(name, model)',
                'The field name in model must be unique!'),
        ]
        self._constraints += [
            ('check_name', 'invalid_name'),
        ]
        self._error_messages.update({
            'invalid_name': 'Model Field Name must be a python identifier!',
        })
        self._order.insert(0, ('name', 'ASC'))

    def default_name(self):
        return 'No Name'

    def default_field_description(self):
        return 'No description available'

    def check_name(self, ids):
        '''
        Check name
        '''
        for field in self.browse(ids):
            if not IDENTIFIER.match(field.name):
                return False
        return True

    def read(self, ids, fields_names=None):
        translation_obj = self.pool.get('ir.translation')

        to_delete = []
        if Transaction().context.get('language'):
            if fields_names is None:
                fields_names = self._columns.keys()

            if 'field_description' in fields_names \
                    or 'help' in fields_names:
                if 'model' not in fields_names:
                    fields_names.append('model')
                    to_delete.append('model')
                if 'name' not in fields_names:
                    fields_names.append('name')
                    to_delete.append('name')

        int_id = False
        if isinstance(ids, (int, long)):
            int_id = True
            ids = [ids]
        res = super(ModelField, self).read(ids, fields_names=fields_names)

        if (Transaction().context.get('language')
                and ('field_description' in fields_names
                    or 'help' in fields_names)):
            model_ids = set()
            for rec in res:
                if isinstance(rec['model'], (list, tuple)):
                    model_ids.add(rec['model'][0])
                else:
                    model_ids.add(rec['model'])
            model_ids = list(model_ids)
            cursor = Transaction().cursor
            cursor.execute('SELECT id, model FROM ir_model WHERE id IN ' \
                    '(' + ','.join(('%s',) * len(model_ids)) + ')', model_ids)
            id2model = dict(cursor.fetchall())

            trans_args = []
            for rec in res:
                if isinstance(rec['model'], (list, tuple)):
                    model_id = rec['model'][0]
                else:
                    model_id = rec['model']
                if 'field_description' in fields_names:
                    trans_args.append((id2model[model_id] + ',' + rec['name'],
                        'field', Transaction().language, None))
                if 'help' in fields_names:
                    trans_args.append((id2model[model_id] + ',' + rec['name'],
                            'help', Transaction().language, None))
            translation_obj._get_sources(trans_args)
            for rec in res:
                if isinstance(rec['model'], (list, tuple)):
                    model_id = rec['model'][0]
                else:
                    model_id = rec['model']
                if 'field_description' in fields_names:
                    res_trans = translation_obj._get_source(
                            id2model[model_id] + ',' + rec['name'],
                            'field', Transaction().language)
                    if res_trans:
                        rec['field_description'] = res_trans
                if 'help' in fields_names:
                    res_trans = translation_obj._get_source(
                            id2model[model_id] + ',' + rec['name'],
                            'help', Transaction().language)
                    if res_trans:
                        rec['help'] = res_trans

        if to_delete:
            for rec in res:
                for field in to_delete:
                    del rec[field]
        if int_id:
            res = res[0]
        return res

ModelField()


class ModelAccess(ModelSQL, ModelView):
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
    perm_delete = fields.Boolean('Delete Access')
    description = fields.Text('Description')

    def __init__(self):
        super(ModelAccess, self).__init__()
        self._sql_constraints += [
            ('model_group_uniq', 'UNIQUE("model", "group")',
                'Only one record by model and group is allowed!'),
        ]
        self._error_messages.update({
            'read': 'You can not read this document! (%s)',
            'write': 'You can not write in this document! (%s)',
            'create': 'You can not create this kind of document! (%s)',
            'delete': 'You can not delete this document! (%s)',
            })

    def check_xml_record(self, ids, values):
        return True

    def default_perm_read(self):
        return False

    def default_perm_write(self):
        return False

    def default_perm_create(self):
        return False

    def default_perm_delete(self):
        return False

    @Cache('ir_model_access.check')
    def check(self, model_name, mode='read', raise_exception=True):
        assert mode in ['read', 'write', 'create', 'delete'], \
                'Invalid access mode for security'
        model_obj = self.pool.get(model_name)
        if hasattr(model_obj, 'table_query') \
                and model_obj.table_query():
            return False
        if Transaction().user == 0:
            return True
        ir_model_obj = self.pool.get('ir.model')
        user_group_obj = self.pool.get('res.user-res.group')
        cursor = Transaction().cursor
        cursor.execute('SELECT MAX(CASE WHEN a.perm_'+mode+' THEN 1 else 0 END) '
            'FROM ir_model_access a '
                'JOIN "' + ir_model_obj._table + '" m '
                    'ON (a.model = m.id) '
                'JOIN "' + user_group_obj._table + '" gu '
                    'ON (gu.gid = a."group") '
            'WHERE m.model = %s AND gu.uid = %s',
            (model_name, Transaction().user,))
        row = cursor.fetchall()
        if row[0][0] is None:
            cursor.execute('SELECT ' \
                        'MAX(CASE WHEN perm_' + mode + ' THEN 1 else 0 END) ' \
                    'FROM ir_model_access a ' \
                    'JOIN ir_model m ' \
                        'ON (a.model = m.id) ' \
                    'WHERE a."group" IS NULL AND m.model = %s', (model_name,))
            row = cursor.fetchall()
            if row[0][0] is None:
                return True

        if not row[0][0]:
            if raise_exception:
                self.raise_user_error(mode, model_name)
            else:
                return False
        return True

    def write(self, ids, vals):
        res = super(ModelAccess, self).write(ids, vals)
        # Restart the cache
        self.check.reset()
        for _, model in self.pool.iterobject():
            try:
                model.fields_view_get.reset()
            except Exception:
                pass
        return res

    def create(self, vals):
        res = super(ModelAccess, self).create(vals)
        # Restart the cache
        self.check.reset()
        for _, model in self.pool.iterobject():
            try:
                model.fields_view_get.reset()
            except Exception:
                pass
        return res

    def delete(self, ids):
        res = super(ModelAccess, self).delete(ids)
        # Restart the cache
        self.check.reset()
        for _, model in self.pool.iterobject():
            try:
                model.fields_view_get.reset()
            except Exception:
                pass
        return res

ModelAccess()


class ModelData(ModelSQL, ModelView):
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
    noupdate = fields.Boolean('No Update')

    def __init__(self):
        super(ModelData, self).__init__()
        self._sql_constraints = [
            ('fs_id_module_model_uniq', 'UNIQUE("fs_id", "module", "model")',
                'The triple (fs_id, module, model) must be unique!'),
        ]

    def default_date_init(self):
        return datetime.datetime.now()

    def default_inherit(self):
        return False

    def default_noupdate(self):
        return False

    def get_id(self, module, fs_id):
        """
        Return for an fs_id the corresponding db_id.

        :param module: the module name
        :param fs_id: the id in the xml file

        :return: the database id
        """
        ids = self.search([
            ('module', '=', module),
            ('fs_id', '=', fs_id),
            ('inherit', '=', False),
            ], limit=1)
        if not ids:
            raise Exception("Reference to %s not found" % \
                                ".".join([module,fs_id]))
        return self.read(ids[0], ['db_id'])['db_id']

ModelData()


class PrintModelGraphInit(ModelView):
    'Print Model Graph Init'
    _name = 'ir.model.print_model_graph.init'
    _description = __doc__
    level = fields.Integer('Level')
    filter = fields.Text('Filter', help="Entering a Python "
            "Regular Expression will exclude matching models from the graph.")

    def default_level(self):
        return 1

PrintModelGraphInit()


class PrintModelGraph(Wizard):
    _name = 'ir.model.print_model_graph'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'ir.model.print_model_graph.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('print', 'Print', 'tryton-ok', True),
                ],
            },
        },
        'print': {
            'result': {
                'type': 'print',
                'report': 'ir.model.graph',
                'state': 'end',
            },
        },
    }

PrintModelGraph()


class ModelGraph(Report):
    _name = 'ir.model.graph'

    def execute(self, ids, datas):
        import pydot
        model_obj = self.pool.get('ir.model')
        action_report_obj = self.pool.get('ir.action.report')

        if not datas['form']['filter']:
            filter = None
        else:
            filter = re.compile(datas['form']['filter'], re.VERBOSE)
        action_report_ids = action_report_obj.search([
            ('report_name', '=', self._name)
            ])
        if not action_report_ids:
            raise Exception('Error', 'Report (%s) not find!' % self._name)
        action_report = action_report_obj.browse(action_report_ids[0])

        models = model_obj.browse(ids)

        graph = pydot.Dot(fontsize="8")
        graph.set('center', '1')
        graph.set('ratio', 'auto')
        self.fill_graph(models, graph, level=datas['form']['level'],
                filter=filter)
        data = graph.create(prog='dot', format='png')
        return ('png', base64.encodestring(data), False, action_report.name)

    def fill_graph(self, models, graph, level=1, filter=None):
        '''
        Fills a pydot graph with a models structure.

        :param models: a BrowseRecordList of ir.model
        :param graph: a pydot.Graph
        :param level: the depth to dive into model reationships
        :param filter: a compiled regular expression object to filter specific
            models
        '''
        import pydot
        model_obj = self.pool.get('ir.model')

        sub_models = set()
        if level > 0:
            for model in models:
                for field in model.fields:
                    if field.name in ('create_uid', 'write_uid'):
                        continue
                    if field.relation and not graph.get_node(field.relation):
                        sub_models.add(field.relation)
            if sub_models:
                model_ids = model_obj.search([
                    ('model', 'in', list(sub_models)),
                    ])
                sub_models = model_obj.browse(model_ids)
                if set(sub_models) != set(models):
                    self.fill_graph(sub_models, graph, level=level - 1,
                            filter=filter)

        for model in models:
            if filter and re.search(filter, model.model):
                    continue
            label = '{' + model.model + '\\n'
            if model.fields:
                label += '|'
            for field in model.fields:
                if field.name in ('create_uid', 'write_uid',
                        'create_date', 'write_date', 'id'):
                    continue
                label += '+ ' + field.name + ': ' + field.ttype
                if field.relation:
                    label += ' ' + field.relation
                label += '\l'
            label += '}'
            if pydot.__version__ == '1.0.2':
                # version 1.0.2 doesn't quote correctly label on Node object
                label = '"' + label + '"'
            node = pydot.Node(str(model.model), shape='record', label=label)
            graph.add_node(node)

            for field in model.fields:
                if field.name in ('create_uid', 'write_uid'):
                    continue
                if field.relation:
                    node_name = field.relation
                    if pydot.__version__ == '1.0.2':
                        # version 1.0.2 doesn't quote correctly node name
                        node_name = '"' + node_name + '"'
                    if not graph.get_node(node_name):
                        continue
                    args = {}
                    tail = model.model
                    head = field.relation
                    edge_model_name = model.model
                    edge_relation_name = field.relation
                    if pydot.__version__ == '1.0.2':
                        # version 1.0.2 doesn't quote correctly edge name
                        edge_model_name = '"' + edge_model_name + '"'
                        edge_relation_name = '"' + edge_relation_name + '"'
                    if field.ttype == 'many2one':
                        edge = graph.get_edge(edge_model_name,
                                edge_relation_name)
                        if edge:
                            continue
                        args['arrowhead'] = "normal"
                    elif field.ttype == 'one2many':
                        edge = graph.get_edge(edge_relation_name,
                                edge_model_name)
                        if edge:
                            continue
                        args['arrowhead'] = "normal"
                        tail = field.relation
                        head = model.model
                    elif field.ttype == 'many2many':
                        if graph.get_edge(edge_model_name, edge_relation_name):
                            continue
                        if graph.get_edge(edge_relation_name, edge_model_name):
                            continue
                        args['arrowtail'] = "inv"
                        args['arrowhead'] = "inv"

                    edge = pydot.Edge(str(tail), str(head), **args)
                    graph.add_edge(edge)

ModelGraph()
