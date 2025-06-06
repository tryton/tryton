# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt

from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, If


class Role(ModelSQL, ModelView):
    __name__ = 'res.role'
    name = fields.Char("Name", required=True, translate=True)
    groups = fields.Many2Many('res.role-res.group', 'role', 'group', "Groups")
    users = fields.One2Many('res.user.role', 'role', "Users")

    @classmethod
    def on_modification(cls, mode, roles, field_names=None):
        pool = Pool()
        User = pool.get('res.user')
        super().on_modification(mode, roles, field_names=field_names)
        if mode == 'write':
            users = {u.user for r in roles for u in r.users}
            User.sync_roles(User.browse(users))

    @classmethod
    def on_delete(cls, roles):
        pool = Pool()
        User = pool.get('res.user')
        callback = super().on_delete(roles)
        if users := {u.user for r in roles for u in r.users}:
            callback.append(lambda: User.sync_roles(
                    User.browse(users), clear=True))
        return callback

    @classmethod
    def copy(cls, roles, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('users')
        return super().copy(roles, default=default)


class RoleGroup(ModelSQL):
    __name__ = 'res.role-res.group'
    role = fields.Many2One(
        'res.role', "Role", ondelete='CASCADE', required=True)
    group = fields.Many2One(
        'res.group', "Group", ondelete='CASCADE', required=True)


class User(metaclass=PoolMeta):
    __name__ = 'res.user'
    roles = fields.One2Many('res.user.role', 'user', "Roles")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        group_readonly = Bool(Eval('roles', []))
        if 'readonly' in cls.groups.states:
            group_readonly |= cls.groups.states['readonly']
        cls.groups.states['readonly'] = group_readonly

        cls._context_fields.append('roles')

    @classmethod
    def on_modification(cls, mode, users, field_names=None):
        super().on_modification(mode, users, field_names=field_names)
        if mode in {'create', 'write'}:
            cls.sync_roles(users)

    @classmethod
    def sync_roles(cls, users=None, date=None, clear=False):
        if date is None:
            date = dt.datetime.now()
        if users is None:
            users = cls.search([])
        to_write = []
        for user in users:
            if not user.roles and not clear:
                continue
            new = {g.id for r in user.roles for g in r.role.groups
                if r.valid(date)}
            old = {g.id for g in user.groups}
            if new != old:
                to_write.append([user])
                to_write.append({'groups': [
                            ('add', new - old),
                            ('remove', old - new),
                            ]})
        if to_write:
            cls.write(*to_write)


class UserRole(ModelSQL, ModelView):
    __name__ = 'res.user.role'
    user = fields.Many2One(
        'res.user', "User", ondelete='CASCADE', required=True)
    role = fields.Many2One(
        'res.role', "Role", ondelete='CASCADE', required=True)
    from_date = fields.DateTime(
        "From Date",
        domain=[
            If(Eval('from_date') & Eval('to_date'),
                ('from_date', '<=', Eval('to_date', None)),
                ()),
            ])
    to_date = fields.DateTime(
        "To Date",
        domain=[
            If(Eval('from_date') & Eval('to_date'),
                ('to_date', '>=', Eval('from_date', None)),
                ()),
            ])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('from_date', 'DESC NULLS FIRST'))
        cls._order.insert(1, ('to_date', 'ASC NULLS FIRST'))

    def valid(self, date):
        from_date = self.from_date or dt.datetime.min
        to_date = self.to_date or dt.datetime.max
        return from_date <= date <= to_date
