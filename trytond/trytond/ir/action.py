#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Action"
from trytond.model import ModelView, ModelSQL, ModelStorage, fields
from trytond.tools import file_open, Cache, safe_eval
from trytond.backend import TableHandler
from trytond.pyson import PYSONEncoder, CONTEXT, PYSON
import base64
import os


class Action(ModelSQL, ModelView):
    "Action"
    _name = 'ir.action'
    _description = __doc__
    name = fields.Char('Name', required=True, translate=True)
    type = fields.Char('Type', required=True, readonly=True)
    usage = fields.Char('Usage')
    keywords = fields.One2Many('ir.action.keyword', 'action',
            'Keywords')
    groups = fields.Many2Many('ir.action-res.group', 'action_id', 'gid',
            'Groups')
    active = fields.Boolean('Active', select=2)

    def __init__(self):
        super(Action, self).__init__()
        self._rpc.update({
            'get_action_id': False,
        })

    def default_usage(self, cursor, user, context=None):
        return False

    def default_active(self, cursor, user, context=None):
        return True

    def get_action_id(self, cursor, user, action_id, context=None):
        if context is None:
            context = {}
        ctx = context.copy()
        ctx['active_test'] = False
        if self.search(cursor, user, [
            ('id', '=', action_id),
            ], context=ctx):
            return action_id
        for action_type in (
                'ir.action.report',
                'ir.action.act_window',
                'ir.action.wizard',
                'ir.action.url',
                ):
            action_obj = self.pool.get(action_type)
            action_id2 = action_obj.search(cursor, user, [
                ('id', '=', action_id),
                ], context=ctx)
            if action_id2:
                action = action_obj.browse(cursor, user, action_id2[0],
                        context=context)
                return action.action.id
        return False

Action()


