# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import account

__all__ = ['register']


def register():
    Pool.register(
        account.Move,
        account.MoveLine,
        account.MoveLineGroup,
        account.MoveLineGroup_MoveLine,
        module='account_move_line_grouping', type_='model')
    Pool.register(
        account.OpenAccount,
        module='account_move_line_grouping', type_='wizard')
