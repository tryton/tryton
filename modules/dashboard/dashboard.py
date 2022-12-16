# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null
from sql.conditionals import Case

from trytond.model import ModelView, ModelSQL, fields
from trytond import backend
from trytond.pyson import Eval

__all__ = ['DashboardAction']


class DashboardAction(ModelSQL, ModelView):
    "Dashboard Action"
    __name__ = "dashboard.action"
    user = fields.Many2One('res.user', 'User', required=True,
            select=True)
    sequence = fields.Integer('Sequence')
    act_window = fields.Many2One('ir.action.act_window', 'Action',
            required=True, ondelete='CASCADE', domain=[
                ('res_model', '!=', None),
                ('res_model', '!=', ''),
                ('usage', '=', 'dashboard'),
                # XXX copy ir.action rule to prevent access rule error
                ['OR',
                    ('groups', 'in', Eval('context', {}).get('groups', [])),
                    ('groups', '=', None),
                ],
            ])

    @classmethod
    def __setup__(cls):
        super(DashboardAction, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        table = TableHandler(cls, module_name)

        super(DashboardAction, cls).__register__(module_name)

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')

    @staticmethod
    def order_sequence(tables):
        table, _ = tables[None]
        return [Case((table.sequence == Null, 0), else_=1), table.sequence]
