#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from decimal import Decimal
from trytond.transaction import Transaction


class Move(ModelSQL, ModelView):
    _name = 'stock.move'

    account_move = fields.Many2One('account.move', 'Account Move',
            readonly=True)

    def _get_account_stock_move_lines(self, move, type_):
        '''
        Return move line values for stock move
        '''
        uom_obj = self.pool.get('product.uom')
        currency_obj = self.pool.get('currency.currency')
        assert type_.startswith('in_') or type_.startswith('out_'), 'wrong type'

        move_line = {
            'name': move.rec_name,
        }
        if type_.endswith('supplier'):
            with Transaction().set_context(date=move.effective_date):
                unit_price = currency_obj.compute(move.currency.id,
                    move.unit_price, move.company.currency.id, round=False)
        else:
            unit_price = uom_obj.compute_price(move.product.default_uom,
                    move.cost_price, move.uom)
        amount = currency_obj.round(move.company.currency,
                Decimal(str(move.quantity)) * unit_price)

        if type_.startswith('in_'):
            move_line['debit'] = Decimal('0.0')
            move_line['credit'] = amount
            account_type = type_[3:]
        else:
            move_line['debit'] = amount
            move_line['credit'] = Decimal('0.0')
            account_type = type_[4:]

        move_line['account'] = getattr(move.product,
                'account_stock_%s_used' % account_type).id

        return [move_line]

    def _get_account_stock_move_line(self, move, amount):
        '''
        Return counterpart move line value for stock move
        '''
        move_line = {
            'name': move.rec_name,
            'account': move.product.account_stock_used.id,
        }
        if amount >= Decimal('0.0'):
            move_line['debit'] = Decimal('0.0')
            move_line['credit'] = amount
        else:
            move_line['debit'] = - amount
            move_line['credit'] = Decimal('0.0')
        return move_line

    def _get_account_stock_move(self, move, move_lines, type_):
        '''
        Return account move value for stock move
        '''
        date_obj = self.pool.get('ir.date')
        period_obj = self.pool.get('account.period')
        assert type_.startswith('in_') or type_.startswith('out_'), 'wrong type'

        date = move.effective_date or date_obj.today()
        period_id = period_obj.find(move.company.id, date=date)

        if type_.startswith('in_'):
            journal_type = type_[3:]
        else:
            journal_type = type_[4:]

        journal_id = getattr(move.product,
                'account_journal_stock_%s_used' % journal_type).id

        return {
            'journal': journal_id,
            'period': period_id,
            'date': date,
            'lines': [('create', line) for line in move_lines],
        }

    def _get_account_stock_move_type(self, move):
        '''
        Get account move type
        '''
        type_ = (move.from_location.type, move.to_location.type)
        if type_ == ('supplier', 'storage'):
            return 'in_supplier'
        elif type_ == ('storage', 'supplier'):
            return 'out_supplier'
        elif type_ == ('storage', 'customer'):
            return 'out_customer'
        elif type_ == ('customer', 'storage'):
            return 'in_customer'
        elif type_ == ('storage', 'lost_found'):
            return 'out_lost_found'
        elif type_ == ('lost_found', 'storage'):
            return 'in_lost_found'

    def _create_account_stock_move(self, move):
        '''
        Create account move for stock move
        '''
        account_move_obj = self.pool.get('account.move')
        type_ = self._get_account_stock_move_type(move)
        if not type_:
            return
        assert not move.account_move, 'account move field not empty'
        account_move_lines = self._get_account_stock_move_lines(move, type_)

        amount = Decimal('0.0')
        for line in account_move_lines:
            amount += line['debit'] - line['credit']
        account_move_lines.append(
                self._get_account_stock_move_line(move, amount))

        with Transaction().set_user(0, set_context=True):
            account_move_id = account_move_obj.create(
                    self._get_account_stock_move(move, account_move_lines, type_))
        self.write(move.id, {
            'account_move': account_move_id,
            })
        account_move_obj.post(account_move_id)
        return account_move_id

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default.setdefault('account_move', None)
        return super(Move, self).copy(ids, default=default)

    def create(self, vals):
        new_id = super(Move, self).create(vals)
        if vals.get('state') == 'done':
            move = self.browse(new_id)
            self._create_account_stock_move(move)
        return new_id

    def write(self, ids, vals):
        res = super(Move, self).write(ids, vals)
        if vals.get('state') == 'done':
            if isinstance(ids, (int, long)):
                move = self.browse(ids)
                self._create_account_stock_move(move)
            else:
                for move in self.browse(ids):
                    self._create_account_stock_move(move)
        return res

Move()
