# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
import operator
from trytond.pool import Pool, PoolMeta

__all__ = ['InvoiceLine']


class InvoiceLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice.line'

    def _get_anglo_saxon_move_lines(self, amount, type_):
        '''
        Return account move for anglo-saxon stock accounting
        '''
        assert type_.startswith('in_') or type_.startswith('out_'), \
            'wrong type'

        result = []
        move_line = {}
        move_line['description'] = self.description
        move_line['amount_second_currency'] = None
        move_line['second_currency'] = None

        if type_.startswith('in_'):
            move_line['debit'] = amount
            move_line['credit'] = Decimal('0.0')
            account_type = type_[3:]
        else:
            move_line['debit'] = Decimal('0.0')
            move_line['credit'] = amount
            account_type = type_[4:]
        move_line['account'] = getattr(self.product,
                'account_stock_%s_used' % account_type).id

        result.append(move_line)
        move_line = move_line.copy()
        move_line['debit'], move_line['credit'] = \
            move_line['credit'], move_line['debit']
        if type_.endswith('supplier'):
            move_line['account'] = self.account.id
        else:
            move_line['account'] = self.product.account_cogs_used.id
        result.append(move_line)
        return result

    @property
    def _anglo_saxon_stock_moves(self):
        pool = Pool()
        PurchaseLine = pool.get('purchase.line')
        SaleLine = pool.get('sale.line')
        if isinstance(self.origin, (PurchaseLine, SaleLine)):
            return list(self.origin.moves)
        return []

    def get_move_line(self):
        pool = Pool()
        Move = pool.get('stock.move')
        Period = pool.get('account.period')

        result = super(InvoiceLine, self).get_move_line()

        if self.type != 'line':
            return result
        if not self.product:
            return result
        if self.product.type != 'goods':
            return result

        accounting_date = (self.invoice.accounting_date
            or self.invoice.invoice_date)
        period_id = Period.find(self.invoice.company.id, date=accounting_date)
        period = Period(period_id)
        if period.fiscalyear.account_stock_method != 'anglo_saxon':
            return result

        # an empty list means we'll use the current cost price
        moves = [move for move in self._anglo_saxon_stock_moves
            if move.state == 'done']
        if self.invoice.type == 'in':
            type_ = 'in_supplier'
        elif self.invoice.type == 'out':
            type_ = 'out_customer'
        if self.quantity < 0:
            direction, target = type_.split('_')
            if direction == 'in':
                direction = 'out'
            else:
                direction = 'in'
            type_ = '%s_%s' % (direction, target)

        moves.sort(key=operator.attrgetter('effective_date'))
        cost = Move.update_anglo_saxon_quantity_product_cost(
            self.product, moves, abs(self.quantity), self.unit, type_)
        cost = self.invoice.currency.round(cost)

        anglo_saxon_move_lines = self._get_anglo_saxon_move_lines(cost, type_)
        result.extend(anglo_saxon_move_lines)
        return result
