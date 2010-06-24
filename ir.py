#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import Model, fields
from trytond.tools import Cache
from lxml import etree
import math


class View(Model):
    _name = 'ir.ui.view'

    def dashboard_id(self, cursor, user, context=None):
        '''
        Return the database id of view_dashboard

        :param cursor: the database cursor
        :param user: the user id
        :param context: the context
        :return: an integer
        '''
        model_data_obj = self.pool.get('ir.model.data')
        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'view_dashboard'),
            ('module', '=', 'dashboard'),
            ('inherit', '=', False),
            ], limit=1, context=context)
        if not model_data_ids:
            return 0
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        return model_data.db_id

    dashboard_id = Cache('ir.ui.view.dashboard_id')(dashboard_id)

    def _dashboard_element_action(self, cursor, user, action,
            context=None):
        '''
        Return etree Element for the given dashboard action.

        :param cursor: the database cursor
        :param user: the user id
        :param action: a BrowseRecord of dashboard.action
        :param context: the context
        :return: an etree Element
        '''
        return etree.Element('action', {
            'name': str(action.act_window.id),
            })

    def dashboard_view(self, cursor, user_id, arch, context=None):
        '''
        Add action to view arch of dashboard

        :param cursor: the database cursor
        :param user_id: the user id
        :param arch: a string with the xml arch of dashboard
        :param context: the context
        :return: a string with the new xml arch
        '''
        user_obj = self.pool.get('res.user')
        tree = etree.fromstring(arch)
        root = tree.getroottree().getroot()
        user = user_obj.browse(cursor, user_id, user_id, context=context)
        if user.dashboard_layout == 'square':
            root.set('col', str(int(math.ceil(math.sqrt(
                len(user.dashboard_actions))))))
            for action in user.dashboard_actions:
                root.append(self._dashboard_element_action(cursor,
                    user_id, action, context=context))
        elif user.dashboard_layout == 'stack_right':
            group = None
            root.set('col', '2')
            for action in user.dashboard_actions:
                element = self._dashboard_element_action(cursor,
                        user_id, action, context=context)
                if group is None:
                    root.append(element)
                    group = etree.Element('group', {
                        'col': '1',
                        })
                    root.append(group)
                else:
                    group.append(element)
        elif user.dashboard_layout == 'stack_left':
            root.set('col', '2')
            group = etree.Element('group', {
                'col': '1',
                })
            root.append(group)
            first = True
            for action in user.dashboard_actions:
                element = self._dashboard_element_action(cursor,
                        user_id, action, context=context)
                if first:
                    first = False
                    root.append(element)
                else:
                    group.append(element)
        elif user.dashboard_layout == 'stack_top':
            root.set('col', '1')
            group = etree.Element('group', {
                'col': str(len(user.dashboard_actions) - 1),
                'expand': '1',
                })
            root.append(group)
            first = True
            for action in user.dashboard_actions:
                element = self._dashboard_element_action(cursor,
                        user_id, action, context=context)
                if first:
                    first = False
                    root.append(element)
                else:
                    group.append(element)
        elif user.dashboard_layout == 'stack_bottom':
            root.set('col', '1')
            group = etree.Element('group', {
                'col': str(len(user.dashboard_actions) - 1),
                'expand': '1',
                })
            first = True
            for action in user.dashboard_actions:
                element = self._dashboard_element_action(cursor,
                        user_id, action, context=context)
                if first:
                    first = False
                    root.append(element)
                else:
                    group.append(element)
            root.append(group)
        arch = etree.tostring(tree, encoding='utf-8')
        return arch

    def read(self, cursor, user, ids, fields_names=None, context=None):
        res = super(View, self).read(cursor, user, ids,
                fields_names=fields_names, context=context)
        if user == 0:
            return res
        dashboard_id = self.dashboard_id(cursor, user, context=context)
        if not dashboard_id:
            # Restart the cache
            self.dashboard_id(cursor.dbname)
        if fields_names is None \
                or 'arch' in fields_names:
            if isinstance(ids, (int, long)):
                if dashboard_id == ids:
                    res['arch'] = self.dashboard_view(cursor, user,
                            res['arch'], context=context)
            elif dashboard_id in ids:
                for res2 in res:
                    if res2['id'] == dashboard_id:
                        res2['arch'] = self.dashboard_view(cursor, user,
                                res2['arch'], context=context)
        return res

View()
