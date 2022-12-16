#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime
import re
import heapq

from ..model import ModelView, ModelSQL, fields
from ..report import Report
from ..wizard import Wizard, StateView, StateAction, Button
from ..transaction import Transaction
from ..cache import Cache
from ..pool import Pool
from ..pyson import Bool, Eval
from ..rpc import RPC
from ..backend import TableHandler
try:
    from ..tools.StringMatcher import StringMatcher
except ImportError:
    from difflib import SequenceMatcher as StringMatcher

__all__ = [
    'Model', 'ModelField', 'ModelAccess', 'ModelFieldAccess', 'ModelButton',
    'ModelData', 'PrintModelGraphStart', 'PrintModelGraph', 'ModelGraph',
    ]

IDENTIFIER = re.compile(r'^[a-zA-z_][a-zA-Z0-9_]*$')


class Model(ModelSQL, ModelView):
    "Model"
    __name__ = 'ir.model'
    name = fields.Char('Model Description', translate=True, loading='lazy',
        states={
            'readonly': Bool(Eval('module')),
            },
        depends=['module'])
    model = fields.Char('Model Name', required=True,
        states={
            'readonly': Bool(Eval('module')),
            },
        depends=['module'])
    info = fields.Text('Information',
        states={
            'readonly': Bool(Eval('module')),
            },
        depends=['module'])
    module = fields.Char('Module',
       help="Module in which this model is defined", readonly=True)
    global_search_p = fields.Boolean('Global Search')
    fields = fields.One2Many('ir.model.field', 'model', 'Fields',
       required=True)

    @classmethod
    def __setup__(cls):
        super(Model, cls).__setup__()
        cls._sql_constraints += [
            ('model_uniq', 'UNIQUE(model)',
                'The model must be unique!'),
            ]
        cls._error_messages.update({
                'invalid_module': ('Module name "%s" is not a valid python '
                    'identifier.'),
                })
        cls._order.insert(0, ('model', 'ASC'))
        cls.__rpc__.update({
                'list_models': RPC(),
                'global_search': RPC(),
                })

    @classmethod
    def validate(cls, models):
        super(Model, cls).validate(models)
        cls.check_module(models)

    @classmethod
    def check_module(cls, models):
        '''
        Check module
        '''
        for model in models:
            if model.module and not IDENTIFIER.match(model.module):
                cls.raise_user_error('invalid_module', (model.rec_name,))

    @classmethod
    def list_models(cls):
        'Return a list of all models names'
        with Transaction().set_user(0):
            models = cls.search([], order=[
                    ('module', 'ASC'),  # Optimization assumption
                    ('model', 'ASC'),
                    ('id', 'ASC'),
                    ])
            return [m.model for m in models]

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Property = pool.get('ir.property')
        res = super(Model, cls).create(vlist)
        # Restart the cache of models_get
        Property._models_get_cache.clear()
        return res

    @classmethod
    def write(cls, models, vals):
        pool = Pool()
        Property = pool.get('ir.property')
        super(Model, cls).write(models, vals)
        # Restart the cache of models_get
        Property._models_get_cache.clear()

    @classmethod
    def delete(cls, models):
        pool = Pool()
        Property = pool.get('ir.property')
        super(Model, cls).delete(models)
        # Restart the cache of models_get
        Property._models_get_cache.clear()

    @classmethod
    def global_search(cls, text, limit, menu='ir.ui.menu'):
        """
        Search on models for text including menu
        Returns a list of tuple (ratio, model, model_name, id, rec_name, icon)
        The size of the list is limited to limit
        """
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')

        if not limit > 0:
            raise ValueError('limit must be > 0: %r' % (limit,))

        models = cls.search(['OR',
                ('global_search_p', '=', True),
                ('model', '=', menu),
                ])
        access = ModelAccess.get_access([m.model for m in models])
        s = StringMatcher()
        if isinstance(text, str):
            text = text.decode('utf-8')
        s.set_seq2(text)

        def generate():
            for model in models:
                if not access[model.model]['read']:
                    continue
                Model = pool.get(model.model)
                if not hasattr(Model, 'search_global'):
                    continue
                for id_, rec_name, icon in Model.search_global(text):
                    if isinstance(rec_name, str):
                        rec_name = rec_name.decode('utf-8')
                    s.set_seq1(rec_name)
                    yield (s.ratio(), model.model, model.rec_name,
                        id_, rec_name, icon)
        return heapq.nlargest(int(limit), generate())


