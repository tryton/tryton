# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
import operator

from trytond.i18n import gettext
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

from .exceptions import COGSWarning


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    def _get_anglo_saxon_move_lines(self, amount, type_):
        '''
        Return account move for anglo-saxon stock accounting
        '''
        pool = Pool()
        MoveLine = pool.get('account.move.line')

        assert type_.startswith('in_') or type_.startswith('out_'), \
            'wrong type'

        result = []
        move_line = MoveLine()
        move_line.description = self.description
        move_line.amount_second_currency = None
        move_line.second_currency = None

        if type_.startswith('in_'):
            move_line.debit = amount
            move_line.credit = Decimal('0.0')
            move_line.account = self.product.account_stock_in_used
        else:
            move_line.debit = Decimal('0.0')
            move_line.credit = amount
            move_line.account = self.product.account_stock_out_used

        result.append(move_line)
        debit, credit = move_line.debit, move_line.credit
        move_line = MoveLine()
        move_line.description = self.description
        move_line.amount_second_currency = move_line.second_currency = None
        move_line.debit, move_line.credit = credit, debit
        if type_.endswith('supplier'):
            move_line.account = self.account
        else:
            move_line.account = self.product.account_cogs_used
        if move_line.account.party_required:
            move_line.party = self.invoice.party
        result.append(move_line)
        return result

    def get_move_lines(self):
        pool = Pool()
        Move = pool.get('stock.move')
        Period = pool.get('account.period')
        Warning = pool.get('res.user.warning')

        result = super(InvoiceLine, self).get_move_lines()

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
        moves = []
        for move in self.stock_moves:
            if move.state != 'done':
                continue
            # remove move for different product
            if move.product != self.product:
                warning_name = '%s.stock.different_product' % self
                if Warning.check(warning_name):
                    raise COGSWarning(warning_name,
                        gettext('account_stock_anglo_saxon'
                            '.msg_invoice_line_stock_move_different_product',
                            line=self.rec_name,
                            product=self.product.rec_name))
            else:
                moves.append(move)

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
        cost = self.invoice.company.currency.round(cost)

        with Transaction().set_context(
                company=self.invoice.company.id, date=accounting_date):
            anglo_saxon_move_lines = self._get_anglo_saxon_move_lines(
                cost, type_)
        result.extend(anglo_saxon_move_lines)
        return result
