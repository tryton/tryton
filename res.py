# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If, Bool


class Role(ModelSQL, ModelView):
    "Role"
    __name__ = 'res.role'
    name = fields.Char("Name", required=True, translate=True)
    groups = fields.Many2Many('res.role-res.group', 'role', 'group', "Groups")

    @classmethod
    def write(cls, *args):
        pool = Pool()
        User = pool.get('res.user')
        roles = sum(args[0:None:2], [])
        super().write(*args)

        users = User.search([
                ('roles.role', 'in', [r.id for r in roles]),
                ])
        User.sync_roles(users)


class RoleGroup(ModelSQL):
    "Role - Group"
    __name__ = 'res.role-res.group'
    role = fields.Many2One(
        'res.role', "Role", ondelete='CASCADE', select=True, required=True)
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
    def create(cls, vlist):
        users = super().create(vlist)
        cls.sync_roles(users)
        return users

    @classmethod
    def write(cls, *args):
        users = sum(args[0:None:2], [])
        super().write(*args)
        cls.sync_roles(users)

    @classmethod
    def sync_roles(cls, users=None, date=None):
        pool = Pool()
        Date = pool.get('ir.date')
        if date is None:
            date = Date.today()
        if users is None:
            users = cls.search([])
        to_write = []
        for user in users:
            if not user.roles:
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
    "User Role"
    __name__ = 'res.user.role'
    user = fields.Many2One(
        'res.user', "User", ondelete='CASCADE', select=True, required=True)
    role = fields.Many2One('res.role', "Role", required=True)
    from_date = fields.Date(
        "From Date",
        domain=[
            If(Eval('from_date') & Eval('to_date'),
                ('from_date', '<=', Eval('to_date', None)),
                ()),
            ],
        depends=['to_date'])
    to_date = fields.Date(
        "To Date",
        domain=[
            If(Eval('from_date') & Eval('to_date'),
                ('to_date', '>=', Eval('from_date', None)),
                ()),
            ],
        depends=['from_date'])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('from_date', 'DESC NULLS FIRST'))
        cls._order.insert(1, ('to_date', 'ASC NULLS FIRST'))

    def valid(self, date):
        from_date = self.from_date or datetime.date.min
        to_date = self.to_date or datetime.date.max
        return from_date <= date <= to_date
