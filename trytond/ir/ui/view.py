#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import os
import logging
from lxml import etree
from difflib import SequenceMatcher
from trytond.model import ModelView, ModelSQL, fields
from trytond.backend import TableHandler
from trytond.pyson import PYSONEncoder, CONTEXT, Eval
from trytond.tools import safe_eval
from trytond.transaction import Transaction
from trytond.wizard import Wizard
from trytond.pool import Pool


class View(ModelSQL, ModelView):
    "View"
    _name = 'ir.ui.view'
    _description = __doc__
    _rec_name = 'model'
    model = fields.Char('Model', required=True, select=1)
    priority = fields.Integer('Priority', required=True, select=1)
    type = fields.Selection([
        (False, ''),
        ('tree','Tree'),
        ('form','Form'),
        ('graph', 'Graph'),
        ('board', 'Board'),
        ], 'View Type', select=1)
    arch = fields.Text('View Architecture')
    inherit = fields.Many2One('ir.ui.view', 'Inherited View', select=1,
            ondelete='CASCADE')
    field_childs = fields.Char('Children Field', states={
            'invisible': Eval('type') != 'tree',
            }, depends=['type'])
    module = fields.Char('Module', readonly=True)
    domain = fields.Char('Domain', states={
            'invisible': ~Eval('inherit'),
            }, depends=['inherit'])

    def __init__(self):
        super(View, self).__init__()
        self._constraints += [
            ('check_xml', 'invalid_xml'),
        ]
        self._error_messages.update({
            'invalid_xml': 'Invalid XML for View!',
        })
        self._order.insert(0, ('priority', 'ASC'))

    def init(self, module_name):
        super(View, self).init(module_name)
        table = TableHandler(Transaction().cursor, self, module_name)

        # Migration from 1.0 arch no more required
        table.not_null_action('arch', action='remove')

    def default_arch(self):
        return '<?xml version="1.0"?>'

    def default_priority(self):
        return 16

    def default_module(self):
        return Transaction().context.get('module') or ''

    def check_xml(self, ids):
        "Check XML"
        pool = Pool()
        translation_obj = pool.get('ir.translation')
        cursor = Transaction().cursor
        views = self.browse(ids)
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

            # validate the tree using RelaxNG
            rng_name = os.path.join(os.path.dirname(__file__),
                    (view.inherit and view.inherit.type or view.type) + '.rng')
            if hasattr(etree, 'RelaxNG'):
                validator = etree.RelaxNG(file=rng_name)
                if not validator.validate(tree):
                    logger = logging.getLogger('ir')
                    error_log = reduce(lambda x, y: str(x) + '\n' + str(y),
                            validator.error_log.filter_from_errors())
                    logger.error(
                        'Invalid xml view:\n%s' %  (str(error_log) + '\n' + xml))
                    return False
            root_element = tree.getroottree().getroot()

            # validate pyson attributes
            validates = {
                'states': fields.states_validate,
                'domain': fields.domain_validate,
                'context': fields.context_validate,
                'digits': fields.digits_validate,
                'add_remove': fields.add_remove_validate,
            }
            def encode(element):
                for attr in ('states', 'domain', 'context', 'digits',
                        'add_remove', 'spell', 'colors'):
                    if element.get(attr):
                        try:
                            value = safe_eval(element.get(attr), CONTEXT)
                            validates.get(attr, lambda a: True)(value)
                        except Exception, e:
                            logger = logging.getLogger('ir')
                            logger.error('Invalid pyson view element "%s:%s":' \
                                    '\n%s\n%s' % \
                                    (element.get('id') or element.get('name'),
                                        attr, str(e), xml))
                            return False
                for child in element:
                    if not encode(child):
                        return False
                return True
            if not encode(root_element):
                return False

            strings = self._translate_view(root_element)
            with Transaction().set_user(0):
                view_ids = self.search([
                    ('model', '=', view.model),
                    ('id', '!=', view.id),
                    ('module', '=', view.module),
                    ])
                for view2 in self.browse(view_ids):
                    xml2 = view2.arch.strip()
                    if not xml2:
                        continue
                    tree2 = etree.fromstring(xml2)
                    root2_element = tree2.getroottree().getroot()
                    strings += self._translate_view(root2_element)
            if not strings:
                continue
            for string in set(strings):
                done = False
                if string in trans_views:
                    del trans_views[string]
                    continue
                string_md5 = translation_obj.get_src_md5(string)
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

    def delete(self, ids):
        res = super(View, self).delete(ids)
        # Restart the cache
        pool = Pool()
        for _, model in pool.iterobject():
            try:
                model.fields_view_get.reset()
            except Exception:
                pass
        return res

    def create(self, vals):
        res = super(View, self).create(vals)
        # Restart the cache
        pool = Pool()
        for _, model in pool.iterobject():
            try:
                model.fields_view_get.reset()
            except Exception:
                pass
        return res

    def write(self, ids, vals):
        res = super(View, self).write(ids, vals)
        # Restart the cache
        pool = Pool()
        for _, model in pool.iterobject():
            try:
                model.fields_view_get.reset()
            except Exception:
                pass
        return res

    def _translate_view(self, element):
        strings = []
        for attr in ('string', 'sum', 'confirm', 'help'):
            if element.get(attr):
                string = element.get(attr)
                if string:
                    strings.append(string)
        for child in element:
            strings.extend(self._translate_view(child))
        return strings

