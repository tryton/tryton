# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.i18n import gettext
from trytond.model import ModelSQL, fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.account.exceptions import AccountMissing
from trytond.modules.account_invoice.exceptions import PaymentTermComputeError
from trytond.modules.company.model import CompanyValueMixin


class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'

    cash_rounding = fields.MultiValue(fields.Boolean("Cash Rounding"))
    cash_rounding_credit_account = fields.MultiValue(fields.Many2One(
            'account.account', "Cash Rounding Credit Account",
            domain=[
                ('type', '!=', None),
                ('closed', '!=', True),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'required': Eval('cash_rounding', False),
                },
            depends=['cash_rounding']))
    cash_rounding_debit_account = fields.MultiValue(fields.Many2One(
            'account.account', "Cash Rounding Debit Account",
            domain=[
                ('type', '!=', None),
                ('closed', '!=', True),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'required': Eval('cash_rounding', False),
                },
            depends=['cash_rounding']))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {
                'cash_rounding',
                'cash_rounding_credit_account',
                'cash_rounding_debit_account',
                }:
            return pool.get('account.configuration.cash_rounding_account')
        return super().multivalue_model(field)


class ConfigurationCashRoundingAccount(ModelSQL, CompanyValueMixin):
    "Account Configuration Cash Rounding Account"
    __name__ = 'account.configuration.cash_rounding_account'

    cash_rounding = fields.Boolean("Cash Rounding")
    cash_rounding_credit_account = fields.Many2One(
        'account.account', "Cash Rounding Credit Account",
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    cash_rounding_debit_account = fields.Many2One(
        'account.account', "Cash Rounding Debit Account",
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    cash_rounding = fields.Boolean(
        "Cash Rounding",
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])

    @classmethod
    def default_cash_rounding(cls):
        pool = Pool()
        Config = pool.get('account.configuration')
        config = Config(1)
        if cls.default_type() == 'out':
            return config.cash_rounding

    @fields.depends(methods=['_on_change_lines_taxes'])
    def on_change_cash_rounding(self):
        self._on_change_lines_taxes()

    @fields.depends('cash_rounding', methods=['_cash_round_total_amount'])
    def _on_change_lines_taxes(self):
        super()._on_change_lines_taxes()
        if self.cash_rounding:
            self.total_amount = self._cash_round_total_amount(
                self.total_amount)

    @classmethod
    def get_amount(cls, invoices, names):
        amounts = super().get_amount(invoices, names)
        if 'total_amount' in names:
            total_amounts = amounts['total_amount']
            for invoice in invoices:
                if invoice.cash_rounding:
                    amount = total_amounts[invoice.id]
                    amount = invoice._cash_round_total_amount(amount)
                    total_amounts[invoice.id] = amount
        return amounts

    @fields.depends('currency', 'payment_term', 'company', 'invoice_date')
    def _cash_round_total_amount(self, amount):
        "Round total amount according to cash rounding"
        if self.currency:
            amounts = [amount]
            if self.payment_term and self.company:
                try:
                    term_lines = self.payment_term.compute(
                        amount, self.company.currency,
                        self.invoice_date)
                    amounts = [a for _, a in term_lines]
                except PaymentTermComputeError:
                    pass
            amount = sum(map(self.currency.cash_round, amounts))
        return amount

    def _get_move_line(self, date, amount):
        line = super()._get_move_line(date, amount)
        if self.cash_rounding:
            currency = self.company.currency
            line.debit = currency.cash_round(line.debit)
            line.credit = currency.cash_round(line.credit)

            currency = line.second_currency
            if currency:
                line.amount_second_currency = currency.cash_round(
                    self.amount_second_currency)
        return line

    def get_move(self):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        MoveLine = pool.get('account.move.line')
        move = super().get_move()
        if self.cash_rounding:
            config = Configuration(1)
            total = Decimal(0)
            total_currency = Decimal(0)
            for line in move.lines:
                total += line.debit - line.credit
                if line.amount_second_currency:
                    total_currency += line.amount_second_currency
            if total or total_currency:
                line = MoveLine()
                if total <= 0:
                    line.debit, line.credit = -total, 0
                    line.account = config.get_multivalue(
                        'cash_rounding_debit_account',
                        company=self.company.id)
                else:
                    line.debit, line.credit = 0, total
                    line.account = config.get_multivalue(
                        'cash_rounding_credit_account',
                        company=self.company.id)
                if not line.account:
                    raise AccountMissing(
                        gettext(
                            'account_cash_rounding'
                            '.msg_missing_cash_rounding_account'))
                if total_currency:
                    line.amount_second_currency = total_currency
            lines = list(move.lines)
            lines.append(line)
            move.lines = lines
        return move