class ActionKeyword(ModelSQL, ModelView):
    "Action keyword"
    _name = 'ir.action.keyword'
    _description = __doc__
    keyword = fields.Selection([
            ('tree_open', 'Open tree'),
            ('tree_action', 'Action tree'),
            ('form_print', 'Print form'),
            ('form_action', 'Action form'),
            ('form_relate', 'Form relate'),
            ('graph_open', 'Open Graph'),
            ], string='Keyword', required=True)
    model = fields.Reference('Model', selection='models_get')
    action = fields.Many2One('ir.action', 'Action',
            ondelete='CASCADE')

    def __init__(self):
        super(ActionKeyword, self).__init__()
        self._rpc.update({'get_keyword': False})
        self._constraints += [
            ('check_wizard_model', 'wrong_wizard_model'),
        ]
        self._error_messages.update({
            'wrong_wizard_model': 'Wrong wizard model!',
        })

    def check_wizard_model(self, cursor, user, ids):
        action_wizard_obj = self.pool.get('ir.action.wizard')
        for action_keyword in self.browse(cursor, user, ids):
            if action_keyword.action.type == 'ir.action.wizard':
                action_wizard_id = action_wizard_obj.search(cursor, user, [
                    ('action', '=', action_keyword.action.id),
                    ], limit=1)[0]
                action_wizard = action_wizard_obj.browse(cursor, user,
                        action_wizard_id)
                if action_wizard.model:
                    model, record_id = action_keyword.model.split(',', 1)
                    if model != action_wizard.model:
                        return False
        return True

    def _convert_vals(self, cursor, user, vals, context=None):
        vals = vals.copy()
        action_obj = self.pool.get('ir.action')
        if 'action' in vals:
            vals['action'] = action_obj.get_action_id(cursor, user,
                    vals['action'], context=context)
        return vals

    def models_get(self, cursor, user, context=None):
        model_obj = self.pool.get('ir.model')
        model_ids = model_obj.search(cursor, user, [], context=context)
        res = []
        for model in model_obj.browse(cursor, user, model_ids,
                context=context):
            res.append([model.model, model.name])
        return res

    def delete(self, cursor, user, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        for keyword in self.browse(cursor, user, ids, context=context):
            # Restart the cache view
            try:
                self.pool.get(keyword.model.split(',')[0])\
                        .fields_view_get(cursor.dbname)
            except:
                pass
        return super(ActionKeyword, self).delete(cursor, user, ids,
                context=context)

    def create(self, cursor, user, vals, context=None):
        vals = self._convert_vals(cursor, user, vals, context=context)
        if 'model' in vals:
            # Restart the cache view
            try:
                self.pool.get(vals['model'].split(',')[0])\
                        .fields_view_get(cursor.dbname)
            except:
                pass
        return super(ActionKeyword, self).create(cursor, user, vals,
                context=context)

    def write(self, cursor, user, ids, vals, context=None):
        vals = self._convert_vals(cursor, user, vals, context=context)
        if isinstance(ids, (int, long)):
            ids = [ids]
        for keyword in self.browse(cursor, user, ids, context=context):
            # Restart the cache view
            try:
                self.pool.get(keyword.model.split(',')[0])\
                        .fields_view_get(cursor.dbname)
            except:
                pass
        res = super(ActionKeyword, self).write(cursor, user, ids, vals,
                context=context)
        for keyword in self.browse(cursor, user, ids, context=context):
            # Restart the cache view
            try:
                self.pool.get(keyword.model.split(',')[0])\
                        .fields_view_get(cursor.dbname)
            except:
                pass
        return res

    def get_keyword(self, cursor, user, keyword, value, context=None):
        res = []
        model, model_id = value

        action_keyword_ids = []
        if model_id:
            action_keyword_ids = self.search(cursor, user, [
                ('keyword', '=', keyword),
                ('model', '=', model + ',' + str(model_id)),
                ], context=context)
        action_keyword_ids.extend(self.search(cursor, user, [
            ('keyword', '=', keyword),
            ('model', '=', model + ',0'),
            ], context=context))
        encoder = PYSONEncoder()
        for action_keyword_id in action_keyword_ids:
            action_keyword = self.browse(cursor, user, action_keyword_id,
                context=context)
            try:
                action_obj = self.pool.get(action_keyword.action.type)
            except:
                continue
            action_id = action_obj.search(cursor, user, [
                ('action', '=', action_keyword.action.id),
                ], context=context)
            if action_id:
                res.append(action_obj.read(cursor, user, action_id[0],
                    context=context))
                if action_keyword.action.type == 'ir.action.report':
                    del res[-1]['report_content_data']
                    del res[-1]['report_content']
                    del res[-1]['style_content']
                    res[-1]['email'] = encoder.encode(safe_eval(res[-1]['email']
                        or '{}', CONTEXT))
                elif action_keyword.action.type == 'ir.action.act_window':
                    for field in ('domain', 'context', 'search_value'):
                        del res[-1][field]
        return res

ActionKeyword()


class ActionReport(ModelSQL, ModelView):
    "Action report"
    _name = 'ir.action.report'
    _description = __doc__
    _inherits = {'ir.action': 'action'}
    model = fields.Char('Model')
    report_name = fields.Char('Internal Name', required=True)
    report = fields.Char('Path')
    report_content_data = fields.Binary('Content')
    report_content = fields.Function(fields.Binary('Content'),
            'get_report_content', setter='set_report_content')
    action = fields.Many2One('ir.action', 'Action', required=True,
            ondelete='CASCADE')
    style = fields.Property(fields.Char('Style',
            help='Define the style to apply on the report.'))
    style_content = fields.Function(fields.Binary('Style'),
            'get_style_content')
    direct_print = fields.Boolean('Direct Print')
    extension = fields.Selection(
        [('odt', 'ODT Document'),
         ('pdf', 'PDF Document'),],
        string='Extension', required=True)
    module = fields.Char('Module', readonly=True, select=1)
    email = fields.Char('Email')

    def __init__(self):
        super(ActionReport, self).__init__()
        self._sql_constraints += [
            ('report_name_module_uniq', 'UNIQUE(report_name, module)',
                'The internal name must be unique by module!'),
        ]

    def init(self, cursor, module_name):
        super(ActionReport, self).init(cursor, module_name)

        table = TableHandler(cursor, self, module_name)

        # Migration from 1.0 report_name_uniq has been removed
        table.drop_constraint('report_name_uniq')

        # Migration from 1.0 output_format (m2o) is now extension (selection)
        if table.column_exist('output_format'):
            cursor.execute(
                'SELECT report.id FROM "'+ self._table + '" report '\
                'JOIN ir_action_report_outputformat of '\
                    'ON (report.output_format = of.id) '\
                'WHERE of.format = \'pdf\''
                )

            ids = [x[0] for x in cursor.fetchall()]
            self.write(cursor, 0, ids, {'extension': 'pdf'})
            ids = self.search(cursor, 0, [('id', 'not in', ids)])
            self.write(cursor, 0, ids, {'extension': 'odt'})

            table.drop_column("output_format")
            TableHandler.dropTable(cursor, 'ir.action.report.outputformat',
                      'ir_action_report_outputformat')

    def default_type(self, cursor, user, context=None):
        return 'ir.action.report'

    def default_report_content(self, cursor, user, context=None):
        return False

    def default_direct_print(self, cursor, user, context=None):
        return False

    def default_extension(self, cursor, user, context=None):
        return 'odt'

    def default_module(self, cursor, user, context=None):
        return context and context.get('module', '') or ''

    def get_report_content(self, cursor, user, ids, name, context=None):
        res = {}
        for report in self.browse(cursor, user, ids, context=context):
            data = report[name + '_data']
            if not data and report[name[:-8]]:
                try:
                    data = base64.encodestring(file_open(
                        report[name[:-8]].replace('/', os.sep),
                        mode='rb').read())
                except:
                    data = False
            res[report.id] = data
        return res

    def set_report_content(self, cursor, user, ids, name, value,
            context=None):
        self.write(cursor, user, ids, {'%s_data' % name: value},
                context=context)

    def get_style_content(self, cursor, user, ids, name, context=None):
        res = {}
        for report in self.browse(cursor, user, ids, context=context):
            try:
                data = base64.encodestring(file_open(
                    report.style.replace('/', os.sep),
                    mode='rb').read())
            except:
                data = False
            res[report.id] = data
        return res

    def copy(self, cursor, user, ids, default=None, context=None):
        if default is None:
            default = {}

        int_id = False
        if isinstance(ids, (int, long)):
            int_id = True
            ids = [ids]

        new_ids = []
        reports = self.browse(cursor, user, ids, context=context)
        for report in reports:
            if report.report:
                default['report_content'] = False
            default['report_name'] = report.report_name
            new_ids.append(super(ActionReport, self).copy(cursor, user,
                report.id, default=default, context=context))
        if int_id:
            return new_ids[0]
        return new_ids

    def create(self, cursor, user, vals, context=None):
        later = {}
        vals = vals.copy()
        for field in vals:
            if field in self._columns \
                    and hasattr(self._columns[field], 'set'):
                later[field] = vals[field]
        for field in later:
            del vals[field]
        if cursor.nextid(self._table):
            cursor.setnextid(self._table, cursor.currid('ir_action'))
        new_id = super(ActionReport, self).create(cursor, user, vals,
                context=context)
        report = self.browse(cursor, user, new_id, context=context)
        new_id = report.action.id
        cursor.execute('UPDATE "' + self._table + '" SET id = %s ' \
                'WHERE id = %s', (report.action.id, report.id))
        cursor.update_auto_increment(self._table, report.action.id)
        ModelStorage.delete(self, cursor, user, report.id)
        self.write(cursor, user, new_id, later, context=context)
        return new_id

    def write(self, cursor, user, ids, vals, context=None):
        if context is None:
            context = {}

        if 'module' in context:
            vals = vals.copy()
            vals['module'] = context['module']

        return super(ActionReport, self).write(cursor, user, ids, vals,
                context=context)

    def delete(self, cursor, user, ids, context=None):
        action_obj = self.pool.get('ir.action')

        if isinstance(ids, (int, long)):
            ids = [ids]
        action_ids = [x.action.id for x in self.browse(cursor, user, ids,
            context=context)]

        res = super(ActionReport, self).delete(cursor, user, ids,
                context=context)
        action_obj.delete(cursor, user, action_ids, context=context)
        return res

ActionReport()


class ActionActWindow(ModelSQL, ModelView):
    "Action act window"
    _name = 'ir.action.act_window'
    _description = __doc__
    _inherits = {'ir.action': 'action'}
    domain = fields.Char('Domain Value')
    context = fields.Char('Context Value')
    res_model = fields.Char('Model')
    view_type = fields.Selection([
        ('tree','Tree'),
        ('form','Form'),
        ('board', 'Board'),
        ], string='Type of view')
    act_window_views = fields.One2Many('ir.action.act_window.view',
            'act_window', 'Views')
    views = fields.Function(fields.Binary('Views'), 'get_views')
    limit = fields.Integer('Limit',
            help='Default limit for the list view')
    auto_refresh = fields.Integer('Auto-Refresh',
            help='Add an auto-refresh on the view')
    action = fields.Many2One('ir.action', 'Action', required=True,
            ondelete='CASCADE')
    window_name = fields.Boolean('Window Name',
            help='Use the action name as window name')
    search_value = fields.Char('Search Criteria',
            help='Default search criteria for the list view')
    pyson_domain = fields.Function(fields.Char('PySON Domain'), 'get_pyson')
    pyson_context = fields.Function(fields.Char('PySON Context'),
            'get_pyson')
    pyson_search_value = fields.Function(fields.Char(
        'PySON Search Criteria'), 'get_pyson')

    def __init__(self):
        super(ActionActWindow, self).__init__()
        self._constraints += [
            ('check_domain', 'invalid_domain'),
            ('check_context', 'invalid_context'),
            ('check_search_value', 'invalid_search_value'),
        ]
        self._error_messages.update({
            'invalid_domain': 'Invalid domain!',
            'invalid_context': 'Invalid context!',
            'invalid_search_value': 'Invalid search criteria!',
        })

    def default_type(self, cursor, user, context=None):
        return 'ir.action.act_window'

    def default_view_type(self, cursor, user, context=None):
        return 'form'

    def default_context(self, cursor, user, context=None):
        return '{}'

    def default_limit(self, cursor, user, context=None):
        return 0

    def default_auto_refresh(self, cursor, user, context=None):
        return 0

    def default_window_name(self, cursor, user, context=None):
        return True

    def default_search_value(self, cursor, user, context=None):
        return '{}'

    def check_domain(self, cursor, user, ids):
        "Check domain"
        for action in self.browse(cursor, user, ids):
            if action.domain:
                try:
                    value = safe_eval(action.domain, CONTEXT)
                except:
                    return False
                if isinstance(value, PYSON):
                    if not value.types() == set([list]):
                        return False
                elif not isinstance(value, list):
                    return False
                else:
                    try:
                        fields.domain_validate(value)
                    except:
                        return False
        return True

    def check_context(self, cursor, user, ids):
        "Check context"
        for action in self.browse(cursor, user, ids):
            if action.context:
                try:
                    value = safe_eval(action.context, CONTEXT)
                except:
                    return False
                if isinstance(value, PYSON):
                    if not value.types() == set([dict]):
                        return False
                elif not isinstance(value, dict):
                    return False
                else:
                    try:
                        fields.context_validate(value)
                    except:
                        return False
        return True

    def check_search_value(self, cursor, user, ids):
        "Check search_value"
        for action in self.browse(cursor, user, ids):
            if action.search_value:
                try:
                    value = safe_eval(action.search_value, CONTEXT)
                except:
                    return False
                if isinstance(value, PYSON):
                    if not value.types() == set([dict]):
                        return False
                elif not isinstance(value, dict):
                    return False
        return True

    def get_views(self, cursor, user, ids, name, context=None):
        res = {}
        for act in self.browse(cursor, user, ids, context=context):
            res[act.id] = [(view.view.id, view.view.type) \
                    for view in act.act_window_views]
        return res

    def get_pyson(self, cursor, user, ids, name, context=None):
        res = {}
        encoder = PYSONEncoder()
        field = name[6:]
        defaults = {
            'domain': '[]',
            'context': '{}',
            'search_value': '{}',
        }
        for act in self.browse(cursor, user, ids, context=context):
            res[act.id] = encoder.encode(safe_eval(act[field] or
                defaults.get(field, 'False'), CONTEXT))
        return res

    def create(self, cursor, user, vals, context=None):
        later = {}
        vals = vals.copy()
        for field in vals:
            if field in self._columns \
                    and hasattr(self._columns[field], 'set'):
                later[field] = vals[field]
        for field in later:
            del vals[field]
        if cursor.nextid(self._table):
            cursor.setnextid(self._table, cursor.currid('ir_action'))
        new_id = super(ActionActWindow, self).create(cursor, user, vals,
                context=context)
        act_window = self.browse(cursor, user, new_id, context=context)
        new_id = act_window.action.id
        cursor.execute('UPDATE "' + self._table + '" SET id = %s ' \
                'WHERE id = %s', (act_window.action.id, act_window.id))
        cursor.update_auto_increment(self._table, act_window.action.id)
        ModelStorage.delete(self, cursor, user, act_window.id)
        self.write(cursor, user, new_id, later, context=context)
        return new_id

    def delete(self, cursor, user, ids, context=None):
        action_obj = self.pool.get('ir.action')

        if isinstance(ids, (int, long)):
            ids = [ids]
        action_ids = [x.action.id for x in self.browse(cursor, user, ids,
            context=context)]

        res = super(ActionActWindow, self).delete(cursor, user, ids,
                context=context)
        action_obj.delete(cursor, user, action_ids, context=context)
        return res

ActionActWindow()


class ActionActWindowView(ModelSQL, ModelView):
    "Action act window view"
    _name = 'ir.action.act_window.view'
    _rec_name = 'view'
    _description = __doc__
    sequence = fields.Integer('Sequence')
    view = fields.Many2One('ir.ui.view', 'View', required=True,
            ondelete='CASCADE')
    act_window = fields.Many2One('ir.action.act_window', 'Action',
            ondelete='CASCADE')

    def __init__(self):
        super(ActionActWindowView, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))

    def init(self, cursor, module_name):
        super(ActionActWindowView, self).init(cursor, module_name)
        table = TableHandler(cursor, self, module_name)

        # Migration from 1.0 remove multi
        table.drop_column('multi')

