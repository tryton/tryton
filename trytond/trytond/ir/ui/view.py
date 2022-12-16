#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from __future__ import with_statement
import os
import logging
from lxml import etree
from difflib import SequenceMatcher
from trytond.model import ModelView, ModelSQL, fields
from trytond.backend import TableHandler
from trytond.pyson import PYSONEncoder, CONTEXT, Eval, Not, Bool, Equal
from trytond.tools import safe_eval
from trytond.transaction import Transaction


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
        'invisible': Not(Equal(Eval('type'), 'tree')),
        })
    module = fields.Char('Module', readonly=True)
    domain = fields.Char('Domain', states={
        'invisible': Not(Bool(Eval('inherit'))),
        })

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
                        cursor.execute('UPDATE ir_translation ' \
                            'SET src = %s, ' \
                                'fuzzy = %s ' \
                            'WHERE id = %s ',
                            (string, True, trans_views[string_trans]['id']))
                        del trans_views[string_trans]
                        done = True
                        break
                if not done:
                    cursor.execute('INSERT INTO ir_translation ' \
                        '(name, lang, type, src, value, module, fuzzy)' \
                        'VALUES (%s, %s, %s, %s, %s, %s, %s)',
                        (view.model, 'en_US', 'view', string, '',
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
        for _, model in self.pool.iterobject():
            try:
                model.fields_view_get.reset()
            except Exception:
                pass
        return res

    def create(self, vals):
        res = super(View, self).create(vals)
        # Restart the cache
        for _, model in self.pool.iterobject():
            try:
                model.fields_view_get.reset()
            except Exception:
                pass
        return res

    def write(self, ids, vals):
        res = super(View, self).write(ids, vals)
        # Restart the cache
        for _, model in self.pool.iterobject():
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
        ids = self.search([
            ('user_id','=',user_id),
            ('resource','=',model),
            ])
        return self.read(ids, ['res_id', 'name'])

    def default_resource(self):
        return 'ir.ui.menu'

ViewShortcut()


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
        if isinstance(ids, (int, long)):
            ids = [ids]
        views = self.browse(ids)
        for view in views:
            # Restart the cache
            try:
                self.pool.get(view.model).fields_view_get.reset()
            except Exception:
                pass
        res = super(ViewTreeWidth, self).delete(ids)
        return res

    def create(self, vals):
        res = super(ViewTreeWidth, self).create(vals)
        if 'model' in vals:
            model = vals['model']
            # Restart the cache
            try:
                self.pool.get(model).fields_view_get.reset()
            except Exception:
                pass
        return res

    def write(self, ids, vals):
        if isinstance(ids, (int, long)):
            ids = [ids]
        views = self.browse(ids)
        for view in views:
            # Restart the cache
            try:
                self.pool.get(view.model).fields_view_get.reset()
            except Exception:
                pass
        res = super(ViewTreeWidth, self).write(ids, vals)
        views = self.browse(ids)
        for view in views:
            # Restart the cache
            try:
                self.pool.get(view.model).fields_view_get.reset()
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
