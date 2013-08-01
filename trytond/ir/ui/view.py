#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import os
import logging
from lxml import etree
from difflib import SequenceMatcher
from trytond.model import ModelView, ModelSQL, fields
from trytond.backend import TableHandler
from trytond.pyson import CONTEXT, Eval, Bool
from trytond.tools import safe_eval, file_open
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.pool import Pool
from trytond.cache import Cache
from trytond.rpc import RPC

__all__ = [
    'View', 'ShowViewStart', 'ShowView', 'ViewShortcut',
    'OpenShortcut', 'ViewTreeWidth', 'ViewTreeExpandedState',
    ]


class View(ModelSQL, ModelView):
    "View"
    __name__ = 'ir.ui.view'
    _rec_name = 'model'
    model = fields.Char('Model', select=True, states={
            'required': Eval('type').in_([None, 'tree', 'form', 'graph']),
            })
    priority = fields.Integer('Priority', required=True, select=True)
    type = fields.Selection([
            (None, ''),
            ('tree', 'Tree'),
            ('form', 'Form'),
            ('graph', 'Graph'),
            ('board', 'Board'),
            ], 'View Type', select=True)
    data = fields.Text('Data')
    name = fields.Char('Name', states={
            'invisible': ~(Eval('module') & Eval('name')),
            }, depends=['module'], readonly=True)
    arch = fields.Function(fields.Text('View Architecture', states={
                'readonly': Bool(Eval('name')),
                }, depends=['name']), 'get_arch', setter='set_arch')
    inherit = fields.Many2One('ir.ui.view', 'Inherited View', select=True,
            ondelete='CASCADE')
    field_childs = fields.Char('Children Field', states={
            'invisible': Eval('type') != 'tree',
            }, depends=['type'])
    module = fields.Char('Module', states={
            'invisible': ~Eval('module'),
            }, readonly=True)
    domain = fields.Char('Domain', states={
            'invisible': ~Eval('inherit'),
            }, depends=['inherit'])
    _get_rng_cache = Cache('ir_ui_view.get_rng')

    @classmethod
    def __setup__(cls):
        super(View, cls).__setup__()
        cls._constraints += [
            ('check_xml', 'invalid_xml'),
        ]
        cls._error_messages.update({
            'invalid_xml': 'Invalid XML for View!',
        })
        cls._order.insert(0, ('priority', 'ASC'))
        cls._buttons.update({
                'show': {},
                })

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

        # Migration from 2.4 arch moved into data
        if table.column_exist('arch'):
            table.column_rename('arch', 'data')

        super(View, cls).__register__(module_name)

        # Migration from 1.0 arch no more required
        table.not_null_action('arch', action='remove')

        # Migration from 2.4 model no more required
        table.not_null_action('model', action='remove')

    @staticmethod
    def default_priority():
        return 16

    @staticmethod
    def default_module():
        return Transaction().context.get('module') or ''

    @classmethod
    @ModelView.button_action('ir.act_view_show')
    def show(cls, views):
        pass

    @classmethod
    def get_rng(cls, type_):
        key = (cls.__name__, type_)
        rng = cls._get_rng_cache.get(key)
        if rng is None:
            rng_name = os.path.join(os.path.dirname(__file__), type_ + '.rng')
            rng = etree.fromstring(open(rng_name).read())
            cls._get_rng_cache.set(key, rng)
        return rng

    @classmethod
    def check_xml(cls, views):
        "Check XML"
        pool = Pool()
        Translation = pool.get('ir.translation')
        cursor = Transaction().cursor
        for view in views:
            cursor.execute('SELECT id, name, src FROM ir_translation ' \
                    'WHERE lang = %s ' \
                        'AND type = %s ' \
                        'AND name = %s '\
                        'AND module = %s',
                            ('en_US', 'view', view.model, view.module))
            trans_views = {}
            for trans in cursor.dictfetchall():
                trans_views[trans['src']] = trans
            if not view.arch:
                continue
            xml = view.arch.strip()
            if not xml:
                continue
            tree = etree.fromstring(xml)

            if hasattr(etree, 'RelaxNG'):
                rng_type = view.inherit.type if view.inherit else view.type
                validator = etree.RelaxNG(etree=cls.get_rng(rng_type))
                if not validator.validate(tree):
                    logger = logging.getLogger('ir')
                    error_log = reduce(lambda x, y: str(x) + '\n' + str(y),
                            validator.error_log.filter_from_errors())
                    logger.error('Invalid xml view:\n%s'
                        % (str(error_log) + '\n' + xml))
                    return False
            root_element = tree.getroottree().getroot()

            # validate pyson attributes
            validates = {
                'states': fields.states_validate,
            }

            def encode(element):
                for attr in ('states', 'domain', 'spell', 'colors'):
                    if element.get(attr):
                        try:
                            value = safe_eval(element.get(attr), CONTEXT)
                            validates.get(attr, lambda a: True)(value)
                        except Exception, e:
                            logger = logging.getLogger('ir')
                            logger.error('Invalid pyson view element "%s:%s":'
                                '\n%s\n%s'
                                % (element.get('id') or element.get('name'),
                                    attr, str(e), xml))
                            return False
                for child in element:
                    if not encode(child):
                        return False
                return True
            if not encode(root_element):
                return False

            strings = cls._translate_view(root_element)
            with Transaction().set_user(0):
                views2 = cls.search([
                    ('model', '=', view.model),
                    ('id', '!=', view.id),
                    ('module', '=', view.module),
                    ])
                for view2 in views2:
                    xml2 = view2.arch.strip()
                    if not xml2:
                        continue
                    tree2 = etree.fromstring(xml2)
                    root2_element = tree2.getroottree().getroot()
                    strings += cls._translate_view(root2_element)
            if not strings:
                continue
            for string in set(strings):
                done = False
                if string in trans_views:
                    del trans_views[string]
                    continue
                string_md5 = Translation.get_src_md5(string)
                for string_trans in trans_views:
                    if string_trans in strings:
                        continue
                    seqmatch = SequenceMatcher(lambda x: x == ' ',
                            string, string_trans)
                    if seqmatch.ratio() == 1.0:
                        del trans_views[string_trans]
                        done = True
                        break
                    if seqmatch.ratio() > 0.6:
                        cursor.execute('UPDATE ir_translation '
                            'SET src = %s, '
                                'src_md5 = %s, '
                                'fuzzy = %s '
                            'WHERE id = %s ',
                            (string, string_md5, True,
                                trans_views[string_trans]['id']))
                        del trans_views[string_trans]
                        done = True
                        break
                if not done:
                    cursor.execute('INSERT INTO ir_translation '
                        '(name, lang, type, src, src_md5, value, module, '
                            'fuzzy) '
                        'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                        (view.model, 'en_US', 'view', string, string_md5, '',
                            view.module, False))
            if strings:
                cursor.execute('DELETE FROM ir_translation ' \
                        'WHERE name = %s ' \
                            'AND type = %s ' \
                            'AND module = %s ' \
                            'AND src NOT IN ' \
                                '(' + ','.join(('%s',) * len(strings)) + ')',
                        (view.model, 'view', view.module) + tuple(strings))
        return True

    def get_arch(self, name):
        value = None
        if self.name and self.module:
            path = os.path.join(self.module, 'view', self.name + '.xml')
            try:
                with file_open(path, subdir='modules') as fp:
                    value = fp.read()
            except IOError:
                pass
        if not value:
            value = self.data
        return value

    @classmethod
    def set_arch(cls, views, name, value):
        cls.write(views, {'data': value})

    @classmethod
    def delete(cls, views):
        super(View, cls).delete(views)
        # Restart the cache
        ModelView._fields_view_get_cache.clear()

    @classmethod
    def create(cls, vals):
        view = super(View, cls).create(vals)
        # Restart the cache
        ModelView._fields_view_get_cache.clear()
        return view

    @classmethod
    def write(cls, views, vals):
        super(View, cls).write(views, vals)
        # Restart the cache
        ModelView._fields_view_get_cache.clear()

    @classmethod
    def _translate_view(cls, element):
        strings = []
        for attr in ('string', 'sum', 'confirm', 'help'):
            if element.get(attr):
                string = element.get(attr)
                if string:
                    strings.append(string)
        for child in element:
            strings.extend(cls._translate_view(child))
        return strings