ActionActWindowView()


class ActionWizard(ModelSQL, ModelView):
    "Action wizard"
    _name = 'ir.action.wizard'
    _description = __doc__
    _inherits = {'ir.action': 'action'}
    wiz_name = fields.Char('Wizard name', required=True)
    action = fields.Many2One('ir.action', 'Action', required=True,
            ondelete='CASCADE')
    model = fields.Char('Model')
    email = fields.Char('Email')
    window = fields.Boolean('Window', help='Run wizard in a new window')

    def default_type(self, cursor, user, context=None):
        return 'ir.action.wizard'

    def create(self, cursor, user, vals, context=None):
        later = {}
        vals = vals.copy()
        for field in vals:
            if field in self._columns \
                    and hasattr(self._columns[field], 'set'):
                later[field] = vals[field]
        for field in later:
            del vals[field]
        if cursor.nextid(self._table):
            cursor.setnextid(self._table, cursor.currid('ir_action'))
        new_id = super(ActionWizard, self).create(cursor, user, vals,
                context=context)
        wizard = self.browse(cursor, user, new_id, context=context)
        new_id = wizard.action.id
        cursor.execute('UPDATE "' + self._table + '" SET id = %s ' \
                'WHERE id = %s', (wizard.action.id, wizard.id))
        cursor.update_auto_increment(self._table, wizard.action.id)
        ModelStorage.delete(self, cursor, user, wizard.id)
        self.write(cursor, user, new_id, later, context=context)
        return new_id

    def delete(self, cursor, user, ids, context=None):
        action_obj = self.pool.get('ir.action')

        if isinstance(ids, (int, long)):
            ids = [ids]
        action_ids = [x.action.id for x in self.browse(cursor, user, ids,
            context=context)]

        res = super(ActionWizard, self).delete(cursor, user, ids,
                context=context)
        action_obj.delete(cursor, user, action_ids, context=context)
        return res

