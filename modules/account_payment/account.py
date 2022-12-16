# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null
from sql.aggregate import Sum
from sql.conditionals import Case, Coalesce
from sql.functions import Abs

from trytond.pool import Pool, PoolMeta
from trytond.model import ModelView, fields
from trytond.pyson import Eval, If, Bool
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.transaction import Transaction

from .payment import KINDS

__all__ = ['MoveLine', 'PayLine', 'PayLineStart', 'Configuration']


class MoveLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.move.line'
    payment_amount = fields.Function(fields.Numeric('Payment Amount',
            digits=(16,
                If(Bool(Eval('second_currency_digits')),
                    Eval('second_currency_digits', 2),
                    Eval('currency_digits', 2))),
            states={
                'invisible': ~Eval('payment_kind'),
                },
            depends=['payment_kind', 'second_currency_digits',
                'currency_digits']), 'get_payment_amount',
        searcher='search_payment_amount')
    payments = fields.One2Many('account.payment', 'line', 'Payments',
        readonly=True,
        states={
            'invisible': ~Eval('payment_kind'),
            },
        depends=['payment_kind'])
    payment_kind = fields.Function(fields.Selection([
                (None, ''),
                ] + KINDS, 'Payment Kind'), 'get_payment_kind',
        searcher='search_payment_kind')

    @classmethod
    def __setup__(cls):
        super(MoveLine, cls).__setup__()
        cls._buttons.update({
                'pay': {
                    'invisible': ~Eval('payment_kind').in_(dict(KINDS).keys()),
                    },
                })

    @classmethod
    def get_payment_amount(cls, lines, name):
        amounts = {}
        for line in lines:
            if line.account.kind not in ('payable', 'receivable'):
                amounts[line.id] = None
                continue
            if line.second_currency:
                amount = abs(line.amount_second_currency)
            else:
                amount = abs(line.credit - line.debit)

            for payment in line.payments:
                if payment.state != 'failed':
                    amount -= payment.amount

            amounts[line.id] = amount
        return amounts

    @classmethod
    def search_payment_amount(cls, name, clause):
        pool = Pool()
        Payment = pool.get('account.payment')
        Account = pool.get('account.account')
        _, operator, value = clause
        Operator = fields.SQL_OPERATORS[operator]
        table = cls.__table__()
        payment = Payment.__table__()
        account = Account.__table__()

        payment_amount = Sum(Coalesce(payment.amount, 0))
        main_amount = Abs(table.credit - table.debit) - payment_amount
        second_amount = Abs(table.amount_second_currency) - payment_amount
        amount = Case((table.second_currency == Null, main_amount),
            else_=second_amount)
        value = cls.payment_amount.sql_format(value)

        query = table.join(payment, type_='LEFT',
            condition=(table.id == payment.line) & (payment.state != 'failed')
            ).join(account, condition=table.account == account.id
                ).select(table.id,
                    where=account.kind.in_(['payable', 'receivable']),
                    group_by=(table.id, account.kind, table.second_currency),
                    having=Operator(amount, value)
                    )
        return [('id', 'in', query)]

    def get_payment_kind(self, name):
        return self.account.kind if self.account.kind in dict(KINDS) else None

    @classmethod
    def search_payment_kind(cls, name, clause):
        return [('account.kind',) + tuple(clause[1:])]

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('payments', None)
        return super(MoveLine, cls).copy(lines, default=default)

    @classmethod
    @ModelView.button_action('account_payment.act_pay_line')
    def pay(cls, lines):
        pass


class PayLineStart(ModelView):
    'Pay Line'
    __name__ = 'account.move.line.pay.start'
    journal = fields.Many2One('account.payment.journal', 'Journal',
        required=True, domain=[
            ('company', '=', Eval('context', {}).get('company', -1)),
            ])
    date = fields.Date('Date', required=True)

    @staticmethod
    def default_date():
        pool = Pool()
        Payment = pool.get('account.payment')
        return Payment.default_date()


class PayLine(Wizard):
    'Pay Line'
    __name__ = 'account.move.line.pay'
    start = StateView('account.move.line.pay.start',
        'account_payment.move_line_pay_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Pay', 'pay', 'tryton-ok', default=True),
            ])
    pay = StateAction('account_payment.act_payment_form')

    def get_payment(self, line):
        pool = Pool()
        Payment = pool.get('account.payment')

        if (line.debit > 0) or (line.credit < 0):
            kind = 'receivable'
        else:
            kind = 'payable'

        return Payment(
            company=line.move.company,
            journal=self.start.journal,
            party=line.party,
            kind=kind,
            date=self.start.date,
            amount=line.payment_amount,
            line=line,
            )

    def do_pay(self, action):
        pool = Pool()
        Line = pool.get('account.move.line')
        Payment = pool.get('account.payment')

        lines = Line.browse(Transaction().context['active_ids'])

        payments = []
        for line in lines:
            payments.append(self.get_payment(line))
        Payment.save(payments)
        return action, {
            'res_id': [p.id for p in payments],
            }


class Configuration:
    __metaclass__ = PoolMeta
    __name__ = 'account.configuration'
    payment_group_sequence = fields.Property(fields.Many2One('ir.sequence',
            'Payment Group Sequence', domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'account.payment.group'),
                ], required=True))
