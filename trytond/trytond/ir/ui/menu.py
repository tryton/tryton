#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from __future__ import with_statement
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction

def one_in(i, j):
    """Check the presence of an element of setA in setB
    """
    for k in i:
        if k in j:
            return True
    return False

ICONS = [(x, x) for x in [
    'tryton-accessories',
    'tryton-attachment',
    'tryton-clear',
    'tryton-close',
    'tryton-calculator',
    'tryton-calendar',
    'tryton-clock',
    'tryton-connect',
    'tryton-copy',
    'tryton-currency',
    'tryton-delete',
    'tryton-development',
    'tryton-dialog-error',
    'tryton-dialog-information',
    'tryton-dialog-warning',
    'tryton-disconnect',
    'tryton-executable',
    'tryton-find',
    'tryton-find-replace',
    'tryton-folder-new',
    'tryton-folder-saved-search',
    'tryton-fullscreen',
    'tryton-graph',
    'tryton-go-home',
    'tryton-go-jump',
    'tryton-go-next',
    'tryton-go-previous',
    'tryton-help',
    'tryton-image-missing',
    'tryton-information',
    'tryton-lock',
    'tryton-list',
    'tryton-list-add',
    'tryton-list-remove',
    'tryton-locale',
    'tryton-log-out',
    'tryton-mail-message-new',
    'tryton-new',
    'tryton-noimage',
    'tryton-open',
    'tryton-package',
    'tryton-preferences',
    'tryton-preferences-system',
    'tryton-preferences-system-session',
    'tryton-presentation',
    'tryton-print',
    'tryton-readonly',
    'tryton-refresh',
    'tryton-save-as',
    'tryton-save',
    'tryton-spreadsheet',
    'tryton-start-here',
    'tryton-tree',
    'tryton-system',
    'tryton-system-file-manager',
    'tryton-users',
    'tryton-web-browser',
]]


class UIMenu(ModelSQL, ModelView):
    "UI menu"
    _name = 'ir.ui.menu'
    _description = __doc__
    name = fields.Char('Menu', required=True, translate=True)
    sequence = fields.Integer('Sequence')
    childs = fields.One2Many('ir.ui.menu', 'parent', 'Children')
    parent = fields.Many2One('ir.ui.menu', 'Parent Menu', select=1)
    groups = fields.Many2Many('ir.ui.menu-res.group',
       'menu_id', 'gid', 'Groups')
    complete_name = fields.Function(fields.Char('Complete Name',
        order_field='name'), 'get_full_name')
    icon = fields.Selection(ICONS, 'Icon', translate=False)
    action = fields.Function(fields.Reference('Action',
            selection=[
                ('', ''),
                ('ir.action.report', 'ir.action.report'),
                ('ir.action.act_window', 'ir.action.act_window'),
                ('ir.action.wizard', 'ir.action.wizard'),
                ('ir.action.url', 'ir.action.url'),
                ]), 'get_action', setter='set_action')
    active = fields.Boolean('Active')

    def __init__(self):
        super(UIMenu, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))

    def default_icon(self):
        return 'tryton-open'

    def default_sequence(self):
        return 10

    def default_active(self):
        return True

    def get_full_name(self, ids, name):
        res = {}
        for menu in self.browse(ids):
            res[menu.id] = self._get_one_full_name(menu)
        return res

    def _get_one_full_name(self, menu, level=6):
        if level <= 0:
            return '...'
        if menu.parent:
            parent_path = self._get_one_full_name(menu.parent, level-1) + "/"
        else:
            parent_path = ''
        return parent_path + menu.name

    def search(self, domain, offset=0, limit=None, order=None, count=False,
            query_string=False):
        res = super(UIMenu, self).search(domain, offset=offset, limit=limit,
                order=order, count=False, query_string=query_string)
        if query_string:
            return res

        def check_menu(res):
            if not res:
                return []
            menus = self.browse(res)
            parent_ids = [x.parent.id for x in menus if x.parent]
            parent_ids = self.search([
                ('id', 'in', parent_ids),
                ])
            parent_ids = check_menu(parent_ids)
            return [x.id for x in menus
                    if (x.parent.id in parent_ids) or not x.parent]

        res = check_menu(res)
        if count:
            return len(res)
        return res

    def get_action(self, ids, name):
        action_keyword_obj = self.pool.get('ir.action.keyword')
        res = {}
        for menu_id in ids:
            res[menu_id] = False
        with Transaction().set_context(active_test=False):
            action_keyword_ids = action_keyword_obj.search([
                ('keyword', '=', 'tree_open'),
                ('model', 'in', [self._name + ',' + str(x) for x in ids]),
                ])
        for action_keyword in action_keyword_obj.browse(action_keyword_ids):
            model_id = int(
                    action_keyword.model.split(',')[1].split(',')[0].strip('('))
            action_obj = self.pool.get(action_keyword.action.type)
            with Transaction().set_context(active_test=False):
                action_id = action_obj.search([
                    ('action', '=', action_keyword.action.id),
                    ])
            if action_id:
                action_id = action_id[0]
            else:
                action_id = 0
            res[model_id] = action_keyword.action.type + ',' + str(action_id)
        return res

    def set_action(self, ids, name, value):
        if not value:
            return
        action_keyword_obj = self.pool.get('ir.action.keyword')
        action_keyword_ids = []
        cursor = Transaction().cursor
        for i in range(0, len(ids), cursor.IN_MAX):
            sub_ids = ids[i:i + cursor.IN_MAX]
            action_keyword_ids += action_keyword_obj.search([
                ('keyword', '=', 'tree_open'),
                ('model', 'in', [self._name + ',' + str(menu_id)
                    for menu_id in sub_ids]),
                ])
        if action_keyword_ids:
            with Transaction().set_context(_timestamp=False):
                action_keyword_obj.delete(action_keyword_ids)
        action_type, action_id = value.split(',')
        if not int(action_id):
            return
        action_obj = self.pool.get(action_type)
        action = action_obj.browse(int(action_id))
        for menu_id in ids:
            with Transaction().set_context(_timestamp=False):
                action_keyword_obj.create({
                    'keyword': 'tree_open',
                    'model': self._name + ',' + str(menu_id),
                    'action': action.action.id,
                    })

UIMenu()
