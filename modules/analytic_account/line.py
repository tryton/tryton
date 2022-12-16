#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import time
from decimal import Decimal
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateAction
from trytond.backend import TableHandler
from trytond.pyson import Eval, PYSONEncoder
from trytond.transaction import Transaction
from trytond.pool import Pool

__all__ = ['Line', 'MoveLine', 'OpenAccount']


class Line(ModelSQL, ModelView):
    'Analytic Line'
    __name__ = 'analytic_account.line'
    name = fields.Char('Name', required=True)
    debit = fields.Numeric('Debit', digits=(16, Eval('currency_digits', 2)),
        required=True, depends=['currency_digits'])
    credit = fields.Numeric('Credit', digits=(16, Eval('currency_digits', 2)),
        required=True, depends=['currency_digits'])
    currency = fields.Function(fields.Many2One('currency.currency', 'Currency',
        on_change_with=['move_line']), 'on_change_with_currency')
    currency_digits = fields.Function(fields.Integer('Currency Digits',
        on_change_with=['move_line']), 'on_change_with_currency_digits')
    account = fields.Many2One('analytic_account.account', 'Account',
            required=True, select=True, domain=[('type', '!=', 'view')])
    move_line = fields.Many2One('account.move.line', 'Account Move Line',
            ondelete='CASCADE', required=True)
    journal = fields.Many2One('account.journal', 'Journal', required=True,
            select=True)
    date = fields.Date('Date', required=True)
    reference = fields.Char('Reference')
    party = fields.Many2One('party.party', 'Party')
    active = fields.Boolean('Active', select=True)

    @classmethod
    def __setup__(cls):
        super(Line, cls).__setup__()
        cls._sql_constraints += [
            ('credit_debit',
                'CHECK((credit * debit = 0.0) AND (credit + debit >= 0.0))',
                'Wrong credit/debit values.'),
            ]
        cls._error_messages.update({
                'line_on_view_account': ('You can not create a move line using '
                    'view account "%s".'),
                'line_on_inactive_account': ('You can not create a move line '
                    'using inactive account "%s".'),
                })
        cls._order.insert(0, ('date', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        super(Line, cls).__register__(module_name)
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

        # Migration from 1.2 currency has been changed in function field
        table.not_null_action('currency', action='remove')

    @staticmethod
    def default_date():
        Date = Pool().get('ir.date')
        return Date.today()

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_debit():
        return Decimal(0)

    @staticmethod
    def default_credit():
        return Decimal(0)

    def on_change_with_currency(self, name=None):
        if self.move_line:
            return self.move_line.account.company.currency.id

    def on_change_with_currency_digits(self, name=None):
        if self.move_line:
            return self.move_line.account.company.currency.digits
        return 2

    @staticmethod
    def query_get(obj='l'):
        '''
        Return SQL clause for analytic line depending of the context.
        obj is the SQL alias of the analytic_account_line in the query.
        '''
        res = obj + '.active'
        if Transaction().context.get('start_date'):
            # Check start_date
            time.strptime(str(Transaction().context['start_date']), '%Y-%m-%d')
            res += (' AND ' + obj + '.date >= date(\''
                + str(Transaction().context['start_date']) + '\')')
        if Transaction().context.get('end_date'):
            # Check end_date
            time.strptime(str(Transaction().context['end_date']), '%Y-%m-%d')
            res += (' AND ' + obj + '.date <= date(\''
                + str(Transaction().context['end_date']) + '\')')
        return res

    @classmethod
    def validate(cls, lines):
        super(Line, cls).validate(lines)
        for line in lines:
            line.check_account()

    def check_account(self):
        if self.account.type == 'view':
            self.raise_user_error('line_on_view_account',
                (self.account.rec_name,))
        if not self.account.active:
            self.raise_user_error('line_on_inactive_account',
                (self.account.rec_name,))


class MoveLine(ModelSQL, ModelView):
    __name__ = 'account.move.line'
    analytic_lines = fields.One2Many('analytic_account.line', 'move_line',
            'Analytic Lines')


class OpenAccount(Wizard):
    'Open Account'
    __name__ = 'analytic_account.line.open_account'
    start_state = 'open_'
    open_ = StateAction('analytic_account.act_line_form')

    def do_open_(self, action):
        action['pyson_domain'] = [
            ('account', '=', Transaction().context['active_id']),
            ]
        if Transaction().context.get('start_date'):
            action['pyson_domain'].append(
                ('date', '>=', Transaction().context['start_date'])
                )
        if Transaction().context.get('end_date'):
            action['pyson_domain'].append(
                ('date', '<=', Transaction().context['end_date'])
                )
        action['pyson_domain'] = PYSONEncoder().encode(action['pyson_domain'])
        return action, {}

    def transition_open_(self):
        return 'end'
