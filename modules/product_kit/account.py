# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, Workflow
from trytond.pool import PoolMeta, Pool


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, invoices):
        pool = Pool()
        Move = pool.get('stock.move')
        super().post(invoices)
        moves = sum(
            (l.stock_component_moves for i in invoices for l in i.lines), [])
        if moves:
            Move.__queue__.update_unit_price(moves)


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @property
    def stock_component_moves(self):
        return []


class InvoiceLineSale(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @property
    def stock_component_moves(self):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        moves = super().stock_component_moves
        if isinstance(self.origin, SaleLine):
            for component in self.origin.components:
                moves.extend(component.moves)
        return moves


class InvoiceLinePurchase(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @property
    def stock_component_moves(self):
        pool = Pool()
        PurchaseLine = pool.get('purchase.line')
        moves = super().stock_component_moves
        if isinstance(self.origin, PurchaseLine):
            for component in self.origin.components:
                moves.extend(component.moves)
        return moves
