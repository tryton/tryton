#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import math
from lxml import etree
from trytond.model import Model
from trytond.transaction import Transaction
from trytond.cache import Cache
from trytond.pool import Pool


class View(Model):
    _name = 'ir.ui.view'

    def dashboard_id(self):
        '''
        Return the database id of view_dashboard

        :param user: the user id
        :return: an integer
        '''
        model_data_obj = Pool().get('ir.model.data')
        model_data_ids = model_data_obj.search([
            ('fs_id', '=', 'view_dashboard'),
            ('module', '=', 'dashboard'),
            ('inherit', '=', None),
            ], limit=1)
        if not model_data_ids:
            return 0
        model_data = model_data_obj.browse(model_data_ids[0])
        return model_data.db_id

    dashboard_id = Cache('ir.ui.view.dashboard_id')(dashboard_id)

    def _dashboard_element_action(self, action):
        '''
        Return etree Element for the given dashboard action.

        :param action: a BrowseRecord of dashboard.action
        :return: an etree Element
        '''
        return etree.Element('action', {
            'name': str(action.act_window.id),
            })

    def dashboard_view(self, arch):
        '''
        Add action to view arch of dashboard

        :param arch: a string with the xml arch of dashboard
        :return: a string with the new xml arch
        '''
        user_obj = Pool().get('res.user')
        tree = etree.fromstring(arch)
        root = tree.getroottree().getroot()
        user = user_obj.browse(Transaction().user)
        if user.dashboard_layout == 'square':
            root.set('col', str(int(math.ceil(math.sqrt(
                len(user.dashboard_actions))))))
            for action in user.dashboard_actions:
                root.append(self._dashboard_element_action(action))
        elif user.dashboard_layout == 'stack_right':
            group = None
            root.set('col', '2')
            for action in user.dashboard_actions:
                element = self._dashboard_element_action(action)
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
                element = self._dashboard_element_action(action)
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
                element = self._dashboard_element_action(action)
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
                element = self._dashboard_element_action(action)
                if first:
                    first = False
                    root.append(element)
                else:
                    group.append(element)
            root.append(group)
        arch = etree.tostring(tree, encoding='utf-8')
        return arch

    def read(self, ids, fields_names=None):
        res = super(View, self).read(ids, fields_names=fields_names)
        if Transaction().user == 0:
            return res
        dashboard_id = self.dashboard_id()
        if not dashboard_id:
            # Restart the cache
            self.dashboard_id.reset()
        if fields_names is None \
                or 'arch' in fields_names:
            if isinstance(ids, (int, long)):
                if dashboard_id == ids:
                    res['arch'] = self.dashboard_view(res['arch'])
            elif dashboard_id in ids:
                for res2 in res:
                    if res2['id'] == dashboard_id:
                        res2['arch'] = self.dashboard_view(res2['arch'])
        return res

View()
