# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import hashlib
from collections import defaultdict
from itertools import groupby

from sql import Null, Literal

from trytond.model import ModelSQL, ModelView, Workflow, fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction


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

    @classmethod
    def __setup__(cls):
        super(Period, cls).__setup__()
        cls._error_messages.update({
                'period_close_line_payment': (
                    'There are payable/receivable lines '
                    'from the period "%(period)s" not linked '
                    'to an invoice.'),
                })

    def is_on_cash_basis(self, tax):
        if not tax:
            return False
        group = _tax_group(tax)
        return (group in self.tax_group_on_cash_basis
            or group in self.fiscalyear.tax_group_on_cash_basis)

    @classmethod
    @ModelView.button
    @Workflow.transition('close')
    def close(cls, periods):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        super(Period, cls).close(periods)
        for period in periods:
            if (period.tax_group_on_cash_basis
                    or period.fiscalyear.tax_group_on_cash_basis):
                move_lines = MoveLine.search([
                        ('move.period', '=', period.id),
                        ('reconciliation', '=', None),
                        ('invoice_payment', '=', None),
                        ('account.kind', 'in', ['receivable', 'payable']),
                        ])
                if move_lines:
                    warning_name = (
                        'period_close_line_payment.%s' % hashlib.md5(
                            str(move_lines).encode('utf-8')).hexdigest())
                    cls.raise_user_warning(
                        warning_name, 'period_close_line_payment', {
                            'period': period.rec_name,
                            })


class TaxGroupCash(ModelSQL):
    "Tax Group On Cash Basis"
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
        where = super(Tax, cls)._amount_where(tax_line, move_line, move)
        return ((where
                & (tax_line.on_cash_basis == False)
                | (tax_line.on_cash_basis == Null))
            | ((tax_line.period.in_(periods) if periods else Literal(False))
                & (tax_line.on_cash_basis == True)))

    @classmethod
    def _amount_domain(cls):
        context = Transaction().context
        periods = context.get('periods', [])
        domain = super(Tax, cls)._amount_domain()
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
            },
        depends=['company', 'on_cash_basis'])

    @classmethod
    def default_on_cash_basis(cls):
        return False

    @property
    def period_checked(self):
        period = super(TaxLine, self).period_checked
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
        lines = cls.browse(sorted(lines, key=cls.group_cash_basis_key))
        for key, lines in groupby(lines, key=cls.group_cash_basis_key):
            key = dict(key)
            if not key['on_cash_basis']:
                continue
            lines = list(lines)
            company = lines[0].company
            line_no_periods = [l for l in lines if not l.period]
            if line_no_periods:
                line_no_period, = line_no_periods
                to_save.append(line_no_period)
            else:
                line_no_period = None
            total = sum(l.amount for l in lines)
            amount = company.currency.round(total * ratio)
            if line_no_period and line_no_period.amount == amount:
                line_no_period.period = period
            else:
                line = cls(**key)
                if line_no_period:
                    line.amount = amount - total + line_no_period.amount
                    line_no_period.amount -= line.amount
                else:
                    line.amount = amount - total
                line.period = period
                if line.amount:
                    to_save.append(line)
        cls.save(to_save)


class Move(metaclass=PoolMeta):
    __name__ = 'account.move'

    @classmethod
    @ModelView.button
    def post(cls, moves):
        pool = Pool()
        TaxLine = pool.get('account.tax.line')
        super(Move, cls).post(moves)

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
        depends=['type'],
        help="The tax group reported on cash basis for this invoice.")

    @fields.depends('party', 'type')
    def on_change_party(self):
        super(Invoice, self).on_change_party()
        if self.type == 'in' and self.party:
            self.tax_group_on_cash_basis = (
                self.party.supplier_tax_group_on_cash_basis)
        else:
            self.tax_group_on_cash_basis = []

    def get_move(self):
        move = super(Invoice, self).get_move()
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
        elif self.state == 'cancel':
            ratio = 0
        else:
            payment_amount = sum(
                l.debit - l.credit for l in self.payment_lines)
            if amount:
                ratio = abs(payment_amount / amount)
            else:
                ratio = 0
        assert 0 <= ratio <= 1
        return ratio

    @classmethod
    def write(cls, *args):
        pool = Pool()
        TaxLine = pool.get('account.tax.line')
        Date = pool.get('ir.date')
        Period = pool.get('account.period')

        super(Invoice, cls).write(*args)

        invoices = []
        actions = iter(args)
        for records, values in zip(actions, actions):
            if ('payment_lines' in values
                    or values.get('state') in {'paid', 'cancel', 'posted'}):
                invoices.extend(records)
        invoices = cls.browse(sum(args[0:None:2], []))
        invoices = [i for i in invoices if i.move]

        # Call update_cash_basis grouped per period and ratio only because
        # group_cash_basis_key already group per move_line.
        to_update = defaultdict(list)
        date = Transaction().context.get('payment_date', Date.today())
        periods = {}
        for invoice in invoices:
            if invoice.company not in periods:
                periods[invoice.company] = Period.find(
                    invoice.company.id, date=date)
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
                    self.invoice.company.id, date=accounting_date)
                period = Period(period)
            return period.is_on_cash_basis(self.tax)


class InvoiceTaxGroupCash(ModelSQL):
    "Tax Group on Cash Basis per Invoice"
    __name__ = 'account.invoice.tax.group.cash'

    invoice = fields.Many2One(
        'account.invoice', "Invoice", ondelete='CASCADE',
        domain=[
            ('type', '=', 'in'),
            ])
    tax_group = fields.Many2One(
        'account.tax.group', "Tax Group", ondelete='CASCADE', required=True)
