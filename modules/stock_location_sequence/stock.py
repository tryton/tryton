#This file is part of Tryton.  The COPYRIGHT file at the top level
#of this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Not, Eval, Bool
from trytond.transaction import Transaction
from trytond.backend import TableHandler
from trytond.pool import PoolMeta

__all__ = ['Location']
__metaclass__ = PoolMeta


class Location:
    "Stock Location"
    __name__ = 'stock.location'
    sequence = fields.Integer('Sequence',
        order_field='(%(table)s.sequence IS NULL) %(order)s, '
        '%(table)s.sequence %(order)s',
        states={
            'readonly': Not(Bool(Eval('active'))),
            },
        depends=['active'])

    @classmethod
    def __setup__(cls):
        super(Location, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

        super(Location, cls).__register__(module_name)

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')
