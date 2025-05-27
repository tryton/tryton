# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model import ModelView, dualmethod, fields
from trytond.modules.account.exceptions import PostError
from trytond.pool import Pool, PoolMeta


class Journal(metaclass=PoolMeta):
    __name__ = 'account.journal'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.type.selection.append(('statement', "Statement"))


class Move(metaclass=PoolMeta):
    __name__ = 'account.move'

    statement_lines = fields.One2Many(
        'account.statement.line', 'move', "Statement Lines", readonly=True)

    @classmethod
    def _get_origin(cls):
        return super()._get_origin() + ['account.statement']

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

    @classmethod
    def copy(cls, moves, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('statement_lines')
        return super().copy(moves, default=default)


class MoveLine(metaclass=PoolMeta):
    __name__ = 'account.move.line'

    @classmethod
    def _get_origin(cls):
        return super()._get_origin() + ['account.statement.line']

    @fields.depends('move', '_parent_move.statement_lines')
    def on_change_with_description_used(self, name=None):
        description = super().on_change_with_description_used(name=name)
        if (not description
                and self.move
                and getattr(self.move, 'statement_lines', None)):
            for statement_line in self.move.statement_lines:
                if statement_line.description:
                    description = statement_line.description
                    break
        return description

    @classmethod
    def search_description_used(cls, name, clause):
        operator = clause[1]
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        domain = [bool_op,
            super().search_description_used(name, clause),
            ('move.statement_lines.description', *clause[1:]),
            ]
        return domain
