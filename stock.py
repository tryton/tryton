#This file is part of Tryton.  The COPYRIGHT file at the top level
#of this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Not, Eval, Bool
from trytond.transaction import Transaction
from trytond.backend import TableHandler


class Location(ModelSQL, ModelView):
    "Stock Location"
    _name = 'stock.location'
    sequence = fields.Integer('Sequence',
        order_field='(%(table)s.sequence IS NULL) %(order)s, '
        '%(table)s.sequence %(order)s',
        states={
            'readonly': Not(Bool(Eval('active'))),
            },
        depends=['active'])

    def __init__(self):
        super(Location, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))

    def init(self, module_name):
        cursor = Transaction().cursor
        table = TableHandler(cursor, self, module_name)

        super(Location, self).init(module_name)

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')

Location()
