# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from itertools import groupby

from sql import Literal, Null
from sql.operators import Equal

from trytond.i18n import gettext
from trytond.model import (
    Exclude, ModelSQL, ModelView, Workflow, dualmethod, fields)
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.tools import sortable_values
from trytond.transaction import Transaction

from .exceptions import ClosePeriodWarning


def _tax_group(tax):
    while tax.parent:
        tax = tax.parent
    return tax.group


class FiscalYear(metaclass=PoolMeta):
    __name__ = 'account.fiscalyear'

    tax_group_on_cash_basis = fields.Many2Many(
        'account.tax.group.cash', 'fiscalyear', 'tax_group',
        "Tax Group On Cash Basis",
        help="The tax group reported on cash basis for this fiscal year.")


class Period(metaclass=PoolMeta):
    __name__ = 'account.period'

    tax_group_on_cash_basis = fields.Many2Many(
        'account.tax.group.cash', 'period', 'tax_group',
        "Tax Group On Cash Basis",
        help="The tax group reported on cash basis for this period.")

    def is_on_cash_basis(self, tax):
        if not tax:
            return False
        group = _tax_group(tax)
        return (group in self.tax_group_on_cash_basis
            or group in self.fiscalyear.tax_group_on_cash_basis)

    @classmethod
    @ModelView.button
    @Workflow.transition('closed')
    def close(cls, periods):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Warning = pool.get('res.user.warning')
        super().close(periods)
        for period in periods:
            if (period.tax_group_on_cash_basis
                    or period.fiscalyear.tax_group_on_cash_basis):
                move_lines = MoveLine.search([
                        ('move.period', '=', period.id),
                        ('reconciliation', '=', None),
                        ('invoice_payment', '=', None),
                        ['OR', [
                                ('account.type.receivable', '=', True),
                                ('credit', '>', 0),
                                ], [
                                ('account.type.payable', '=', True),
                                ('debit', '<', 0),
                                ],
                            ],
                        ])
                if move_lines:
                    warning_name = Warning.format(
                        'period_close_line_payment', move_lines)
                    if Warning.check(warning_name):
                        raise ClosePeriodWarning(warning_name,
                            gettext('account_tax_cash'
                                '.msg_close_period_line_payment',
                                period=period.rec_name))


class TaxGroupCash(ModelSQL):
    __name__ = 'account.tax.group.cash'

    fiscalyear = fields.Many2One(
        'account.fiscalyear', "Fiscal Year", ondelete='CASCADE')
    period = fields.Many2One(
        'account.period', "Period", ondelete='CASCADE')
    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE')
    tax_group = fields.Many2One(
        'account.tax.group', "Tax Group", ondelete='CASCADE', required=True)


class Tax(metaclass=PoolMeta):
    __name__ = 'account.tax'

    @classmethod
    def _amount_where(cls, tax_line, move_line, move):
        context = Transaction().context
        periods = context.get('periods', [])
        where = super()._amount_where(tax_line, move_line, move)
        return ((where
                & (tax_line.on_cash_basis == Literal(False))
                | (tax_line.on_cash_basis == Null))
            | ((tax_line.period.in_(periods) if periods else Literal(False))
                & (tax_line.on_cash_basis == Literal(True))))

    @classmethod
    def _amount_domain(cls):
        context = Transaction().context
        periods = context.get('periods', [])
        domain = super()._amount_domain()
        return ['OR',
            [domain,
                ('on_cash_basis', '=', False),
                ],
            [('period', 'in', periods),
                ('on_cash_basis', '=', True),
                ]]


class TaxLine(metaclass=PoolMeta):
    __name__ = 'account.tax.line'

    on_cash_basis = fields.Boolean("On Cash Basis")
    period = fields.Many2One('account.period', "Period",
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        states={
            'invisible': ~Eval('on_cash_basis', False),
            })

    @classmethod
    def __setup__(cls):
        super().__setup__()

        t = cls.__table__()
        cls._sql_constraints = [
            ('tax_type_move_line_cash_basis_no_period',
                Exclude(
                    t,
                    (t.tax, Equal),
                    (t.type, Equal),
                    (t.move_line, Equal),
                    where=(t.on_cash_basis == Literal(True))
                    & (t.period == Null)),
                'account_tax_cash.'
                'msg_tax_type_move_line_cash_basis_no_period_unique'),
            ]

    @classmethod
    def default_on_cash_basis(cls):
        return False

    @property
    def period_checked(self):
        period = super().period_checked
        if self.on_cash_basis:
            period = self.period
        return period

    @classmethod
    def group_cash_basis_key(cls, line):
        return (
            ('tax', line.tax),
            ('type', line.type),
            ('move_line', line.move_line),
            ('on_cash_basis', line.on_cash_basis),
            )

    @classmethod
    def update_cash_basis(cls, lines, ratio, period):
        if not lines:
            return
        to_save = []
        lines = cls.browse(sorted(
                lines, key=sortable_values(cls.group_cash_basis_key)))
        for key, lines in groupby(lines, key=cls.group_cash_basis_key):
            key = dict(key)
            if not key['on_cash_basis']:
                continue
            lines = list(lines)
            company = lines[0].company
            line_no_periods = [l for l in lines if not l.period]
            if line_no_periods:
                line_no_period, = line_no_periods
            else:
                line_no_period = None
            total = sum(l.amount for l in lines)
            amount = total * ratio - sum(l.amount for l in lines if l.period)
            amount = company.currency.round(amount)
            if amount:
                if line_no_period and line_no_period.amount == amount:
                    line_no_period.period = period
                else:
                    line = cls(**key, amount=amount)
                    if line_no_period:
                        line_no_period.amount -= line.amount
                    line.period = period
                    if line.amount:
                        to_save.append(line)
                if line_no_period:
                    to_save.append(line_no_period)
        cls.save(to_save)


