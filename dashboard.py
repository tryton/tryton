#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.backend import TableHandler


class DashboardAction(ModelSQL, ModelView):
    "Dashboard Action"
    _name = "dashboard.action"

    user = fields.Many2One('res.user', 'User', required=True,
            select=True)
    sequence = fields.Integer('Sequence',
        order_field='(%(table)s.sequence IS NULL) %(order)s, '
        '%(table)s.sequence %(order)s')
    act_window = fields.Many2One('ir.action.act_window', 'Action',
            required=True, ondelete='CASCADE', domain=[
                ('res_model', '!=', None),
                ('res_model', '!=', ''),
            ])

    def __init__(self):
        super(DashboardAction, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))

    def init(self, module_name):
        cursor = Transaction().cursor
        table = TableHandler(cursor, self, module_name)

        super(DashboardAction, self).init(module_name)

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')

DashboardAction()
