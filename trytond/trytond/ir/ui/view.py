#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"View"
from trytond.model import ModelView, ModelSQL, fields
from difflib import SequenceMatcher
import os
import logging
from lxml import etree
from trytond.backend import TableHandler
from trytond.pyson import PYSONEncoder, CONTEXT, Eval, Not, Bool, Equal
from trytond.tools import safe_eval


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

    def init(self, cursor, module_name):
        super(View, self).init(cursor, module_name)
        table = TableHandler(cursor, self, module_name)

        # Migration from 1.0 arch no more required
        table.not_null_action('arch', action='remove')

    def default_arch(self, cursor, user, context=None):
        return '<?xml version="1.0"?>'

    def default_priority(self, cursor, user, context=None):
        return 16

    def default_module(self, cursor, user, context=None):
        return context and context.get('module', '') or ''

    def check_xml(self, cursor, user, ids):
        "Check XML"
        views = self.browse(cursor, user, ids)
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
            view_ids = self.search(cursor, 0, [
                ('model', '=', view.model),
                ('id', '!=', view.id),
                ('module', '=', view.module),
                ])
            for view2 in self.browse(cursor, 0, view_ids):
                xml2 = view2.arch.strip()
                if not xml2:
                    continue
                tree2 = etree.fromstring(xml2)
                root2_element = tree2.getroottree().getroot()
                strings += self._translate_view(root2_element)
            if not strings:
                continue
            for string in {}.fromkeys(strings).keys():
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

    def delete(self, cursor, user, ids, context=None):
        res = super(View, self).delete(cursor, user, ids, context=context)
        # Restart the cache
        for _, model in self.pool.iterobject():
            try:
                model.fields_view_get(cursor.dbname)
            except:
                pass
        return res

    def create(self, cursor, user, vals, context=None):
        res = super(View, self).create(cursor, user, vals, context=context)
        # Restart the cache
        for _, model in self.pool.iterobject():
            try:
                model.fields_view_get(cursor.dbname)
            except:
                pass
        return res

    def write(self, cursor, user, ids, vals, context=None):
        res = super(View, self).write(cursor, user, ids, vals, context=context)
        # Restart the cache
        for _, model in self.pool.iterobject():
            try:
                model.fields_view_get(cursor.dbname)
            except:
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

    def get_sc(self, cursor, user, user_id, model='ir.ui.menu', context=None):
        "Provide user's shortcuts"
        ids = self.search(cursor, user, [
            ('user_id','=',user_id),
            ('resource','=',model),
            ], context=context)
        return self.read(cursor, user, ids, ['res_id', 'name'], context=context)

    def default_resource(self, cursor, user, context=None):
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

    def delete(self, cursor, user, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        views = self.browse(cursor, user, ids, context=context)
        for view in views:
            # Restart the cache
            try:
                self.pool.get(view.model).fields_view_get(cursor.dbname)
            except:
                pass
        res = super(ViewTreeWidth, self).delete(cursor, user, ids, context=context)
        return res

    def create(self, cursor, user, vals, context=None):
        res = super(ViewTreeWidth, self).create(cursor, user, vals, context=context)
        if 'model' in vals:
            model = vals['model']
            # Restart the cache
            try:
                self.pool.get(model).fields_view_get(cursor.dbname)
            except:
                pass
        return res

    def write(self, cursor, user, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        views = self.browse(cursor, user, ids)
        for view in views:
            # Restart the cache
            try:
                self.pool.get(view.model).fields_view_get(cursor.dbname)
            except:
                pass
        res = super(ViewTreeWidth, self).write(cursor, user, ids, vals, context=context)
        views = self.browse(cursor, user, ids)
        for view in views:
            # Restart the cache
            try:
                self.pool.get(view.model).fields_view_get(cursor.dbname)
            except:
                pass
        return res

    def set_width(self, cursor, user, model, fields, context=None):
        '''
        Set width for the current user on the model.
        fields is a dictionary with key: field name and value: width.
        '''
        ids = self.search(cursor, user, [
            ('user', '=', user),
            ('model', '=', model),
            ('field', 'in', fields.keys()),
            ], context=context)
        self.delete(cursor, user, ids, context=context)

        for field in fields.keys():
            self.create(cursor, user, {
                'model': model,
                'field': field,
                'user': user,
                'width': fields[field],
                }, context=context)

ViewTreeWidth()