View()


class ShowViewInit(ModelView):
    'Show view init'
    _name = 'ir.ui.view.show.init'

ShowViewInit()


class ShowView(Wizard):
    'Show view'
    _name = 'ir.ui.view.show'

    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'ir.ui.view.show.init',
                'state': [
                    ('end', 'Close', 'tryton-cancel', True),
                    ],
                },
            },
        }

    def __init__(self):
        super(ShowView, self).__init__()
        self._error_messages.update({
                'view_type': 'Only "form" view can be shown!',
                })

    def execute(self, wiz_id, data, state='init'):
        pool = Pool()
        view_obj = pool.get('ir.ui.view')
        result = super(ShowView, self).execute(wiz_id, data, state=state)
        view = view_obj.browse(data['id'])
        view_id = view.id
        view_type = view.type
        if view.inherit:
            view_id = view.inherit.id
            view_type = view.inherit.type
        if view_type != 'form':
            self.raise_user_error('view_type')
        model_obj = pool.get(view.model)
        fields_view = model_obj.fields_view_get(view_id=view.id)
        result['fields'] = fields_view['fields']
        result['arch'] = fields_view['arch']
        result['object'] = view.model
        return result

ShowView()


class ViewShortcut(ModelSQL, ModelView):
    "View shortcut"
    _name = 'ir.ui.view_sc'
    _description = __doc__
    name = fields.Char('Shortcut Name', required=True)
    res_id = fields.Integer('Resource Ref.', required=True)
    sequence = fields.Integer('Sequence')
    user_id = fields.Many2One('res.user', 'User Ref.', required=True,
       ondelete='CASCADE')
    resource = fields.Char('Resource Name', required=True)

    def __init__(self):
        super(ViewShortcut, self).__init__()
        self._rpc.update({'get_sc': False})
        self._order.insert(0, ('sequence', 'ASC'))

    def get_sc(self, user_id, model='ir.ui.menu'):
        "Provide user's shortcuts"
        result = []
        ids = self.search([
            ('user_id','=',user_id),
            ('resource','=',model),
            ])
        for shorcut in self.browse(ids):
            result.append({
                    'res_id': shorcut.res_id,
                    'name': shorcut.name,
                    })
        return result

    def default_resource(self):
        return 'ir.ui.menu'

ViewShortcut()


class AddShortcut(Wizard):
    'Add shortcut'
    _name = 'ir.ui.view_sc.add'

    states = {
        'init': {
            'result': {
                'type': 'action',
                'action': '_add_shortcut',
                'state': 'end',
            },
        },
    }

    def _add_shortcut(self, data):
        pool = Pool()
        view_sc_obj = pool.get('ir.ui.view_sc')
        model_obj = pool.get(data['model'])

        record = model_obj.browse(data['id'])
        view_sc_obj.create({
            'name': record.rec_name,
            'res_id': record.id,
            'user_id': Transaction().user,
            'resource': model_obj._name,
            })
        return {}

AddShortcut()


class OpenShortcut(Wizard):
    'Open a shortcut'
    _name = 'ir.ui.view_sc.open'

    states = {
        'init': {
            'result': {
                'type': 'action',
                'action': '_open',
                'state': 'end',
            }
        }
    }

    def _open(self, data):
        pool = Pool()
        view_sc_obj = pool.get('ir.ui.view_sc')
        action_keyword_obj = pool.get('ir.action.keyword')

        view_sc = view_sc_obj.browse(data['id'])
        models = (
                '%s,%d' % (view_sc.resource, view_sc.res_id),
                '%s,0' % (view_sc.resource),
                )
        action_keyword_ids = None
        for model in models:
            action_keyword_ids = action_keyword_obj.search([
                ('keyword', '=', 'tree_open'),
                ('model', '=', model),
                ])
            if action_keyword_ids:
                break
        if not action_keyword_ids:
            return {}
        action_keyword = action_keyword_obj.browse(action_keyword_ids[0])
        action_obj = pool.get(action_keyword.action.type)
        action_ids = action_obj.search([
            ('action.id', '=', action_keyword.action.id),
            ])
        if not action_ids:
            return {}
        return action_obj.read(action_ids[0])

