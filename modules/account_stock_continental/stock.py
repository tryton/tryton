# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.model import Workflow, ModelView
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    def _get_account_stock_move_lines(self, type_):
        '''
        Return move lines for stock move
        '''
        pool = Pool()
        Uom = pool.get('product.uom')
        AccountMoveLine = pool.get('account.move.line')
        Currency = pool.get('currency.currency')
        assert type_.startswith('in_') or type_.startswith('out_'), \
            'wrong type'

        move_line = AccountMoveLine()
        if ((
                    type_.endswith('supplier')
                    or type_ == 'in_production')
                and self.product.cost_price_method != 'fixed'):
            with Transaction().set_context(date=self.effective_date):
                unit_price = Currency.compute(self.currency, self.unit_price,
                    self.company.currency, round=False)
        else:
            unit_price = Uom.compute_price(self.product.default_uom,
                self.cost_price, self.uom)
        amount = self.company.currency.round(
                Decimal(str(self.quantity)) * unit_price)

        if type_.startswith('in_'):
            move_line.debit = Decimal('0.0')
            move_line.credit = amount
            move_line.account = self.product.account_stock_in_used
        else:
            move_line.debit = amount
            move_line.credit = Decimal('0.0')
            move_line.account = self.product.account_stock_out_used

        return [move_line]

    def _get_account_stock_move_line(self, amount):
        '''
        Return counterpart move line value for stock move
        '''
        pool = Pool()
        AccountMoveLine = pool.get('account.move.line')
        move_line = AccountMoveLine(
            account=self.product.account_stock_used,
            )
        if not amount:
            return
        if amount >= Decimal('0.0'):
            move_line.debit = Decimal('0.0')
            move_line.credit = amount
        else:
            move_line.debit = - amount
            move_line.credit = Decimal('0.0')
        return move_line

    def _get_account_stock_move_type(self):
        '''
        Get account move type
        '''
        type_ = (self.from_location.type, self.to_location.type)
        if type_ in [('supplier', 'storage'), ('supplier', 'drop')]:
            return 'in_supplier'
        elif type_ in [('storage', 'supplier'), ('drop', 'supplier')]:
            return 'out_supplier'
        elif type_ in [('storage', 'customer'), ('drop', 'customer')]:
            return 'out_customer'
        elif type_ in [('customer', 'storage'), ('customer', 'drop')]:
            return 'in_customer'
        elif type_ == ('storage', 'lost_found'):
            return 'out_lost_found'
        elif type_ == ('lost_found', 'storage'):
            return 'in_lost_found'
        elif type_ == ('supplier', 'customer'):
            return 'supplier_customer'
        elif type_ == ('customer', 'supplier'):
            return 'customer_supplier'
        elif type_ == ('storage', 'production'):
            return 'out_production'
        elif type_ == ('production', 'storage'):
            return 'in_production'

    def _get_account_stock_move(self):
        '''
        Return account move for stock move
        '''
        pool = Pool()
        AccountMove = pool.get('account.move')
        Date = pool.get('ir.date')
        Period = pool.get('account.period')
        AccountConfiguration = pool.get('account.configuration')

        if self.product.type != 'goods':
            return

        date = self.effective_date or Date.today()
        period_id = Period.find(self.company.id, date=date)
        period = Period(period_id)
        if not period.fiscalyear.account_stock_method:
            return

        type_ = self._get_account_stock_move_type()
        if not type_:
            return
        with Transaction().set_context(
                company=self.company.id, date=date):
            if type_ == 'supplier_customer':
                account_move_lines = self._get_account_stock_move_lines(
                    'in_supplier')
                account_move_lines.extend(self._get_account_stock_move_lines(
                        'out_customer'))
            elif type_ == 'customer_supplier':
                account_move_lines = self._get_account_stock_move_lines(
                    'in_customer')
                account_move_lines.extend(self._get_account_stock_move_lines(
                        'out_supplier'))
            else:
                account_move_lines = self._get_account_stock_move_lines(type_)

        amount = Decimal('0.0')
        for line in account_move_lines:
            amount += line.debit - line.credit
        move_line = self._get_account_stock_move_line(amount)
        if move_line:
            account_move_lines.append(move_line)

        account_configuration = AccountConfiguration(1)
        return AccountMove(
            journal=account_configuration.stock_journal,
            period=period_id,
            date=date,
            origin=self,
            lines=account_move_lines,
            )

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def do(cls, moves):
        pool = Pool()
        AccountMove = pool.get('account.move')
        super(Move, cls).do(moves)
        account_moves = []
        for move in moves:
            account_move = move._get_account_stock_move()
            if account_move:
                account_moves.append(account_move)
        AccountMove.save(account_moves)
        AccountMove.post(account_moves)
