#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Action"
from trytond.model import ModelView, ModelSQL, fields
from trytond.tools import file_open
from trytond.backend import TableHandler
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
        for action_keyword in self.browse(cursor, user, action_keyword_ids,
                context=context):
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
        return res

ActionKeyword()


class ActionReport(ModelSQL, ModelView):
    "Action report"
    _name = 'ir.action.report'
    _sequence = 'ir_action_id_seq'
    _description = __doc__
    _inherits = {'ir.action': 'action'}
    model = fields.Char('Model')
    report_name = fields.Char('Internal Name', required=True)
    report = fields.Char('Path')
    report_content_data = fields.Binary('Content')
    report_content = fields.Function('get_report_content',
            fnct_inv='report_content_inv', type='binary',
            string='Content')
    action = fields.Many2One('ir.action', 'Action', required=True,
            ondelete='CASCADE')
    style = fields.Property(type='char', string='Style',
            help='Define the style to apply on the report.')
    style_content = fields.Function('get_style_content',
            type='binary', string='Style')
    direct_print = fields.Boolean('Direct Print')
    extension = fields.Selection(
        [('odt', 'ODT Document'),
         ('pdf', 'PDF Document'),],
        string='Extension', required=True)
    module = fields.Char('Module', readonly=True)
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

    def get_report_content(self, cursor, user, ids, name, arg, context=None):
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

    def report_content_inv(self, cursor, user, obj_id, name, value, arg,
            context=None):
        self.write(cursor, user, obj_id, {name+'_data': value}, context=context)

    def get_style_content(self, cursor, user, ids, name, arg, context=None):
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
    _sequence = 'ir_action_id_seq'
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
    views = fields.Function('views_get_fnc', type='binary',
            string='Views')
    limit = fields.Integer('Limit',
            help='Default limit for the list view')
    auto_refresh = fields.Integer('Auto-Refresh',
            help='Add an auto-refresh on the view')
    action = fields.Many2One('ir.action', 'Action', required=True,
            ondelete='CASCADE')
    window_name = fields.Boolean('Window Name', required=True,
            help='Use the action name as window name')
    search_value = fields.Char('Search Criteria',
            help='Default search criteria for the list view')

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

    def views_get_fnc(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for act in self.browse(cursor, user, ids, context=context):
            res[act.id] = [(view.view.id, view.view.type) \
                    for view in act.act_window_views]
        return res

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
    _sequence = 'ir_action_id_seq'
    _description = __doc__
    _inherits = {'ir.action': 'action'}
    wiz_name = fields.Char('Wizard name', required=True)
    action = fields.Many2One('ir.action', 'Action', required=True,
            ondelete='CASCADE')
    model = fields.Char('Model')
    email = fields.Char('Email')

    def default_type(self, cursor, user, context=None):
        return 'ir.action.wizard'

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


class ActionURL(ModelSQL, ModelView):
    "Action URL"
    _name = 'ir.action.url'
    _sequence = 'ir_action_id_seq'
    _description = __doc__
    _inherits = {'ir.action': 'action'}
    url = fields.Char('Action Url', required=True)
    action = fields.Many2One('ir.action', 'Action', required=True,
            ondelete='CASCADE')

    def default_type(self, cursor, user, context=None):
        return 'ir.action.url'

    def default_target(self, cursor, user, context=None):
        return 'new'

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