OpenShortcut()


class ViewTreeWidth(ModelSQL, ModelView):
    "View Tree Width"
    _name = 'ir.ui.view_tree_width'
    _description = __doc__
    _rec_name = 'model'
    model = fields.Char('Model', required=True, select=1)
    field = fields.Char('Field', required=True, select=1)
    user = fields.Many2One('res.user', 'User', required=True,
            ondelete='CASCADE', select=1)
    width = fields.Integer('Width')

    def __init__(self):
        super(ViewTreeWidth, self).__init__()
        self._rpc.update({
            'set_width': True,
        })

    def delete(self, ids):
        pool = Pool()
        if isinstance(ids, (int, long)):
            ids = [ids]
        views = self.browse(ids)
        for view in views:
            # Restart the cache
            try:
                pool.get(view.model).fields_view_get.reset()
            except Exception:
                pass
        res = super(ViewTreeWidth, self).delete(ids)
        return res

    def create(self, vals):
        pool = Pool()
        res = super(ViewTreeWidth, self).create(vals)
        if 'model' in vals:
            model = vals['model']
            # Restart the cache
            try:
                pool.get(model).fields_view_get.reset()
            except Exception:
                pass
        return res

    def write(self, ids, vals):
        pool = Pool()
        if isinstance(ids, (int, long)):
            ids = [ids]
        views = self.browse(ids)
        for view in views:
            # Restart the cache
            try:
                pool.get(view.model).fields_view_get.reset()
            except Exception:
                pass
        res = super(ViewTreeWidth, self).write(ids, vals)
        views = self.browse(ids)
        for view in views:
            # Restart the cache
            try:
                pool.get(view.model).fields_view_get.reset()
            except Exception:
                pass
        return res

    def set_width(self, model, fields):
        '''
        Set width for the current user on the model.
        fields is a dictionary with key: field name and value: width.
        '''
        ids = self.search([
            ('user', '=', Transaction().user),
            ('model', '=', model),
            ('field', 'in', fields.keys()),
            ])
        self.delete(ids)

        for field in fields.keys():
            self.create({
                'model': model,
                'field': field,
                'user': Transaction().user,
                'width': fields[field],
                })

ViewTreeWidth()


class ViewTreeExpandedState(ModelSQL, ModelView):
    _name = 'ir.ui.view_tree_expanded_state'

    _rec_name = 'model'
    model = fields.Char('Model', required=True)
    domain = fields.Char('Domain', required=True)
    user = fields.Many2One('res.user', 'User', required=True,
            ondelete='CASCADE')
    child_name = fields.Char('Child Name')
    nodes = fields.Text('Expanded Nodes')

    def __init__(self):
        super(ViewTreeExpandedState, self).__init__()
        self._rpc.update({
                'set_expanded': True,
                'get_expanded': True,
                })

    def init(self, module_name):
        super(ViewTreeExpandedState, self).init(module_name)

        cursor = Transaction().cursor
        table = TableHandler(cursor, self, module_name)
        table.index_action(['model', 'domain', 'user', 'child_name'], 'add')

    def default_nodes(self):
        return '[]'

    def set_expanded(self, model, domain, child_name, nodes):
        current_user = Transaction().user
        with Transaction().set_user(0):
            ids = self.search([
                    ('user', '=', current_user),
                    ('model', '=', model),
                    ('domain', '=', domain),
                    ('child_name', '=', child_name),
                    ])
            self.delete(ids)
            self.create({
                    'user': current_user,
                    'model': model,
                    'domain': domain,
                    'child_name': child_name,
                    'nodes': nodes,
                    })

    def get_expanded(self, model, domain, child_name):
        current_user = Transaction().user
        with Transaction().set_user(0):
            try:
                expanded_info, = self.search([
                        ('user', '=', current_user),
                        ('model', '=', model),
                        ('domain', '=', domain),
                        ('child_name', '=', child_name),
                        ],
                    limit=1)
            except ValueError:
                return '[]'
            return self.browse(expanded_info).nodes


ViewTreeExpandedState()
