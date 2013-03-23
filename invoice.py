#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
import operator
from trytond.pool import Pool, PoolMeta

__all__ = ['InvoiceLine']
__metaclass__ = PoolMeta


class InvoiceLine:
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
        move_line['amount_second_currency'] = Decimal('0.0')
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

    def get_move_line(self):
        pool = Pool()
        Move = pool.get('stock.move')
        PurchaseLine = pool.get('purchase.line')
        SaleLine = pool.get('sale.line')

        result = super(InvoiceLine, self).get_move_line()

        if self.type != 'line':
            return result
        if not self.product:
            return result
        if self.product.type != 'goods':
            return result

        moves = []
        # other types will get current cost price
        if isinstance(self.origin, (PurchaseLine, SaleLine)):
            moves = [move for move in self.origin.moves
                if move.state == 'done']
        if self.invoice.type == 'in_invoice':
            type_ = 'in_supplier'
        elif self.invoice.type == 'out_invoice':
            type_ = 'out_customer'
        elif self.invoice.type == 'in_credit_note':
            type_ = 'out_supplier'
        elif self.invoice.type == 'out_credit_note':
            type_ = 'in_customer'

        moves.sort(key=operator.attrgetter('effective_date'))
        cost = Move.update_anglo_saxon_quantity_product_cost(
            self.product, moves, self.quantity, self.unit, type_)
        cost = self.invoice.currency.round(cost)

        anglo_saxon_move_lines = self._get_anglo_saxon_move_lines(cost, type_)
        result.extend(anglo_saxon_move_lines)
        return result
