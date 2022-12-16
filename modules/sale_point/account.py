# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


class Move(metaclass=PoolMeta):
    __name__ = 'account.move'

    @classmethod
    def _get_origin(cls):
        return super()._get_origin() + [
            'sale.point.sale', 'sale.point.cash.transfer']


class MoveLine(metaclass=PoolMeta):
    __name__ = 'account.move.line'

    @classmethod
    def _get_origin(cls):
        return super()._get_origin() + [
            'sale.point.sale.line', 'sale.point.payment']
