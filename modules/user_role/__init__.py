# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import res
from . import ir

__all__ = ['register']


def register():
    Pool.register(
        res.Role,
        res.RoleGroup,
        res.User,
        res.UserRole,
        ir.Cron,
        module='user_role', type_='model')
    Pool.register(
        module='user_role', type_='wizard')
    Pool.register(
        module='user_role', type_='report')
