# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import json
from collections import defaultdict

from sql import Literal
from sql.aggregate import Count

from trytond.bus import Bus
from trytond.ir.ui.menu import CLIENT_ICONS
from trytond.model import Index, ModelSQL, ModelView, fields
from trytond.pool import Pool
from trytond.pyson import Bool, Eval
from trytond.rpc import RPC
from trytond.transaction import Transaction


class Notification(
        fields.fmany2one(
            'model_ref', 'model', 'ir.model,name', "Model",
            ondelete='CASCADE'),
        ModelSQL, ModelView):
    __name__ = 'res.notification'

    user = fields.Many2One(
        'res.user', "User", required=True, ondelete='CASCADE',
        states={
            'readonly': Eval('id', 0) > 0,
            })
    label = fields.Char("Label")
    description = fields.Char("Description")
    icon = fields.Selection('list_icons', 'Icon', translate=False)
    unread = fields.Boolean("Unread")
    model = fields.Char(
        "Model",
        states={
            'required': Bool(Eval('records')),
            })
    records = fields.Char(
        "Records",
        states={
            'required': Bool(Eval('model')),
            })
    action = fields.Many2One(
        'ir.action', "Action", ondelete='CASCADE',
        states={
            'required': Bool(Eval('action_value')),
            })
    action_value = fields.Char("Action Value")

    @classmethod
    def __setup__(cls):
        super().__setup__()

        cls.__rpc__.update({
                'get': RPC(),
                'get_count': RPC(),
                'mark_read': RPC(
                    readonly=False, instantiate=0, check_access=False),
                })

        table = cls.__table__()
        cls._sql_indexes.update({
                Index(
                    table,
                    (table.user, Index.Equality()),
                    where=table.unread),
                Index(table, (table.user, Index.Equality())),
                })

    @classmethod
    def default_unread(cls):
        return True

    @classmethod
    def copy(cls, notifications, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('unread', True)
        return super().copy(notifications, default=default)

    @classmethod
    def create(cls, vlist):
        notifications = super().create(vlist)

        notifications_by_user = defaultdict(list)
        for notification in notifications:
            notifications_by_user[notification.user.id].append(
                notification)

        notification = cls.__table__()
        cursor = Transaction().connection.cursor()
        cursor.execute(*notification.select(
                notification.user, Count(Literal('*')),
                where=((notification.user.in_(list(notifications_by_user)))
                    & notification.unread),
                group_by=[notification.user]))
        for user, count in cursor.fetchall():
            messages = [
                '\n'.join(filter(None, (n.label, n.description)))
                for n in notifications_by_user[user]]
            Bus.publish(
                f'notification:{user}', {
                    'type': 'user-notification',
                    'count': count,
                    'content': messages,
                    })

        return notifications

    @classmethod
    def list_icons(cls):
        pool = Pool()
        Icon = pool.get('ir.ui.icon')
        return sorted(CLIENT_ICONS
            + [(name, name) for _, name in Icon.list_icons()]
            + [(None, "")],
            key=lambda e: e[1])

    @property
    def _action_value(self):
        if self.action_value:
            action_value = self.action.get_action_value()
            action_value.update(json.loads(self.action_value))
            return action_value
        elif self.action:
            return self.action.id

    @classmethod
    def get(cls, count=10):
        "Get the last count notifications"
        notifications = cls.search([
                ('user', '=', Transaction().user),
                ],
            limit=count, order=[('create_date', 'DESC'), ('id', 'DESC')])
        return [{
                'id': n.id,
                'label': n.label,
                'description': n.description,
                'icon': n.icon,
                'model': n.model,
                'records': json.loads(n.records) if n.records else None,
                'action': n._action_value,
                'unread': bool(n.unread),
                } for n in notifications]

    @classmethod
    def get_count(cls):
        notification = cls.__table__()
        cursor = Transaction().connection.cursor()
        cursor.execute(*notification.select(
                Count(Literal('*')),
                where=((notification.user == Transaction().user)
                    & notification.unread)))
        return cursor.fetchone()[0]

    @classmethod
    def mark_read(cls, notifications):
        current_user = Transaction().user
        notifications = [n for n in notifications if n.user.id == current_user]
        cls.write(notifications, {'unread': False})
