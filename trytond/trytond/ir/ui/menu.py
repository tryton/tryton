#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.pool import Pool

def one_in(i, j):
    """Check the presence of an element of setA in setB
    """
    for k in i:
        if k in j:
            return True
    return False

CLIENT_ICONS = [(x, x) for x in (
    'tryton-attachment-hi',
    'tryton-attachment',
    'tryton-cancel',
    'tryton-clear',
    'tryton-close',
    'tryton-connect',
    'tryton-copy',
    'tryton-delete',
    'tryton-dialog-error',
    'tryton-dialog-information',
    'tryton-dialog-warning',
    'tryton-disconnect',
    'tryton-executable',
    'tryton-find-replace',
    'tryton-find',
    'tryton-folder-new',
    'tryton-fullscreen',
    'tryton-go-home',
    'tryton-go-jump',
    'tryton-go-next',
    'tryton-go-previous',
    'tryton-help',
    'tryton-icon',
    'tryton-list-add',
    'tryton-list-remove',
    'tryton-locale',
    'tryton-lock',
    'tryton-log-out',
    'tryton-mail-message-new',
    'tryton-mail-message',
    'tryton-new',
    'tryton-ok',
    'tryton-open',
    'tryton-preferences-system-session',
    'tryton-preferences-system',
    'tryton-preferences',
    'tryton-print',
    'tryton-refresh',
    'tryton-save-as',
    'tryton-save',
    'tryton-start-here',
    'tryton-system-file-manager',
    'tryton-system',
    'tryton-undo',
    'tryton-web-browser')]
SEPARATOR = ' / '


class UIMenu(ModelSQL, ModelView):
    "UI menu"
    _name = 'ir.ui.menu'
    _description = __doc__
    name = fields.Char('Menu', required=True, translate=True)
    sequence = fields.Integer('Sequence')
    childs = fields.One2Many('ir.ui.menu', 'parent', 'Children')
    parent = fields.Many2One('ir.ui.menu', 'Parent Menu', select=1,
            ondelete='CASCADE')
    groups = fields.Many2Many('ir.ui.menu-res.group',
       'menu', 'group', 'Groups')
    complete_name = fields.Function(fields.Char('Complete Name',
        order_field='name'), 'get_rec_name', searcher='search_rec_name')
    icon = fields.Selection('list_icons', 'Icon', translate=False)
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
        self._constraints += [
            ('check_recursion', 'recursive_menu'),
            ('check_name', 'wrong_name'),
        ]
        self._error_messages.update({
            'recursive_menu': 'You can not create recursive menu!',
            'wrong_name': 'You can not use "%s" in name field!' % SEPARATOR,
        })

    def default_icon(self):
        return 'tryton-open'

    def default_sequence(self):
        return 10

    def default_active(self):
        return True

    def list_icons(self):
        pool = Pool()
        icon_obj = pool.get('ir.ui.icon')
        return sorted(CLIENT_ICONS
            + [(name, name) for _, name in icon_obj.list_icons()])

    def check_name(self, ids):
        for menu in self.browse(ids):
            if SEPARATOR in menu.name:
                return False
        return True

    def get_rec_name(self, ids, name):
        if not ids:
            return {}
        res = {}
        def _name(menu):
            if menu.id in res:
                return res[menu.id]
            elif menu.parent:
                return _name(menu.parent) + SEPARATOR + menu.name
            else:
                return menu.name
        for menu in self.browse(ids):
            res[menu.id] = _name(menu)
        return res

    def search_rec_name(self, name, clause):
        if isinstance(clause[2], basestring):
            values = clause[2].split(SEPARATOR)
            values.reverse()
            domain = []
            field = 'name'
            for name in values:
                domain.append((field, clause[1], name))
                field = 'parent.' + field
            ids = self.search(domain, order=[])
            return [('id', 'in', ids)]
        #TODO Handle list
        return [('name',) + tuple(clause[1:])]

    def search(self, domain, offset=0, limit=None, order=None, count=False,
            query_string=False):
        res = super(UIMenu, self).search(domain, offset=offset, limit=limit,
                order=order, count=False, query_string=query_string)
        if query_string:
            return res

        if res:
            menus = self.browse(res)
            parent_ids = [x.parent.id for x in menus if x.parent]
            parent_ids = self.search([
                ('id', 'in', parent_ids),
                ])
            res = [x.id for x in menus
                    if (x.parent.id in parent_ids) or not x.parent]

        if count:
            return len(res)
        return res

    def get_action(self, ids, name):
        pool = Pool()
        action_keyword_obj = pool.get('ir.action.keyword')
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
            action_obj = pool.get(action_keyword.action.type)
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
        pool = Pool()
        action_keyword_obj = pool.get('ir.action.keyword')
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
        action_obj = pool.get(action_type)
        action = action_obj.browse(int(action_id))
        for menu_id in ids:
            with Transaction().set_context(_timestamp=False):
                action_keyword_obj.create({
                    'keyword': 'tree_open',
                    'model': self._name + ',' + str(menu_id),
                    'action': action.action.id,
                    })

UIMenu()
