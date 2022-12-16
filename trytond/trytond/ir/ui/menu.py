# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from itertools import groupby

from trytond.model import (
    ModelView, ModelSQL, DeactivableMixin, fields, sequence_ordered, tree)
from trytond.transaction import Transaction
from trytond.tools import grouped_slice
from trytond.pool import Pool
from trytond.rpc import RPC


def one_in(i, j):
    """Check the presence of an element of setA in setB
    """
    for k in i:
        if k in j:
            return True
    return False


CLIENT_ICONS = [(x, x) for x in [
        'tryton-add',
        'tryton-archive',
        'tryton-attach',
        'tryton-back',
        'tryton-bookmark-border',
        'tryton-bookmark',
        'tryton-bookmarks',
        'tryton-cancel',
        'tryton-clear',
        'tryton-close',
        'tryton-copy',
        'tryton-create',
        'tryton-date',
        'tryton-delete',
        'tryton-email',
        'tryton-error',
        'tryton-exit',
        'tryton-export',
        'tryton-filter',
        'tryton-format-align-center',
        'tryton-format-align-justify',
        'tryton-format-align-left',
        'tryton-format-align-right',
        'tryton-format-bold',
        'tryton-format-color-text',
        'tryton-format-italic',
        'tryton-format-underline',
        'tryton-forward',
        'tryton-history',
        'tryton-import',
        'tryton-info',
        'tryton-launch',
        'tryton-link',
        'tryton-log',
        'tryton-menu',
        'tryton-note',
        'tryton-ok',
        'tryton-open',
        'tryton-print',
        'tryton-public',
        'tryton-refresh',
        'tryton-remove',
        'tryton-save',
        'tryton-search',
        'tryton-star-border',
        'tryton-star',
        'tryton-switch',
        'tryton-translate',
        'tryton-unarchive',
        'tryton-undo',
        'tryton-warning',
        ]]


class UIMenu(DeactivableMixin, sequence_ordered(), tree(separator=' / '),
        ModelSQL, ModelView):
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
                ], translate=False), 'get_action', setter='set_action')
    action_keywords = fields.One2Many('ir.action.keyword', 'model',
        'Action Keywords')
    favorite = fields.Function(fields.Boolean('Favorite'), 'get_favorite')

    @classmethod
    def order_complete_name(cls, tables):
        return cls.name.convert_order('name', tables, cls)

    @staticmethod
    def default_icon():
        return 'tryton-folder'

    @staticmethod
    def default_sequence():
        return 10

    @staticmethod
    def list_icons():
        pool = Pool()
        Icon = pool.get('ir.ui.icon')
        return sorted(CLIENT_ICONS
            + [(name, name) for _, name in Icon.list_icons()])

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
            parent_ids = {x.parent.id for x in menus if x.parent}
            parents = set()
            for sub_parent_ids in grouped_slice(parent_ids):
                parents.update(cls.search([
                            ('id', 'in', list(sub_parent_ids)),
                            ]))
            # Re-browse to avoid side-cache access
            menus = cls.browse([x.id for x in menus
                    if (x.parent and x.parent in parents) or not x.parent])

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

        def action_type(keyword):
            return keyword.action.type
        action_keywords.sort(key=action_type)
        for type, action_keywords in groupby(action_keywords, key=action_type):
            action_keywords = list(action_keywords)
            action2keywords = defaultdict(list)
            for action_keyword in action_keywords:
                model = action_keyword.model
                actions[model.id] = '%s,-1' % type
                action2keywords[action_keyword.action.id].append(
                    action_keyword)

            Action = pool.get(type)
            with Transaction().set_context(active_test=False):
                factions = Action.search([
                        ('action', 'in', list(action2keywords.keys())),
                        ])
            for action in factions:
                for action_keyword in action2keywords[action.id]:
                    actions[action_keyword.model.id] = str(action)
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
        if isinstance(value, str):
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