class ModelField(ModelSQL, ModelView):
    "Model field"
    __name__ = 'ir.model.field'
    name = fields.Char('Name', required=True,
        states={
            'readonly': Bool(Eval('module')),
            },
        depends=['module'])
    relation = fields.Char('Model Relation',
        states={
            'readonly': Bool(Eval('module')),
            },
        depends=['module'])
    model = fields.Many2One('ir.model', 'Model', required=True,
        select=True, ondelete='CASCADE',
        states={
            'readonly': Bool(Eval('module')),
            },
        depends=['module'])
    field_description = fields.Char('Field Description', translate=True,
        loading='lazy',
        states={
            'readonly': Bool(Eval('module')),
            },
        depends=['module'])
    ttype = fields.Char('Field Type',
        states={
            'readonly': Bool(Eval('module')),
            },
        depends=['module'])
    groups = fields.Many2Many('ir.model.field-res.group', 'field',
            'group', 'Groups')
    help = fields.Text('Help', translate=True, loading='lazy',
        states={
            'readonly': Bool(Eval('module')),
            },
        depends=['module'])
    module = fields.Char('Module',
       help="Module in which this field is defined")

    @classmethod
    def __setup__(cls):
        super(ModelField, cls).__setup__()
        cls._sql_constraints += [
            ('name_model_uniq', 'UNIQUE(name, model)',
                'The field name in model must be unique!'),
            ]
        cls._error_messages.update({
                'invalid_name': ('Model Field name "%s" is not a valid python '
                    'identifier.'),
                })
        cls._order.insert(0, ('name', 'ASC'))

    @staticmethod
    def default_name():
        return 'No Name'

    @staticmethod
    def default_field_description():
        return 'No description available'

    @classmethod
    def validate(cls, fields):
        super(ModelField, cls).validate(fields)
        cls.check_name(fields)

    @classmethod
    def check_name(cls, fields):
        '''
        Check name
        '''
        for field in fields:
            if not IDENTIFIER.match(field.name):
                cls.raise_user_error('invalid_name', (field.name,))

    @classmethod
    def read(cls, ids, fields_names=None):
        pool = Pool()
        Translation = pool.get('ir.translation')

        to_delete = []
        if Transaction().context.get('language'):
            if fields_names is None:
                fields_names = cls._fields.keys()

            if 'field_description' in fields_names \
                    or 'help' in fields_names:
                if 'model' not in fields_names:
                    fields_names.append('model')
                    to_delete.append('model')
                if 'name' not in fields_names:
                    fields_names.append('name')
                    to_delete.append('name')

        res = super(ModelField, cls).read(ids, fields_names=fields_names)

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
            cursor.execute('SELECT id, model FROM ir_model WHERE id IN '
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
            Translation.get_sources(trans_args)
            for rec in res:
                if isinstance(rec['model'], (list, tuple)):
                    model_id = rec['model'][0]
                else:
                    model_id = rec['model']
                if 'field_description' in fields_names:
                    res_trans = Translation.get_source(
                            id2model[model_id] + ',' + rec['name'],
                            'field', Transaction().language)
                    if res_trans:
                        rec['field_description'] = res_trans
                if 'help' in fields_names:
                    res_trans = Translation.get_source(
                            id2model[model_id] + ',' + rec['name'],
                            'help', Transaction().language)
                    if res_trans:
                        rec['help'] = res_trans

        if to_delete:
            for rec in res:
                for field in to_delete:
                    del rec[field]
        return res


class ModelAccess(ModelSQL, ModelView):
    "Model access"
    __name__ = 'ir.model.access'
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
    _get_access_cache = Cache('ir_model_access.get_access', context=False)

    @classmethod
    def __setup__(cls):
        super(ModelAccess, cls).__setup__()
        cls._error_messages.update({
            'read': 'You can not read this document! (%s)',
            'write': 'You can not write in this document! (%s)',
            'create': 'You can not create this kind of document! (%s)',
            'delete': 'You can not delete this document! (%s)',
            })
        cls.__rpc__.update({
                'get_access': RPC(),
                })

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor

        super(ModelAccess, cls).__register__(module_name)

        table = TableHandler(cursor, cls, module_name)

        # Migration from 2.6 (model, group) no more unique
        table.drop_constraint('model_group_uniq')

    @staticmethod
    def check_xml_record(accesses, values):
        return True

    @staticmethod
    def default_perm_read():
        return False

    @staticmethod
    def default_perm_write():
        return False

    @staticmethod
    def default_perm_create():
        return False

    @staticmethod
    def default_perm_delete():
        return False

    @classmethod
    def get_access(cls, models):
        'Return access for models'
        pool = Pool()
        Model = pool.get('ir.model')
        UserGroup = pool.get('res.user-res.group')
        cursor = Transaction().cursor
        user = Transaction().user

        access = {}
        for model in models:
            maccess = cls._get_access_cache.get((user, model), default=-1)
            if maccess == -1:
                break
            access[model] = maccess
        else:
            return access

        default = {'read': True, 'write': True, 'create': True, 'delete': True}
        access = dict((m, default) for m in models)
        cursor.execute(('SELECT '
                    'm.model, '
                    'MAX(CASE WHEN a.perm_read THEN 1 ELSE 0 END), '
                    'MAX(CASE WHEN a.perm_write THEN 1 ELSE 0 END), '
                    'MAX(CASE WHEN a.perm_create THEN 1 ELSE 0 END), '
                    'MAX(CASE WHEN a.perm_delete THEN 1 ELSE 0 END) '
                'FROM "%s" AS a '
                'JOIN "%s" AS m '
                    'ON (a.model = m.id) '
                'LEFT JOIN "%s" AS gu '
                    'ON (gu."group" = a."group") '
                'WHERE m.model IN (' + ','.join(('%%s',) * len(models)) + ') '
                    'AND (gu."user" = %%s OR a."group" IS NULL) '
                'GROUP BY m.model')
            % (cls._table, Model._table, UserGroup._table),
            list(models) + [Transaction().user])
        access.update(dict(
                (m, {'read': r, 'write': w, 'create': c, 'delete': d})
                for m, r, w, c, d in cursor.fetchall()))
        for model, maccess in access.iteritems():
            cls._get_access_cache.set((user, model), maccess)
        return access

    @classmethod
    def check(cls, model_name, mode='read', raise_exception=True):
        'Check access for model_name and mode'
        assert mode in ['read', 'write', 'create', 'delete'], \
            'Invalid access mode for security'
        if Transaction().user == 0:
            return True

        access = cls.get_access([model_name])[model_name][mode]
        if not access and access is not None:
            if raise_exception:
                cls.raise_user_error(mode, model_name)
            else:
                return False
        return True

    @classmethod
    def write(cls, accesses, vals):
        super(ModelAccess, cls).write(accesses, vals)
        # Restart the cache
        cls._get_access_cache.clear()
        ModelView._fields_view_get_cache.clear()

    @classmethod
    def create(cls, vlist):
        res = super(ModelAccess, cls).create(vlist)
        # Restart the cache
        cls._get_access_cache.clear()
        ModelView._fields_view_get_cache.clear()
        return res

    @classmethod
    def delete(cls, accesses):
        super(ModelAccess, cls).delete(accesses)
        # Restart the cache
        cls._get_access_cache.clear()
        ModelView._fields_view_get_cache.clear()


class ModelFieldAccess(ModelSQL, ModelView):
    "Model Field Access"
    __name__ = 'ir.model.field.access'
    _rec_name = 'field'
    field = fields.Many2One('ir.model.field', 'Field', required=True,
            ondelete='CASCADE')
    group = fields.Many2One('res.group', 'Group', ondelete='CASCADE')
    perm_read = fields.Boolean('Read Access')
    perm_write = fields.Boolean('Write Access')
    perm_create = fields.Boolean('Create Access')
    perm_delete = fields.Boolean('Delete Access')
    description = fields.Text('Description')
    _get_access_cache = Cache('ir_model_field_access.check')

    @classmethod
    def __setup__(cls):
        super(ModelFieldAccess, cls).__setup__()
        cls._error_messages.update({
            'read': 'You can not read the field! (%s.%s)',
            'write': 'You can not write on the field! (%s.%s)',
            })

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor

        super(ModelFieldAccess, cls).__register__(module_name)

        table = TableHandler(cursor, cls, module_name)

        # Migration from 2.6 (field, group) no more unique
        table.drop_constraint('field_group_uniq')

    @staticmethod
    def check_xml_record(field_accesses, values):
        return True

    @staticmethod
    def default_perm_read():
        return False

    @staticmethod
    def default_perm_write():
        return False

    @staticmethod
    def default_perm_create():
        return True

    @staticmethod
    def default_perm_delete():
        return True

    @classmethod
    def get_access(cls, models):
        'Return fields access for models'
        pool = Pool()
        Model = pool.get('ir.model')
        ModelField = pool.get('ir.model.field')
        cursor = Transaction().cursor
        user = Transaction().user

        accesses = {}
        for model in models:
            maccesses = cls._get_access_cache.get((user, model))
            if maccesses is None:
                break
            accesses[model] = maccesses
        else:
            return accesses

        default = {}
        accesses = dict((m, default) for m in models)
        cursor.execute(('SELECT '
                    'm.model, '
                    'f.name, '
                    'MAX(CASE WHEN a.perm_read THEN 1 ELSE 0 END), '
                    'MAX(CASE WHEN a.perm_write THEN 1 ELSE 0 END), '
                    'MAX(CASE WHEN a.perm_create THEN 1 ELSE 0 END), '
                    'MAX(CASE WHEN a.perm_delete THEN 1 ELSE 0 END) '
                'FROM "%s" AS a '
                'JOIN "%s" AS f '
                    'ON (a.field = f.id) '
                'JOIN "%s" AS m '
                    'ON (f.model = m.id) '
                'LEFT JOIN "res_user-res_group" AS gu '
                    'ON (gu."group" = a."group") '
                'WHERE m.model IN (' + ','.join(('%%s',) * len(models)) + ') '
                    'AND (gu."user" = %%s OR a."group" IS NULL) '
                'GROUP BY m.model, f.name')
            % (cls._table, ModelField._table, Model._table),
            list(models) + [Transaction().user])
        for m, f, r, w, c, d in cursor.fetchall():
            accesses[m][f] = {'read': r, 'write': w, 'create': c, 'delete': d}
        for model, maccesses in accesses.iteritems():
            cls._get_access_cache.set((user, model), maccesses)
        return accesses

    @classmethod
    def check(cls, model_name, fields, mode='read', raise_exception=True,
            access=False):
        '''
        Check access for fields on model_name.
        '''
        assert mode in ('read', 'write', 'create', 'delete'), \
            'Invalid access mode'
        if Transaction().user == 0:
            if access:
                return dict((x, True) for x in fields)
            return True

        accesses = dict((f, a[mode])
            for f, a in cls.get_access([model_name])[model_name].iteritems())
        if access:
            return accesses
        for field in fields:
            if not accesses.get(field, True):
                if raise_exception:
                    cls.raise_user_error(mode, (model_name, field))
                else:
                    return False
        return True

    @classmethod
    def write(cls, field_accesses, vals):
        super(ModelFieldAccess, cls).write(field_accesses, vals)
        # Restart the cache
        cls._get_access_cache.clear()
        ModelView._fields_view_get_cache.clear()

    @classmethod
    def create(cls, vlist):
        res = super(ModelFieldAccess, cls).create(vlist)
        # Restart the cache
        cls._get_access_cache.clear()
        ModelView._fields_view_get_cache.clear()
        return res

    @classmethod
    def delete(cls, field_accesses):
        super(ModelFieldAccess, cls).delete(field_accesses)
        # Restart the cache
        cls._get_access_cache.clear()
        ModelView._fields_view_get_cache.clear()


class ModelButton(ModelSQL, ModelView):
    "Model Button"
    __name__ = 'ir.model.button'
    name = fields.Char('Name', required=True, readonly=True)
    model = fields.Many2One('ir.model', 'Model', required=True, readonly=True,
        ondelete='CASCADE', select=True)
    groups = fields.Many2Many('ir.model.button-res.group', 'button', 'group',
        'Groups')
    _groups_cache = Cache('ir.model.button.groups')

    @classmethod
    def __setup__(cls):
        super(ModelButton, cls).__setup__()
        cls._sql_constraints += [
            ('name_model_uniq', 'UNIQUE(name, model)',
                'The button name in model must be unique!'),
            ]
        cls._order.insert(0, ('model', 'ASC'))

    @classmethod
    def create(cls, vlist):
        result = super(ModelButton, cls).create(vlist)
        # Restart the cache for get_groups
        cls._groups_cache.clear()
        return result

    @classmethod
    def write(cls, buttons, values):
        super(ModelButton, cls).write(buttons, values)
        # Restart the cache for get_groups
        cls._groups_cache.clear()

    @classmethod
    def delete(cls, buttons):
        super(ModelButton, cls).delete(buttons)
        # Restart the cache for get_groups
        cls._groups_cache.clear()

    @classmethod
    def get_groups(cls, model, name):
        '''
        Return a set of group ids for the named button on the model.
        '''
        key = (model, name)
        groups = cls._groups_cache.get(key)
        if groups is not None:
            return groups
        buttons = cls.search([
                ('model.model', '=', model),
                ('name', '=', name),
                ])
        if not buttons:
            groups = set()
        else:
            button, = buttons
            groups = set(g.id for g in button.groups)
        cls._groups_cache.set(key, groups)
        return groups


class ModelData(ModelSQL, ModelView):
    "Model data"
    __name__ = 'ir.model.data'
    fs_id = fields.Char('Identifier on File System', required=True,
        help="The id of the record as known on the file system.",
        select=True)
    model = fields.Char('Model', required=True, select=True)
    module = fields.Char('Module', required=True, select=True)
    db_id = fields.Integer('Resource ID',
        help="The id of the record in the database.", select=True,
        required=True)
    date_update = fields.DateTime('Update Date')
    date_init = fields.DateTime('Init Date')
    values = fields.Text('Values')
    noupdate = fields.Boolean('No Update')
    _get_id_cache = Cache('ir_model_data.get_id', context=False)

    @classmethod
    def __setup__(cls):
        super(ModelData, cls).__setup__()
        cls._sql_constraints = [
            ('fs_id_module_model_uniq', 'UNIQUE("fs_id", "module", "model")',
                'The triple (fs_id, module, model) must be unique!'),
        ]

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor

        super(ModelData, cls).__register__(module_name)

        table = TableHandler(cursor, cls, module_name)

        # Migration from 2.6: remove inherit
        if table.column_exist('inherit'):
            cursor.execute('DELETE FROM "' + cls._table + '" '
                'WHERE inherit = %s', (True,))
            table.drop_column('inherit', True)

    @staticmethod
    def default_date_init():
        return datetime.datetime.now()

    @staticmethod
    def default_noupdate():
        return False

    @classmethod
    def write(cls, data, values):
        super(ModelData, cls).write(data, values)
        # Restart the cache for get_id
        cls._get_id_cache.clear()

    @classmethod
    def get_id(cls, module, fs_id):
        """
        Return for an fs_id the corresponding db_id.
        """
        key = (module, fs_id)
        id_ = cls._get_id_cache.get(key)
        if id_ is not None:
            return id_
        data = cls.search([
            ('module', '=', module),
            ('fs_id', '=', fs_id),
            ], limit=1)
        if not data:
            raise Exception("Reference to %s not found"
                % ".".join([module, fs_id]))
        id_ = cls.read([d.id for d in data], ['db_id'])[0]['db_id']
        cls._get_id_cache.set(key, id_)
        return id_


class PrintModelGraphStart(ModelView):
    'Print Model Graph'
    __name__ = 'ir.model.print_model_graph.start'
    level = fields.Integer('Level', required=True)
    filter = fields.Text('Filter', help="Entering a Python "
            "Regular Expression will exclude matching models from the graph.")

    @staticmethod
    def default_level():
        return 1


class PrintModelGraph(Wizard):
    __name__ = 'ir.model.print_model_graph'

    start = StateView('ir.model.print_model_graph.start',
        'ir.print_model_graph_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-ok', default=True),
            ])
    print_ = StateAction('ir.report_model_graph')

    def transition_print_(self):
        return 'end'

    def do_print_(self, action):
        return action, {
            'id': Transaction().context.get('active_id'),
            'ids': Transaction().context.get('active_ids'),
            'level': self.start.level,
            'filter': self.start.filter,
            }


