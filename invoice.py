#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import ModelView, ModelSQL, fields


class InvoiceLine(ModelSQL, ModelView):
    _name = 'account.invoice.line'

    def _get_anglo_saxon_move_lines(self, line, amount, type_):
        '''
        Return account move for anglo-saxon stock accounting
        '''
        assert type_.startswith('in_') or type_.startswith('out_'), 'wrong type'

        result = []
        move_line = {}
        move_line['name'] = line.description
        move_line['amount_second_currency'] = Decimal('0.0')
        move_line['second_currency'] = False

        if type_.startswith('in_'):
            move_line['debit'] = amount
            move_line['credit'] = Decimal('0.0')
            account_type = type_[3:]
        else:
            move_line['debit'] = Decimal('0.0')
            move_line['credit'] = amount
            account_type = type_[4:]
        move_line['account'] = getattr(line.product,
                'account_stock_%s_used' % account_type).id

        result.append(move_line)
        move_line = move_line.copy()
        move_line['debit'], move_line['credit'] = \
                move_line['credit'], move_line['debit']
        if type_.endswith('supplier'):
            move_line['account'] = line.account.id
        else:
            move_line['account'] = line.product.account_cogs_used.id
        result.append(move_line)
        return result

    def get_move_line(self, line):
        purchase_line_invoice_line_obj = self.pool.get(
                'purchase.line-account.invoice.line')
        move_obj = self.pool.get('stock.move')
        currency_obj = self.pool.get('currency.currency')

        result = super(InvoiceLine, self).get_move_line(line)

        if line.type != 'line':
            return result
        if not line.product:
            return result
        if line.product.type == 'service':
            return result

        moves = []
        # other types will get current cost price
        if line.invoice.type == 'in_invoice':
            moves = [move for purchase_line in line.purchase_lines
                    for move in purchase_line.moves
                    if move.state == 'done']
        elif line.invoice.type == 'out_invoice':
            moves = [move for sale_line in line.sale_lines
                    for move in sale_line.moves
                    if move.state == 'done']
        if line.invoice.type == 'in_invoice':
            type_ = 'in_supplier'
        elif line.invoice.type == 'out_invoice':
            type_ = 'out_customer'
        elif line.invoice.type == 'in_credit_note':
            type_ = 'out_supplier'
        elif line.invoice.type == 'out_credit_note':
            type_ = 'in_customer'

        moves.sort(lambda x, y: cmp(x.effective_date, y.effective_date))
        cost = move_obj.update_anglo_saxon_quantity_product_cost(
                line.product, moves, line.quantity, line.unit, type_)
        cost = currency_obj.round(line.invoice.currency, cost)

        anglo_saxon_move_lines = self._get_anglo_saxon_move_lines(line, cost,
                type_)
        result.extend(anglo_saxon_move_lines)
        return result

InvoiceLine()
