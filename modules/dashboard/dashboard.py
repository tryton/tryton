# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields, sequence_ordered
from trytond import backend
from trytond.pyson import Eval

__all__ = ['DashboardAction']


class DashboardAction(sequence_ordered(), ModelSQL, ModelView):
    "Dashboard Action"
    __name__ = "dashboard.action"
    user = fields.Many2One('res.user', 'User', required=True,
            select=True)
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
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        table = TableHandler(cls, module_name)

        super(DashboardAction, cls).__register__(module_name)

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')