class ModelGraph(Report):
    __name__ = 'ir.model.graph'

    @classmethod
    def execute(cls, ids, data):
        import pydot
        pool = Pool()
        Model = pool.get('ir.model')
        ActionReport = pool.get('ir.action.report')

        if not data['filter']:
            filter = None
        else:
            filter = re.compile(data['filter'], re.VERBOSE)
        action_report_ids = ActionReport.search([
            ('report_name', '=', cls.__name__)
            ])
        if not action_report_ids:
            raise Exception('Error', 'Report (%s) not find!' % cls.__name__)
        action_report = ActionReport(action_report_ids[0])

        models = Model.browse(ids)

        graph = pydot.Dot(fontsize="8")
        graph.set('center', '1')
        graph.set('ratio', 'auto')
        cls.fill_graph(models, graph, level=data['level'], filter=filter)
        data = graph.create(prog='dot', format='png')
        return ('png', buffer(data), False, action_report.name)

    @classmethod
    def fill_graph(cls, models, graph, level=1, filter=None):
        '''
        Fills a pydot graph with a models structure.
        '''
        import pydot
        pool = Pool()
        Model = pool.get('ir.model')

        sub_models = set()
        if level > 0:
            for model in models:
                for field in model.fields:
                    if field.name in ('create_uid', 'write_uid'):
                        continue
                    if field.relation and not graph.get_node(field.relation):
                        sub_models.add(field.relation)
            if sub_models:
                model_ids = Model.search([
                    ('model', 'in', list(sub_models)),
                    ])
                sub_models = Model.browse(model_ids)
                if set(sub_models) != set(models):
                    cls.fill_graph(sub_models, graph, level=level - 1,
                            filter=filter)

        for model in models:
            if filter and re.search(filter, model.model):
                    continue
            label = '"{' + model.model + '\\n'
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
            label += '}"'
            node_name = '"%s"' % model.model
            node = pydot.Node(node_name, shape='record', label=label)
            graph.add_node(node)

            for field in model.fields:
                if field.name in ('create_uid', 'write_uid'):
                    continue
                if field.relation:
                    node_name = '"%s"' % field.relation
                    if not graph.get_node(node_name):
                        continue
                    args = {}
                    tail = model.model
                    head = field.relation
                    edge_model_name = '"%s"' % model.model
                    edge_relation_name = '"%s"' % field.relation
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
