# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby

from trytond.model import ModelView, ModelSQL, fields, sequence_ordered
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.rpc import RPC

__all__ = [
    'UIMenu', 'UIMenuFavorite',
    ]


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


class UIMenu(sequence_ordered(), ModelSQL, ModelView):
    "UI menu"
    __name__ = 'ir.ui.menu'

    name = fields.Char('Menu', required=True, translate=True)
    childs = fields.One2Many('ir.ui.menu', 'parent', 'Children')
    parent = fields.Many2One('ir.ui.menu', 'Parent Menu', select=True,
            ondelete='CASCADE')
    groups = fields.Many2Many('ir.ui.menu-res.group',
       'menu', 'group', 'Groups')
    complete_name = fields.Function(fields.Char('Complete Name'),
        'get_rec_name', searcher='search_rec_name')
    icon = fields.Selection('list_icons', 'Icon', translate=False)
    action = fields.Function(fields.Reference('Action',
            selection=[
                ('', ''),
                ('ir.action.report', 'ir.action.report'),
                ('ir.action.act_window', 'ir.action.act_window'),
                ('ir.action.wizard', 'ir.action.wizard'),
                ('ir.action.url', 'ir.action.url'),
                ]), 'get_action', setter='set_action')
    action_keywords = fields.One2Many('ir.action.keyword', 'model',
        'Action Keywords')
    active = fields.Boolean('Active')
    favorite = fields.Function(fields.Boolean('Favorite'), 'get_favorite')

    @classmethod
    def __setup__(cls):
        super(UIMenu, cls).__setup__()
        cls._error_messages.update({
                'wrong_name': ('"%%s" is not a valid menu name because it is '
                    'not allowed to contain "%s".' % SEPARATOR),
                })

    @classmethod
    def order_complete_name(cls, tables):
        return cls.name.convert_order('name', tables, cls)

    @staticmethod
    def default_icon():
        return 'tryton-open'

    @staticmethod
    def default_sequence():
        return 10

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def list_icons():
        pool = Pool()
        Icon = pool.get('ir.ui.icon')
        return sorted(CLIENT_ICONS
            + [(name, name) for _, name in Icon.list_icons()])

    @classmethod
    def validate(cls, menus):
        super(UIMenu, cls).validate(menus)
        cls.check_recursion(menus)
        for menu in menus:
            menu.check_name()

    def check_name(self):
        if SEPARATOR in self.name:
            self.raise_user_error('wrong_name', (self.name,))

    def get_rec_name(self, name):
        parent = self.parent
        name = self.name
        while parent:
            name = parent.name + SEPARATOR + name
            parent = parent.parent
        return name

    @classmethod
    def search_rec_name(cls, name, clause):
        if isinstance(clause[2], basestring):
            values = clause[2].split(SEPARATOR.strip())
            values.reverse()
            domain = []
            field = 'name'
            for name in values:
                domain.append((field, clause[1], name.strip()))
                field = 'parent.' + field
        else:
            domain = [('name',) + tuple(clause[1:])]
        ids = [m.id for m in cls.search(domain, order=[])]
        return [('parent', 'child_of', ids)]

    @classmethod
    def search_global(cls, text):
        # TODO improve search clause
        for record in cls.search([
                    ('rec_name', 'ilike', '%%%s%%' % text),
                    ]):
            if record.action:
                yield record, record.rec_name, record.icon

    @classmethod
    def search(cls, domain, offset=0, limit=None, order=None, count=False,
            query=False):
        menus = super(UIMenu, cls).search(domain, offset=offset, limit=limit,
                order=order, count=False, query=query)
        if query:
            return menus

        if menus:
            parent_ids = [x.parent.id for x in menus if x.parent]
            parents = cls.search([
                    ('id', 'in', parent_ids),
                    ])
            menus = [x for x in menus
                if (x.parent and x.parent in parents) or not x.parent]

        if count:
            return len(menus)
        return menus

    @classmethod
    def get_action(cls, menus, name):
        pool = Pool()
        actions = dict((m.id, None) for m in menus)
        with Transaction().set_context(active_test=False):
            menus = cls.browse(menus)
        action_keywords = sum((list(m.action_keywords) for m in menus), [])
        key = lambda k: k.action.type
        action_keywords.sort(key=key)
        for type, action_keywords in groupby(action_keywords, key=key):
            action_keywords = list(action_keywords)
            for action_keyword in action_keywords:
                model = action_keyword.model
                actions[model.id] = '%s,-1' % type

            Action = pool.get(type)
            action2keyword = {k.action.id: k for k in action_keywords}
            with Transaction().set_context(active_test=False):
                factions = Action.search([
                        ('action', 'in', action2keyword.keys()),
                        ])
            for action in factions:
                model = action2keyword[action.id].model
                actions[model.id] = str(action)
        return actions

    @classmethod
    def set_action(cls, menus, name, value):
        pool = Pool()
        ActionKeyword = pool.get('ir.action.keyword')
        action_keywords = []
        transaction = Transaction()
        for i in range(0, len(menus), transaction.database.IN_MAX):
            sub_menus = menus[i:i + transaction.database.IN_MAX]
            action_keywords += ActionKeyword.search([
                ('keyword', '=', 'tree_open'),
                ('model', 'in', [str(menu) for menu in sub_menus]),
                ])
        if action_keywords:
            with Transaction().set_context(_timestamp=False):
                ActionKeyword.delete(action_keywords)
        if not value:
            return
        if isinstance(value, basestring):
            action_type, action_id = value.split(',')
        else:
            action_type, action_id = value
        if int(action_id) <= 0:
            return
        Action = pool.get(action_type)
        action = Action(int(action_id))
        to_create = []
        for menu in menus:
            with Transaction().set_context(_timestamp=False):
                to_create.append({
                        'keyword': 'tree_open',
                        'model': str(menu),
                        'action': action.action.id,
                        })
        if to_create:
            ActionKeyword.create(to_create)

    @classmethod
    def get_favorite(cls, menus, name):
        pool = Pool()
        Favorite = pool.get('ir.ui.menu.favorite')
        user = Transaction().user
        favorites = Favorite.search([
                ('menu', 'in', [m.id for m in menus]),
                ('user', '=', user),
                ])
        menu2favorite = dict((m.id, False if m.action else None)
            for m in menus)
        menu2favorite.update(dict((f.menu.id, True) for f in favorites))
        return menu2favorite


class UIMenuFavorite(sequence_ordered(), ModelSQL, ModelView):
    "Menu Favorite"
    __name__ = 'ir.ui.menu.favorite'

    menu = fields.Many2One('ir.ui.menu', 'Menu', required=True,
        ondelete='CASCADE')
    user = fields.Many2One('res.user', 'User', required=True,
        ondelete='CASCADE')

    @classmethod
    def __setup__(cls):
        super(UIMenuFavorite, cls).__setup__()
        cls.__rpc__.update({
                'get': RPC(),
                'set': RPC(readonly=False),
                'unset': RPC(readonly=False),
                })

    @staticmethod
    def default_user():
        return Transaction().user

    @classmethod
    def get(cls):
        user = Transaction().user
        favorites = cls.search([
                ('user', '=', user),
                ])
        return [(f.menu.id, f.menu.rec_name, f.menu.icon) for f in favorites]

    @classmethod
    def set(cls, menu_id):
        user = Transaction().user
        cls.create([{
                    'menu': menu_id,
                    'user': user,
                    }])

    @classmethod
    def unset(cls, menu_id):
        user = Transaction().user
        favorites = cls.search([
                ('menu', '=', menu_id),
                ('user', '=', user),
                ])
        cls.delete(favorites)
