# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model import ModelView, dualmethod
from trytond.modules.account.exceptions import PostError
from trytond.pool import Pool, PoolMeta


class Journal(metaclass=PoolMeta):
    __name__ = 'account.journal'

    @classmethod
    def __setup__(cls):
        super(Journal, cls).__setup__()
        cls.type.selection.append(('statement', "Statement"))


class Move(metaclass=PoolMeta):
    __name__ = 'account.move'

    @classmethod
    def _get_origin(cls):
        return super(Move, cls)._get_origin() + ['account.statement']

    @dualmethod
    @ModelView.button
    def post(cls, moves):
        pool = Pool()
        Statement = pool.get('account.statement')
        for move in moves:
            if (isinstance(move.origin, Statement)
                    and move.origin.state != 'posted'):
                raise PostError(
                    gettext('account_statement.msg_post_statement_move',
                        move=move.rec_name,
                        statement=move.origin.rec_name))
        super().post(moves)


class MoveLine(metaclass=PoolMeta):
    __name__ = 'account.move.line'

    @classmethod
    def _get_origin(cls):
        return super()._get_origin() + ['account.statement.line']
