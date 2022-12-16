# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import math
from lxml import etree
from trytond.transaction import Transaction
from trytond.cache import Cache
from trytond.pool import Pool, PoolMeta


class View(metaclass=PoolMeta):
    __name__ = 'ir.ui.view'
    _dashboard_cache = Cache('ir.ui.view.dashboard_id')

    @staticmethod
    def dashboard_id():
        '''
        Return the database id of view_dashboard
        '''
        ModelData = Pool().get('ir.model.data')
        models_data = ModelData.search([
                ('fs_id', '=', 'view_dashboard'),
                ('module', '=', 'dashboard'),
                ], limit=1)
        if not models_data:
            return 0
        model_data, = models_data
        return model_data.db_id

    @staticmethod
    def _dashboard_element_action(action):
        '''
        Return etree Element for the given dashboard action.
        '''
        return etree.Element('action', {
                'name': str(action.act_window.id),
                })

    @classmethod
    def dashboard_view(cls, arch):
        '''
        Add action to view arch of dashboard
        '''
        User = Pool().get('res.user')
        tree = etree.fromstring(arch)
        root = tree.getroottree().getroot()
        user = User(Transaction().user)
        if user.dashboard_layout == 'square':
            root.set('col', str(int(math.ceil(math.sqrt(
                len(user.dashboard_actions))))))
            for action in user.dashboard_actions:
                root.append(cls._dashboard_element_action(action))
        elif user.dashboard_layout == 'stack_right':
            group = None
            root.set('col', '2')
            for action in user.dashboard_actions:
                element = cls._dashboard_element_action(action)
                if group is None:
                    root.append(element)
                    group = etree.Element('group', {
                            'col': '1',
                            'yexpand': '1',
                            'yfill': '1',
                            })
                    root.append(group)
                else:
                    group.append(element)
        elif user.dashboard_layout == 'stack_left':
            root.set('col', '2')
            group = etree.Element('group', {
                    'col': '1',
                    'yexpand': '1',
                    'yfill': '1',
                    })
            root.append(group)
            first = True
            for action in user.dashboard_actions:
                element = cls._dashboard_element_action(action)
                if first:
                    first = False
                    root.append(element)
                else:
                    group.append(element)
        elif user.dashboard_layout == 'stack_top':
            root.set('col', '1')
            group = etree.Element('group', {
                    'col': str(len(user.dashboard_actions) - 1),
                    'xexpand': '1',
                    })
            root.append(group)
            first = True
            for action in user.dashboard_actions:
                element = cls._dashboard_element_action(action)
                if first:
                    first = False
                    root.append(element)
                else:
                    group.append(element)
        elif user.dashboard_layout == 'stack_bottom':
            root.set('col', '1')
            group = etree.Element('group', {
                    'col': str(len(user.dashboard_actions) - 1),
                    'xexpand': '1',
                    })
            first = True
            for action in user.dashboard_actions:
                element = cls._dashboard_element_action(action)
                if first:
                    first = False
                    root.append(element)
                else:
                    group.append(element)
            root.append(group)
        arch = etree.tostring(tree, encoding='utf-8').decode('utf-8')
        return arch

    @classmethod
    def read(cls, ids, fields_names):
        res = super(View, cls).read(ids, fields_names)
        if Transaction().user == 0:
            return res
        dashboard_id = cls.dashboard_id()
        if not dashboard_id:
            # Restart the cache
            cls._dashboard_cache.clear()
        if fields_names is None \
                or 'arch' in fields_names:
            if dashboard_id in ids:
                for res2 in res:
                    if res2['id'] == dashboard_id:
                        res2['arch'] = cls.dashboard_view(res2['arch'])
        return res