class Move(metaclass=PoolMeta):
    __name__ = 'account.move'

    @dualmethod
    @ModelView.button
    def post(cls, moves):
        pool = Pool()
        TaxLine = pool.get('account.tax.line')
        super().post(moves)

        tax_lines = []
        for move in moves:
            period = move.period
            for line in move.lines:
                for tax_line in line.tax_lines:
                    if (not tax_line.on_cash_basis
                            and period.is_on_cash_basis(tax_line.tax)):
                        tax_lines.append(tax_line)
        TaxLine.write(tax_lines, {
                'on_cash_basis': True,
                })


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    tax_group_on_cash_basis = fields.Many2Many(
        'account.invoice.tax.group.cash', 'invoice', 'tax_group',
        "Tax Group On Cash Basis",
        states={
            'invisible': Eval('type') != 'in',
            },
        help="The tax group reported on cash basis for this invoice.")

    @fields.depends('party', 'type', 'tax_group_on_cash_basis')
    def on_change_party(self):
        super().on_change_party()
        if self.type == 'in' and self.party:
            self.tax_group_on_cash_basis = (
                self.party.supplier_tax_group_on_cash_basis)
        else:
            self.tax_group_on_cash_basis = []

    def get_move(self):
        move = super().get_move()
        if self.tax_group_on_cash_basis:
            for line in move.lines:
                for tax_line in getattr(line, 'tax_lines', []):
                    tax = tax_line.tax
                    if tax and _tax_group(tax) in self.tax_group_on_cash_basis:
                        tax_line.on_cash_basis = True
        return move

    @property
    def cash_paid_ratio(self):
        amount = sum(l.debit - l.credit for l in self.lines_to_pay)
        if self.state == 'paid':
            ratio = 1
        elif self.state == 'cancelled':
            ratio = 0
        else:
            payment_amount = sum(
                l.debit - l.credit for l in self.payment_lines
                if not l.reconciliation)
            payment_amount -= sum(
                l.debit - l.credit for l in self.lines_to_pay
                if l.reconciliation)
            if amount:
                ratio = abs(payment_amount / amount)
            else:
                ratio = 0
        assert 0 <= ratio <= 1
        return ratio

    @classmethod
    def on_modification(cls, mode, invoices, field_names=None):
        super().on_modification(mode, invoices, field_names=field_names)
        if mode == 'write' and 'payment_lines' in field_names:
            cls._update_tax_cash_basis(invoices)

    @classmethod
    def process(cls, invoices):
        super().process(invoices)
        cls._update_tax_cash_basis(invoices)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, invoices):
        super().cancel(invoices)
        cls._update_tax_cash_basis(invoices)

    @classmethod
    def _update_tax_cash_basis(cls, invoices):
        pool = Pool()
        TaxLine = pool.get('account.tax.line')
        Date = pool.get('ir.date')
        Period = pool.get('account.period')

        # Call update_cash_basis grouped per period and ratio only because
        # group_cash_basis_key already group per move_line.
        to_update = defaultdict(list)
        periods = {}
        for invoice in invoices:
            if not invoice.move:
                continue
            if invoice.company not in periods:
                with Transaction().set_context(company=invoice.company.id):
                    date = Transaction().context.get(
                        'payment_date', Date.today())
                periods[invoice.company] = Period.find(
                    invoice.company, date=date)
            period = periods[invoice.company]
            ratio = invoice.cash_paid_ratio
            for line in invoice.move.lines:
                to_update[(period, ratio)].extend(line.tax_lines)
        for (period, ratio), tax_lines in to_update.items():
            TaxLine.update_cash_basis(tax_lines, ratio, period)


class InvoiceTax(metaclass=PoolMeta):
    __name__ = 'account.invoice.tax'

    @property
    def on_cash_basis(self):
        pool = Pool()
        Period = pool.get('account.period')
        if self.invoice and self.tax:
            if self.tax.group in self.invoice.tax_group_on_cash_basis:
                return True
            if self.invoice.move:
                period = self.invoice.move.period
            else:
                accounting_date = (
                    self.invoice.accounting_date or self.invoice.invoice_date)
                period = Period.find(
                    self.invoice.company, date=accounting_date)
            return period.is_on_cash_basis(self.tax)


class InvoiceTaxGroupCash(ModelSQL):
    __name__ = 'account.invoice.tax.group.cash'

    invoice = fields.Many2One(
        'account.invoice', "Invoice", ondelete='CASCADE',
        domain=[
            ('type', '=', 'in'),
            ])
    tax_group = fields.Many2One(
        'account.tax.group', "Tax Group", ondelete='CASCADE', required=True)
