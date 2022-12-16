# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null
from sql.conditionals import Case

from trytond.model import fields
from trytond.pyson import Not, Eval, Bool
from trytond import backend
from trytond.pool import PoolMeta

__all__ = ['Location']


class Location:
    "Stock Location"
    __metaclass__ = PoolMeta
    __name__ = 'stock.location'
    sequence = fields.Integer('Sequence',
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
        TableHandler = backend.get('TableHandler')
        table = TableHandler(cls, module_name)

        super(Location, cls).__register__(module_name)

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')

    @staticmethod
    def order_sequence(tables):
        table, _ = tables[None]
        return [Case((table.sequence == Null, 0), else_=1), table.sequence]