ActionWizard()


class ActionWizardSize(ModelSQL, ModelView):
    "Action Wizard Size"
    _name = 'ir.action.wizard_size'
    _description = __doc__
    wizard = fields.Char('Wizard', required=True, select=1)
    model = fields.Char('Model', required=True, select=1)
    user = fields.Many2One('res.user', 'User', required=True,
            ondelete='CASCADE', select=1)
    width = fields.Integer('Width')
    height = fields.Integer('Height')

    def __init__(self):
        super(ActionWizardSize, self).__init__()
        self._rpc.update({
            'set_size': True,
        })

    def create(self, cursor, user, vals, context=None):
        res = super(ActionWizardSize, self).create(cursor, user, vals,
                context=context)
        # Restart the cache for get_size
        self.get_size(cursor.dbname)
        return res

    def write(self, cursor, user, ids, vals, context=None):
        res = super(ActionWizardSize, self).write(cursor, user, ids,
                vals, context=context)
        # Restart the cache for get_size
        self.get_size(cursor.dbname)
        return res

    def delete(self, cursor, user, ids, context=None):
        res = super(ActionWizardSize, self).delete(cursor, user, ids,
                context=context)
        # Restart the cache for get_size
        self.get_size(cursor.dbname)
        return res

    def set_size(self, cursor, user, wizard, model, width, height,
            context=None):
        '''
        Set size for wizard dialog.
        :param cursor: the database cursor
        :param user: the user id
        :param wizard: the wizard name
        :param model: the model name
        :param width: the width
        :param height: the height
        :param context: the context
        '''
        ids = self.search(cursor, user, [
            ('user', '=', user),
            ('wizard', '=', wizard),
            ('model', '=', model),
            ], context=context)
        if ids:
            self.write(cursor, user, ids, {
                'width': width,
                'height': height,
                }, context=context)
        else:
            self.create(cursor, user, {
                'wizard': wizard,
                'model': model,
                'user': user,
                'width': width,
                'height': height,
                }, context=context)

    @Cache('ir.action.wizard_size.get_size')
    def get_size(self, cursor, user, wizard, model, context=None):
        '''
        Get size for wizard dialog.
        :param cursor: the database cursor
        :param user: the user id
        :param wizard: the wizard name
        :param model: the model name
        :param context: the context
        :return: (width, height)
        '''
        ids = self.search(cursor, user, [
            ('user', '=', user),
            ('wizard', '=', wizard),
            ('model', '=', model),
            ], limit=1, context=context)
        if ids:
            wizard_size = self.browse(cursor, user, ids[0], context=context)
            return wizard_size.width, wizard_size.height
        return (0, 0)

