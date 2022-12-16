# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import dashboard, ir, res


def register():
    Pool.register(
        dashboard.Action,
        res.User,
        ir.View,
        module='dashboard', type_='model')