class ShowViewStart(ModelView):
    'Show view'
    __name__ = 'ir.ui.view.show.start'


class ShowView(Wizard):
    'Show view'
    __name__ = 'ir.ui.view.show'

    class ShowStateView(StateView):

        def __init__(self, model_name, buttons):
            StateView.__init__(self, model_name, None, buttons)

        def get_view(self):
            pool = Pool()
            View = pool.get('ir.ui.view')
            view = View(Transaction().context.get('active_id'))
            Model = pool.get(view.model)
            if view.type != 'form':
                return Model.fields_view_get(view_type='form')
            return Model.fields_view_get(view_id=view.id)

        def get_defaults(self, wizard, state_name, fields):
            return {}

    start = ShowStateView('ir.ui.view.show.start', [
            Button('Close', 'end', 'tryton-close', default=True),
            ])


class ViewShortcut(ModelSQL, ModelView):
    "View shortcut"
    __name__ = 'ir.ui.view_sc'

    name = fields.Char('Shortcut Name', required=True)
    res_id = fields.Integer('Resource Ref.', required=True)
    sequence = fields.Integer('Sequence',
        order_field='(%(table)s.sequence IS NULL) %(order)s, '
        '%(table)s.sequence %(order)s')
    user_id = fields.Many2One('res.user', 'User Ref.', required=True,
       ondelete='CASCADE')
    resource = fields.Char('Resource Name', required=True)

    @classmethod
    def __setup__(cls):
        super(ViewShortcut, cls).__setup__()
        cls.__rpc__.update({
                'get_sc': RPC(),
                })
        cls._order.insert(0, ('sequence', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        super(ViewShortcut, cls).__register__(module_name)
        table = TableHandler(cursor, cls, module_name)

        # Migration from 2.4 sequence is not required anymore
        table.not_null_action('sequence', action='remove')

    @classmethod
    def get_sc(cls, user_id, model='ir.ui.menu'):
        "Provide user's shortcuts"
        result = []
        shortcuts = cls.search([
                ('user_id', '=', user_id),
                ('resource', '=', model),
                ])
        for shorcut in shortcuts:
            result.append({
                    'res_id': shorcut.res_id,
                    'name': shorcut.name,
                    })
        return result

    @staticmethod
    def default_resource():
        return 'ir.ui.menu'


class OpenShortcut(Wizard):
    'Open a shortcut'
    __name__ = 'ir.ui.view_sc.open'

    start_state = 'open_'

    class OpenStateAction(StateAction):
        def __init__(self):
            StateAction.__init__(self, None)

        def get_action(self):
            pass

    open_ = OpenStateAction()

    @staticmethod
    def transition_open_():
        return 'end'

    @staticmethod
    def do_open_(action):
        pool = Pool()
        ViewSC = pool.get('ir.ui.view_sc')
        ActionKeyword = pool.get('ir.action.keyword')
        Action = pool.get('ir.action')

        view_sc = ViewSC(Transaction().context.get('active_id'))
        models = (
                '%s,%d' % (view_sc.resource, view_sc.res_id),
                '%s,0' % (view_sc.resource),
                )
        action_keywords = None
        for model in models:
            action_keywords = ActionKeyword.search([
                    ('keyword', '=', 'tree_open'),
                    ('model', '=', model),
                    ])
            if action_keywords:
                break
        if not action_keywords:
            return {}, {}
        action_keyword = action_keywords[0]
        return Action.get_action_values(action_keyword.action.type,
            [action_keyword.action.id])[0], {}


class ViewTreeWidth(ModelSQL, ModelView):
    "View Tree Width"
    __name__ = 'ir.ui.view_tree_width'
    _rec_name = 'model'
    model = fields.Char('Model', required=True, select=True)
    field = fields.Char('Field', required=True, select=True)
    user = fields.Many2One('res.user', 'User', required=True,
            ondelete='CASCADE', select=True)
    width = fields.Integer('Width', required=True)

    @classmethod
    def __setup__(cls):
        super(ViewTreeWidth, cls).__setup__()
        cls.__rpc__.update({
                'set_width': RPC(readonly=False),
                })

    @classmethod
    def delete(cls, records):
        ModelView._fields_view_get_cache.clear()
        super(ViewTreeWidth, cls).delete(records)

    @classmethod
    def create(cls, vals):
        res = super(ViewTreeWidth, cls).create(vals)
        ModelView._fields_view_get_cache.clear()
        return res

    @classmethod
    def write(cls, records, vals):
        super(ViewTreeWidth, cls).write(records, vals)
        ModelView._fields_view_get_cache.clear()

    @classmethod
    def set_width(cls, model, fields):
        '''
        Set width for the current user on the model.
        fields is a dictionary with key: field name and value: width.
        '''
        records = cls.search([
            ('user', '=', Transaction().user),
            ('model', '=', model),
            ('field', 'in', fields.keys()),
            ])
        cls.delete(records)

        for field in fields.keys():
            cls.create({
                'model': model,
                'field': field,
                'user': Transaction().user,
                'width': fields[field],
                })


class ViewTreeExpandedState(ModelSQL, ModelView):
    'View Tree Expanded State'
    __name__ = 'ir.ui.view_tree_expanded_state'
    _rec_name = 'model'
    model = fields.Char('Model', required=True)
    domain = fields.Char('Domain', required=True)
    user = fields.Many2One('res.user', 'User', required=True,
            ondelete='CASCADE')
    child_name = fields.Char('Child Name')
    nodes = fields.Text('Expanded Nodes')

    @classmethod
    def __setup__(cls):
        super(ViewTreeExpandedState, cls).__setup__()
        cls.__rpc__.update({
                'set_expanded': RPC(readonly=False),
                'get_expanded': RPC(),
                })

    @classmethod
    def __register__(cls, module_name):
        super(ViewTreeExpandedState, cls).__register__(module_name)

        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)
        table.index_action(['model', 'domain', 'user', 'child_name'], 'add')

    @staticmethod
    def default_nodes():
        return '[]'

    @classmethod
    def set_expanded(cls, model, domain, child_name, nodes):
        current_user = Transaction().user
        with Transaction().set_user(0):
            records = cls.search([
                    ('user', '=', current_user),
                    ('model', '=', model),
                    ('domain', '=', domain),
                    ('child_name', '=', child_name),
                    ])
            cls.delete(records)
            cls.create({
                    'user': current_user,
                    'model': model,
                    'domain': domain,
                    'child_name': child_name,
                    'nodes': nodes,
                    })

    @classmethod
    def get_expanded(cls, model, domain, child_name):
        current_user = Transaction().user
        with Transaction().set_user(0):
            try:
                expanded_info, = cls.search([
                        ('user', '=', current_user),
                        ('model', '=', model),
                        ('domain', '=', domain),
                        ('child_name', '=', child_name),
                        ],
                    limit=1)
            except ValueError:
                return '[]'
            return cls(expanded_info).nodes
