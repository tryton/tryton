# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, Workflow
from trytond.pool import PoolMeta, Pool


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    @classmethod
    def check_over_shipment(cls, moves):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        for move in moves:
            if isinstance(move.origin, SaleLine):
                move.origin.check_over_shipment()

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def do(cls, moves):
        super(Move, cls).do(moves)
        cls.check_over_shipment(moves)

    @classmethod
    @ModelView.button
    @Workflow.transition('assigned')
    def assign(cls, moves):
        super(Move, cls).assign(moves)
        cls.check_over_shipment(moves)