ActionWizardSize()


class ActionURL(ModelSQL, ModelView):
    "Action URL"
    _name = 'ir.action.url'
    _description = __doc__
    _inherits = {'ir.action': 'action'}
    url = fields.Char('Action Url', required=True)
    action = fields.Many2One('ir.action', 'Action', required=True,
            ondelete='CASCADE')

    def default_type(self, cursor, user, context=None):
        return 'ir.action.url'

    def default_target(self, cursor, user, context=None):
        return 'new'

    def create(self, cursor, user, vals, context=None):
        later = {}
        vals = vals.copy()
        for field in vals:
            if field in self._columns \
                    and hasattr(self._columns[field], 'set'):
                later[field] = vals[field]
        for field in later:
            del vals[field]
        if cursor.nextid(self._table):
            cursor.setnextid(self._table, cursor.currid('ir_action'))
        new_id = super(ActionURL, self).create(cursor, user, vals,
                context=context)
        url = self.browse(cursor, user, new_id, context=context)
        new_id = url.action.id
        cursor.execute('UPDATE "' + self._table + '" SET id = %s ' \
                'WHERE id = %s', (url.action.id, url.id))
        cursor.update_auto_increment(self._table, url.action.id)
        ModelStorage.delete(self, cursor, user, url.id)
        self.write(cursor, user, new_id, later, context=context)
        return new_id

    def delete(self, cursor, user, ids, context=None):
        action_obj = self.pool.get('ir.action')

        if isinstance(ids, (int, long)):
            ids = [ids]
        action_ids = [x.action.id for x in self.browse(cursor, user, ids,
            context=context)]

        res = super(ActionURL, self).delete(cursor, user, ids,
                context=context)
        action_obj.delete(cursor, user, action_ids, context=context)
        return res

ActionURL()
