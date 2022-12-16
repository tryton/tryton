# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from collections import defaultdict, namedtuple
from itertools import combinations

from sql import Null
from sql.aggregate import Sum
from sql.conditionals import Coalesce, Case
from sql.functions import Round

from trytond.i18n import gettext
from trytond.model import Workflow, ModelView, ModelSQL, fields, \
    sequence_ordered, Unique, DeactivableMixin, dualmethod
from trytond.model.exceptions import AccessError
from trytond.report import Report
from trytond.wizard import Wizard, StateView, StateTransition, StateAction, \
    Button
from trytond import backend
from trytond.pyson import If, Eval, Bool
from trytond.tools import reduce_ids, grouped_slice
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.rpc import RPC
from trytond.config import config

from trytond.modules.account.tax import TaxableMixin
from trytond.modules.product import price_digits

from .exceptions import (
    InvoiceTaxValidationError, InvoiceNumberError, InvoiceValidationError,
    InvoiceLineValidationError, PayInvoiceError)

if config.getboolean('account_invoice', 'filestore', default=False):
    file_id = 'invoice_report_cache_id'
    store_prefix = config.get('account_invoice', 'store_prefix', default=None)
else:
    file_id = None
    store_prefix = None


class Invoice(Workflow, ModelSQL, ModelView, TaxableMixin):
    'Invoice'
    __name__ = 'account.invoice'
    _order_name = 'number'

    _states = {
        'readonly': Eval('state') != 'draft',
    }
    _depends = ['state']

    company = fields.Many2One('company.company', 'Company', required=True,
        states=_states, select=True, domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        depends=_depends)
    company_party = fields.Function(
        fields.Many2One('party.party', "Company Party"),
        'on_change_with_company_party')
    tax_identifier = fields.Many2One(
        'party.identifier', "Tax Identifier",
        states=_states, depends=_depends)
    type = fields.Selection([
            ('out', "Customer"),
            ('in', "Supplier"),
            ], "Type", select=True, required=True,
        states={
            'readonly': ((Eval('state') != 'draft')
                | Eval('context', {}).get('type')
                | (Eval('lines', [0]) & Eval('type'))),
            }, depends=['state'])
    type_name = fields.Function(fields.Char('Type'), 'get_type_name')
    number = fields.Char('Number', size=None, readonly=True, select=True)
    reference = fields.Char('Reference', size=None, states=_states,
        depends=_depends)
    description = fields.Char('Description', size=None, states=_states,
        depends=_depends)
    state = fields.Selection([
            ('draft', "Draft"),
            ('validated', "Validated"),
            ('posted', "Posted"),
            ('paid', "Paid"),
            ('cancelled', "Cancelled"),
            ], "State", readonly=True)
    invoice_date = fields.Date('Invoice Date',
        states={
            'readonly': Eval('state').in_(['posted', 'paid', 'cancelled']),
            'required': Eval('state').in_(
                If(Eval('type') == 'in',
                    ['validated', 'posted', 'paid'],
                    ['posted', 'paid'])),
            },
        depends=['state'])
    accounting_date = fields.Date('Accounting Date', states=_states,
        depends=_depends)
    sequence = fields.Many2One('ir.sequence.strict', "Sequence", readonly=True)
    party = fields.Many2One('party.party', 'Party',
        required=True, states=_states, depends=_depends)
    party_tax_identifier = fields.Many2One(
        'party.identifier', "Party Tax Identifier",
        states=_states,
        domain=[
            ('party', '=', Eval('party', -1)),
            ],
        depends=_depends + ['party'])
    party_lang = fields.Function(fields.Char('Party Language'),
        'on_change_with_party_lang')
    invoice_address = fields.Many2One('party.address', 'Invoice Address',
        required=True, states=_states, depends=_depends + ['party'],
        domain=[('party', '=', Eval('party'))])
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states={
            'readonly': (
                _states['readonly']
                | (Eval('lines', [0]) & Eval('currency'))),
            },
        depends=_depends)
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    currency_date = fields.Function(fields.Date('Currency Date'),
        'on_change_with_currency_date')
    journal = fields.Many2One('account.journal', 'Journal', required=True,
        states=_states, depends=_depends)
    move = fields.Many2One('account.move', 'Move', readonly=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    cancel_move = fields.Many2One('account.move', 'Cancel Move', readonly=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        states={
            'invisible': ~Eval('cancel_move'),
            },
        depends=['company'])
    account = fields.Many2One('account.account', 'Account', required=True,
        states=_states, depends=_depends + [
            'type', 'company', 'accounting_date', 'invoice_date'],
        domain=[
            ('closed', '!=', True),
            ('company', '=', Eval('company', -1)),
            If(Eval('type') == 'out',
                ('type.receivable', '=', True),
                ('type.payable', '=', True)),
            ],
        context={
            'date': If(Eval('accounting_date'),
                Eval('accounting_date'),
                Eval('invoice_date')),
            })
    payment_term = fields.Many2One('account.invoice.payment_term',
        'Payment Term', states=_states, depends=_depends)
    lines = fields.One2Many('account.invoice.line', 'invoice', 'Lines',
        domain=[
            ('company', '=', Eval('company', -1)),
            ('currency', '=', Eval('currency', -1)),
            ['OR',
                ('invoice_type', '=', Eval('type')),
                ('invoice_type', '=', None),
                ],
            ['OR',
                ('party', '=', Eval('party', -1)),
                ('party', '=', None),
                ],
            ],
        states={
            'readonly': (
                (Eval('state') != 'draft')
                | ~Eval('company')
                | ~Eval('currency')),
            },
        depends=['state', 'company', 'currency', 'type', 'party'])
    taxes = fields.One2Many('account.invoice.tax', 'invoice', 'Tax Lines',
        states=_states, depends=_depends)
    comment = fields.Text('Comment', states=_states, depends=_depends)
    origins = fields.Function(fields.Char('Origins'), 'get_origins')
    untaxed_amount = fields.Function(fields.Numeric('Untaxed',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_amount', searcher='search_untaxed_amount')
    tax_amount = fields.Function(fields.Numeric('Tax', digits=(16,
                Eval('currency_digits', 2)), depends=['currency_digits']),
        'get_amount', searcher='search_tax_amount')
    total_amount = fields.Function(fields.Numeric('Total', digits=(16,
                Eval('currency_digits', 2)), depends=['currency_digits']),
        'get_amount', searcher='search_total_amount')
    reconciled = fields.Function(fields.Date('Reconciled',
            states={
                'invisible': ~Eval('reconciled'),
                }),
            'get_reconciled')
    lines_to_pay = fields.Function(fields.Many2Many(
            'account.move.line', None, None, 'Lines to Pay'),
        'get_lines_to_pay')
    payment_lines = fields.Many2Many('account.invoice-account.move.line',
        'invoice', 'line', string='Payment Lines',
        domain=[
            ('account', '=', Eval('account', -1)),
            ('party', 'in', [None, Eval('party', -1)]),
            ['OR',
                ('invoice_payment', '=', None),
                ('invoice_payment', '=', Eval('id', -1)),
                ],
            If(Eval('type') == 'out',
                If(Eval('total_amount', 0) >= 0,
                    ('debit', '=', 0),
                    ('credit', '=', 0)),
                If(Eval('total_amount', 0) >= 0,
                    ('credit', '=', 0),
                    ('debit', '=', 0))),
            ],
        states={
            'invisible': Eval('state') == 'paid',
            'readonly': Eval('state') != 'posted',
            },
        depends=['state', 'account', 'party', 'id', 'type', 'total_amount'])
    reconciliation_lines = fields.Function(fields.Many2Many(
            'account.move.line', None, None, "Payment Lines",
            states={
                'invisible': Eval('state') != 'paid',
                }),
        'get_reconciliation_lines')
    amount_to_pay_today = fields.Function(fields.Numeric('Amount to Pay Today',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_amount_to_pay')
    amount_to_pay = fields.Function(fields.Numeric('Amount to Pay',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_amount_to_pay')
    invoice_report_cache = fields.Binary('Invoice Report', readonly=True,
        file_id=file_id, store_prefix=store_prefix)
    invoice_report_cache_id = fields.Char('Invoice Report ID', readonly=True)
    invoice_report_format = fields.Char('Invoice Report Format', readonly=True)
    allow_cancel = fields.Function(
        fields.Boolean("Allow Cancel Invoice"), 'get_allow_cancel')

    del _states, _depends

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls._check_modify_exclude = ['state', 'payment_lines', 'cancel_move',
                'invoice_report_cache', 'invoice_report_format']
        cls._order = [
            ('number', 'DESC'),
            ('id', 'DESC'),
            ]
        cls.journal.domain = [
            If(Eval('type') == 'out',
                ('type', 'in', cls._journal_types('out')),
                ('type', 'in', cls._journal_types('in'))),
            ]
        cls.journal.depends += ['type']
        cls.tax_identifier.domain = [
            ('party', '=', Eval('company_party', -1)),
            ('type', 'in', cls.tax_identifier_types()),
            ]
        cls.tax_identifier.depends += ['company_party']
        cls._transitions |= set((
                ('draft', 'validated'),
                ('validated', 'posted'),
                ('draft', 'posted'),
                ('posted', 'paid'),
                ('validated', 'draft'),
                ('paid', 'posted'),
                ('draft', 'cancelled'),
                ('validated', 'cancelled'),
                ('posted', 'cancelled'),
                ('cancelled', 'draft'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': ~Eval('allow_cancel', False),
                    'depends': ['allow_cancel'],
                    },
                'draft': {
                    'invisible': (
                        ~Eval('state').in_(['cancelled', 'validated'])
                        | ((Eval('state') == 'cancelled')
                            & Eval('cancel_move', -1))),
                    'icon': If(Eval('state') == 'cancelled', 'tryton-undo',
                        'tryton-back'),
                    'depends': ['state'],
                    },
                'validate_invoice': {
                    'pre_validate':
                        ['OR',
                            ('invoice_date', '!=', None),
                            ('type', '!=', 'in'),
                        ],
                    'invisible': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                'post': {
                    'pre_validate':
                        ['OR',
                            ('invoice_date', '!=', None),
                            ('type', '!=', 'in'),
                        ],
                    'invisible': ~Eval('state').in_(['draft', 'validated']),
                    'depends': ['state'],
                    },
                'pay': {
                    'invisible': Eval('state') != 'posted',
                    'depends': ['state'],
                    },
                })
        cls.__rpc__.update({
                'post': RPC(
                    readonly=False, instantiate=0, fresh_session=True),
                })

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Line = pool.get('account.invoice.line')
        Tax = pool.get('account.invoice.tax')
        sql_table = cls.__table__()
        line = Line.__table__()
        tax = Tax.__table__()

        super(Invoice, cls).__register__(module_name)
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        table = cls.__table_handler__(module_name)

        # Migration from 3.8: remove invoice/credit note type
        cursor.execute(*sql_table.select(sql_table.id,
                where=sql_table.type.like('%_invoice')
                | sql_table.type.like('%_credit_note'),
                limit=1))
        if cursor.fetchone():
            for type_ in ['out', 'in']:
                cursor.execute(*sql_table.update(
                        columns=[sql_table.type],
                        values=[type_],
                        where=sql_table.type == '%s_invoice' % type_))
                cursor.execute(*line.update(
                        columns=[line.invoice_type],
                        values=[type_],
                        where=line.invoice_type == '%s_invoice' % type_))

                cursor.execute(*line.update(
                        columns=[line.quantity, line.invoice_type],
                        values=[-line.quantity, type_],
                        where=(line.invoice_type == '%s_credit_note' % type_)
                        & (line.invoice == Null)
                        ))
                # Don't use UPDATE FROM because SQLite nor MySQL support it
                cursor.execute(*line.update(
                        columns=[line.quantity, line.invoice_type],
                        values=[-line.quantity, type_],
                        where=line.invoice.in_(sql_table.select(sql_table.id,
                                where=(
                                    sql_table.type == '%s_credit_note' % type_)
                                ))))
                cursor.execute(*tax.update(
                        columns=[tax.base, tax.amount, tax.base_sign],
                        values=[-tax.base, -tax.amount, -tax.base_sign],
                        where=tax.invoice.in_(sql_table.select(sql_table.id,
                                where=(
                                    sql_table.type == '%s_credit_note' % type_)
                                ))))
                cursor.execute(*sql_table.update(
                        columns=[sql_table.type],
                        values=[type_],
                        where=sql_table.type == '%s_credit_note' % type_))

        # Migration from 4.0: Drop not null on payment_term
        table.not_null_action('payment_term', 'remove')

        # Add index on create_date
        table.index_action('create_date', action='add')

        # Migration from 5.6: rename state cancel to cancelled
        cursor.execute(*sql_table.update(
                [sql_table.state], ['cancelled'],
                where=sql_table.state == 'cancel'))

    @staticmethod
    def default_type():
        return Transaction().context.get('type', 'out')

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = Company(Transaction().context['company'])
            return company.currency.id

    @staticmethod
    def default_currency_digits():
        Company = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = Company(Transaction().context['company'])
            return company.currency.digits
        return 2

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @fields.depends('company')
    def on_change_with_company_party(self, name=None):
        if self.company:
            return self.company.party.id

    @classmethod
    def default_payment_term(cls):
        PaymentTerm = Pool().get('account.invoice.payment_term')
        payment_terms = PaymentTerm.search(cls.payment_term.domain)
        if len(payment_terms) == 1:
            return payment_terms[0].id

    @fields.depends('party', 'type')
    def on_change_with_payment_term(self):
        payment_term = None
        if self.party:
            if self.type == 'out':
                payment_term = self.party.customer_payment_term
            elif self.type == 'in':
                payment_term = self.party.supplier_payment_term
        return payment_term.id if payment_term else None

    @fields.depends('party', 'type', 'accounting_date', 'invoice_date')
    def on_change_with_account(self):
        account = None
        if self.party:
            with Transaction().set_context(
                    date=self.accounting_date or self.invoice_date):
                if self.type == 'out':
                    account = self.party.account_receivable_used
                elif self.type == 'in':
                    account = self.party.account_payable_used
        return account.id if account else None

    @fields.depends('type')
    def on_change_type(self):
        Journal = Pool().get('account.journal')
        journal_type = {
            'out': 'revenue',
            'in': 'expense',
            }.get(self.type or 'out', 'revenue')
        journals = Journal.search([
                ('type', '=', journal_type),
                ], limit=1)
        if journals:
            self.journal, = journals

    @classmethod
    def _journal_types(cls, invoice_type):
        if invoice_type == 'out':
            return ['revenue']
        else:
            return ['expense']

    @fields.depends('party')
    def on_change_party(self):
        self.invoice_address = None
        if self.party:
            self.invoice_address = self.party.address_get(type='invoice')
            self.party_tax_identifier = self.party.tax_identifier

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2

    @fields.depends('invoice_date')
    def on_change_with_currency_date(self, name=None):
        Date = Pool().get('ir.date')
        return self.invoice_date or Date.today()

    @fields.depends('party')
    def on_change_with_party_lang(self, name=None):
        Config = Pool().get('ir.configuration')
        if self.party:
            if self.party.lang:
                return self.party.lang.code
        return Config.get_language()

    @classmethod
    def get_type_name(cls, invoices, name):
        type_names = {}
        type2name = {}
        for type, name in cls.fields_get(fields_names=['type']
                )['type']['selection']:
            type2name[type] = name
        for invoice in invoices:
            type_names[invoice.id] = type2name[invoice.type]
        return type_names

    @fields.depends(methods=['_on_change_lines_taxes'])
    def on_change_lines(self):
        self._on_change_lines_taxes()

    @fields.depends(methods=['_on_change_lines_taxes'])
    def on_change_taxes(self):
        self._on_change_lines_taxes()

    @fields.depends('lines', 'taxes', 'currency',
        'accounting_date', 'invoice_date',  # From tax_date
        methods=['_get_taxes'])
    def _on_change_lines_taxes(self):
        pool = Pool()
        InvoiceTax = pool.get('account.invoice.tax')

        self.untaxed_amount = Decimal('0.0')
        self.tax_amount = Decimal('0.0')
        self.total_amount = Decimal('0.0')
        computed_taxes = {}

        if self.lines:
            for line in self.lines:
                self.untaxed_amount += getattr(line, 'amount', None) or 0
            computed_taxes = self._get_taxes()

        def is_zero(amount):
            if self.currency:
                return self.currency.is_zero(amount)
            else:
                return amount == Decimal('0.0')

        tax_keys = []
        taxes = list(self.taxes or [])
        for tax in (self.taxes or []):
            if tax.manual:
                self.tax_amount += tax.amount or Decimal('0.0')
                continue
            key = tax._key
            if (key not in computed_taxes) or (key in tax_keys):
                taxes.remove(tax)
                continue
            tax_keys.append(key)
            if not is_zero(computed_taxes[key]['base']
                    - (tax.base or Decimal('0.0'))):
                self.tax_amount += computed_taxes[key]['amount']
                tax.amount = computed_taxes[key]['amount']
                tax.base = computed_taxes[key]['base']
            else:
                self.tax_amount += tax.amount or Decimal('0.0')
        for key in computed_taxes:
            if key not in tax_keys:
                self.tax_amount += computed_taxes[key]['amount']
                value = InvoiceTax.default_get(
                    list(InvoiceTax._fields.keys()), with_rec_name=False)
                value.update(computed_taxes[key])
                invoice_tax = InvoiceTax(**value)
                if invoice_tax.tax:
                    invoice_tax.sequence = invoice_tax.tax.sequence
                taxes.append(invoice_tax)
        self.taxes = taxes
        if self.currency:
            self.untaxed_amount = self.currency.round(self.untaxed_amount)
            self.tax_amount = self.currency.round(self.tax_amount)
        self.total_amount = self.untaxed_amount + self.tax_amount
        if self.currency:
            self.total_amount = self.currency.round(self.total_amount)

    @classmethod
    def get_amount(cls, invoices, names):
        pool = Pool()
        InvoiceTax = pool.get('account.invoice.tax')
        Move = pool.get('account.move')
        MoveLine = pool.get('account.move.line')
        cursor = Transaction().connection.cursor()

        untaxed_amount = dict((i.id, Decimal(0)) for i in invoices)
        tax_amount = dict((i.id, Decimal(0)) for i in invoices)
        total_amount = dict((i.id, Decimal(0)) for i in invoices)

        type_name = cls.tax_amount._field.sql_type().base
        tax = InvoiceTax.__table__()
        to_round = False
        for sub_ids in grouped_slice(invoices):
            red_sql = reduce_ids(tax.invoice, sub_ids)
            cursor.execute(*tax.select(tax.invoice,
                    Coalesce(Sum(tax.amount), 0).as_(type_name),
                    where=red_sql,
                    group_by=tax.invoice))
            for invoice_id, sum_ in cursor.fetchall():
                # SQLite uses float for SUM
                if not isinstance(sum_, Decimal):
                    sum_ = Decimal(str(sum_))
                    to_round = True
                tax_amount[invoice_id] = sum_
        # Float amount must be rounded to get the right precision
        if to_round:
            for invoice in invoices:
                tax_amount[invoice.id] = invoice.currency.round(
                    tax_amount[invoice.id])

        invoices_move = set()
        invoices_no_move = set()
        for invoice in invoices:
            if invoice.move:
                invoices_move.add(invoice.id)
            else:
                invoices_no_move.add(invoice.id)
        invoices_move = cls.browse(invoices_move)
        invoices_no_move = cls.browse(invoices_no_move)

        type_name = cls.total_amount._field.sql_type().base
        invoice = cls.__table__()
        move = Move.__table__()
        line = MoveLine.__table__()
        to_round = False
        for sub_ids in grouped_slice(invoices_move):
            red_sql = reduce_ids(invoice.id, sub_ids)
            cursor.execute(*invoice.join(move,
                    condition=invoice.move == move.id
                    ).join(line, condition=move.id == line.move
                    ).select(invoice.id,
                    Coalesce(Sum(
                            Case((
                                    line.second_currency == invoice.currency,
                                    line.amount_second_currency),
                                else_=line.debit - line.credit)),
                        0).cast(type_name),
                    where=(invoice.account == line.account) & red_sql,
                    group_by=invoice.id))
            for invoice_id, sum_ in cursor.fetchall():
                # SQLite uses float for SUM
                if not isinstance(sum_, Decimal):
                    sum_ = Decimal(str(sum_))
                    to_round = True
                total_amount[invoice_id] = sum_

        for invoice in invoices_move:
            if invoice.type == 'in':
                total_amount[invoice.id] *= -1
            # Float amount must be rounded to get the right precision
            if to_round:
                total_amount[invoice.id] = invoice.currency.round(
                    total_amount[invoice.id])
            untaxed_amount[invoice.id] = (
                total_amount[invoice.id] - tax_amount[invoice.id])

        for invoice in invoices_no_move:
            untaxed_amount[invoice.id] = sum(
                (line.amount for line in invoice.lines
                    if line.type == 'line'), Decimal(0))
            total_amount[invoice.id] = (
                untaxed_amount[invoice.id] + tax_amount[invoice.id])

        result = {
            'untaxed_amount': untaxed_amount,
            'tax_amount': tax_amount,
            'total_amount': total_amount,
            }
        for key in list(result.keys()):
            if key not in names:
                del result[key]
        return result

    def get_reconciled(self, name):
        def get_reconciliation(line):
            if line.reconciliation and line.reconciliation.delegate_to:
                return get_reconciliation(line.reconciliation.delegate_to)
            else:
                return line.reconciliation
        reconciliations = list(map(get_reconciliation, self.lines_to_pay))
        if not reconciliations:
            return None
        elif not all(reconciliations):
            return None
        else:
            return max(r.date for r in reconciliations)

    @classmethod
    def get_lines_to_pay(cls, invoices, name):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        line = MoveLine.__table__()
        invoice = cls.__table__()
        cursor = Transaction().connection.cursor()

        lines = defaultdict(list)
        for sub_ids in grouped_slice(invoices):
            red_sql = reduce_ids(invoice.id, sub_ids)
            cursor.execute(*invoice.join(line,
                condition=((invoice.move == line.move)
                    & (invoice.account == line.account))).select(
                        invoice.id, line.id,
                        where=red_sql,
                        order_by=(invoice.id, line.maturity_date.nulls_last)))
            for invoice_id, line_id in cursor.fetchall():
                lines[invoice_id].append(line_id)
        return lines

    def get_reconciliation_lines(self, name):
        if self.state != 'paid':
            return
        lines = set()
        for line in self.move.lines:
            if line.account == self.account and line.reconciliation:
                for line in line.reconciliation.lines:
                    if line not in self.move.lines:
                        lines.add(line)
        return [l.id for l in sorted(lines, key=lambda l: l.date)]

    @classmethod
    def get_amount_to_pay(cls, invoices, name):
        pool = Pool()
        Currency = pool.get('currency.currency')
        Date = pool.get('ir.date')

        today = Date.today()
        res = dict((x.id, Decimal(0)) for x in invoices)
        for invoice in invoices:
            if invoice.state != 'posted':
                continue
            amount = Decimal(0)
            amount_currency = Decimal(0)
            for line in invoice.lines_to_pay:
                if line.reconciliation:
                    continue
                if (name == 'amount_to_pay_today'
                        and (not line.maturity_date
                            or line.maturity_date > today)):
                    continue
                if (line.second_currency
                        and line.second_currency == invoice.currency):
                    amount_currency += line.amount_second_currency
                else:
                    amount += line.debit - line.credit
            for line in invoice.payment_lines:
                if line.reconciliation:
                    continue
                if (line.second_currency
                        and line.second_currency == invoice.currency):
                    amount_currency += line.amount_second_currency
                else:
                    amount += line.debit - line.credit
            if amount != Decimal(0):
                with Transaction().set_context(date=invoice.currency_date):
                    amount_currency += Currency.compute(
                        invoice.company.currency, amount, invoice.currency)
            if invoice.type == 'in' and amount_currency:
                amount_currency *= -1
            res[invoice.id] = amount_currency
        return res

    @classmethod
    def search_total_amount(cls, name, clause):
        pool = Pool()
        Rule = pool.get('ir.rule')
        Line = pool.get('account.invoice.line')
        Tax = pool.get('account.invoice.tax')
        Invoice = pool.get('account.invoice')
        Currency = pool.get('currency.currency')
        type_name = cls.total_amount._field.sql_type().base
        line = Line.__table__()
        invoice = Invoice.__table__()
        currency = Currency.__table__()
        tax = Tax.__table__()

        _, operator, value = clause
        invoice_query = Rule.query_get('account.invoice')
        Operator = fields.SQL_OPERATORS[operator]
        # SQLite uses float for sum
        if backend.name == 'sqlite':
            value = float(value)

        union = (line.join(invoice, condition=(invoice.id == line.invoice)
                ).join(currency, condition=(currency.id == invoice.currency)
                ).select(line.invoice.as_('invoice'),
                Coalesce(Sum(Round((line.quantity * line.unit_price).cast(
                                type_name),
                                currency.digits)), 0).as_('total_amount'),
                where=line.invoice.in_(invoice_query),
                group_by=line.invoice)
            | tax.select(tax.invoice.as_('invoice'),
                Coalesce(Sum(tax.amount), 0).as_('total_amount'),
                where=tax.invoice.in_(invoice_query),
                group_by=tax.invoice))
        query = union.select(union.invoice, group_by=union.invoice,
            having=Operator(Sum(union.total_amount).cast(type_name),
                value))
        return [('id', 'in', query)]

    @classmethod
    def search_untaxed_amount(cls, name, clause):
        pool = Pool()
        Rule = pool.get('ir.rule')
        Line = pool.get('account.invoice.line')
        Invoice = pool.get('account.invoice')
        Currency = pool.get('currency.currency')
        type_name = cls.untaxed_amount._field.sql_type().base
        line = Line.__table__()
        invoice = Invoice.__table__()
        currency = Currency.__table__()

        _, operator, value = clause
        invoice_query = Rule.query_get('account.invoice')
        Operator = fields.SQL_OPERATORS[operator]
        # SQLite uses float for sum
        if backend.name == 'sqlite':
            value = float(value)

        query = line.join(invoice,
            condition=(invoice.id == line.invoice)
            ).join(currency,
                condition=(currency.id == invoice.currency)
                ).select(line.invoice,
                    where=line.invoice.in_(invoice_query),
                    group_by=line.invoice,
                    having=Operator(Coalesce(Sum(
                                Round((line.quantity * line.unit_price).cast(
                                        type_name),
                                    currency.digits)), 0).cast(type_name),
                        value))
        return [('id', 'in', query)]

    @classmethod
    def search_tax_amount(cls, name, clause):
        pool = Pool()
        Rule = pool.get('ir.rule')
        Tax = pool.get('account.invoice.tax')
        type_name = cls.tax_amount._field.sql_type().base
        tax = Tax.__table__()

        _, operator, value = clause
        invoice_query = Rule.query_get('account.invoice')
        Operator = fields.SQL_OPERATORS[operator]
        # SQLite uses float for sum
        if backend.name == 'sqlite':
            value = float(value)

        query = tax.select(tax.invoice,
            where=tax.invoice.in_(invoice_query),
            group_by=tax.invoice,
            having=Operator(Coalesce(Sum(tax.amount), 0).cast(type_name),
                value))
        return [('id', 'in', query)]

    def get_allow_cancel(self, name):
        if self.state in {'draft', 'validated'}:
            return True
        if self.state == 'posted':
            return self.type == 'in' or self.company.cancel_invoice_out
        return False

    @property
    def taxable_lines(self):
        taxable_lines = []
        for line in self.lines:
            if getattr(line, 'type', None) == 'line':
                taxable_lines.extend(line.taxable_lines)
        return taxable_lines

    @property
    def tax_date(self):
        return self.accounting_date or self.invoice_date

    @fields.depends('party')
    def _get_tax_context(self):
        context = {}
        if self.party and self.party.lang:
            context['language'] = self.party.lang.code
        return context

    def _compute_taxes(self):
        taxes = self._get_taxes()
        for tax in taxes.values():
            tax['invoice'] = self.id
        return taxes

    @dualmethod
    def update_taxes(cls, invoices, exception=False):
        Tax = Pool().get('account.invoice.tax')
        to_create = []
        to_delete = []
        to_write = []
        for invoice in invoices:
            if invoice.state in ('posted', 'paid', 'cancelled'):
                continue
            computed_taxes = invoice._compute_taxes()
            if not invoice.taxes:
                to_create.extend(computed_taxes.values())
            else:
                tax_keys = []
                for tax in invoice.taxes:
                    if tax.manual:
                        continue
                    key = tax._key
                    if (key not in computed_taxes) or (key in tax_keys):
                        to_delete.append(tax)
                        continue
                    tax_keys.append(key)
                    if not invoice.currency.is_zero(
                            computed_taxes[key]['base'] - tax.base):
                        to_write.extend(([tax], computed_taxes[key]))
                for key in computed_taxes:
                    if key not in tax_keys:
                        to_create.append(computed_taxes[key])
            if exception and (to_create or to_delete or to_write):
                raise InvoiceTaxValidationError(
                    gettext('account_invoice.msg_invoice_tax_invalid',
                        invoice=invoice.rec_name))
        if to_create:
            Tax.create(to_create)
        if to_delete:
            Tax.delete(to_delete)
        if to_write:
            Tax.write(*to_write)

    def _get_move_line(self, date, amount):
        '''
        Return move line
        '''
        pool = Pool()
        Currency = pool.get('currency.currency')
        MoveLine = pool.get('account.move.line')
        line = MoveLine()
        if self.currency != self.company.currency:
            with Transaction().set_context(date=self.currency_date):
                line.amount_second_currency = Currency.compute(
                    self.company.currency, amount, self.currency)
            line.second_currency = self.currency
        else:
            line.amount_second_currency = None
            line.second_currency = None
        if amount <= 0:
            line.debit, line.credit = -amount, 0
        else:
            line.debit, line.credit = 0, amount
        if line.amount_second_currency:
            line.amount_second_currency = (
                line.amount_second_currency.copy_sign(
                    line.debit - line.credit))
        line.account = self.account
        if self.account.party_required:
            line.party = self.party
        line.maturity_date = date
        line.description = self.description
        return line

    def get_move(self):
        '''
        Compute account move for the invoice and return the created move
        '''
        pool = Pool()
        Move = pool.get('account.move')
        Period = pool.get('account.period')
        Date = pool.get('ir.date')

        if self.move:
            return self.move
        self.update_taxes(exception=True)
        move_lines = []
        for line in self.lines:
            move_lines += line.get_move_lines()
        for tax in self.taxes:
            move_lines += tax.get_move_lines()

        total = Decimal('0.0')
        total_currency = Decimal('0.0')
        for line in move_lines:
            total += line.debit - line.credit
            if line.amount_second_currency:
                total_currency += line.amount_second_currency

        term_lines = [(Date.today(), total)]
        if self.payment_term:
            term_lines = self.payment_term.compute(
                total, self.company.currency, self.invoice_date)
        remainder_total_currency = total_currency
        for date, amount in term_lines:
            line = self._get_move_line(date, amount)
            if line.amount_second_currency:
                remainder_total_currency += line.amount_second_currency
            move_lines.append(line)
        if not self.currency.is_zero(remainder_total_currency):
            move_lines[-1].amount_second_currency -= \
                remainder_total_currency

        accounting_date = self.accounting_date or self.invoice_date
        period_id = Period.find(self.company.id, date=accounting_date)

        move = Move()
        move.journal = self.journal
        move.period = period_id
        move.date = accounting_date
        move.origin = self
        move.company = self.company
        move.lines = move_lines
        return move

    @classmethod
    def set_number(cls, invoices):
        '''
        Set number to the invoice
        '''
        pool = Pool()
        Date = pool.get('ir.date')
        Lang = pool.get('ir.lang')
        today = Date.today()

        def accounting_date(invoice):
            return invoice.accounting_date or invoice.invoice_date or today

        invoices = sorted(invoices, key=accounting_date)
        sequences = set()

        for invoice in invoices:
            # Posted and paid invoices are tested by check_modify so we can
            # not modify tax_identifier nor number
            if invoice.state in {'posted', 'paid'}:
                continue
            if not invoice.tax_identifier:
                invoice.tax_identifier = invoice.get_tax_identifier()
            # Generated invoice may not fill the party tax identifier
            if not invoice.party_tax_identifier:
                invoice.party_tax_identifier = invoice.party.tax_identifier

            if invoice.number:
                continue

            if not invoice.invoice_date and invoice.type == 'out':
                invoice.invoice_date = today
            invoice.number, invoice.sequence = invoice.get_next_number()
            if invoice.type == 'out' and invoice.sequence not in sequences:
                date = accounting_date(invoice)
                # Do not need to lock the table
                # because sequence.get_id is sequential
                after_invoices = cls.search([
                            ('sequence', '=', invoice.sequence.id),
                            ['OR',
                                ('accounting_date', '>', date),
                                [
                                    ('accounting_date', '=', None),
                                    ('invoice_date', '>', date),
                                    ],
                                ],
                            ], limit=1)
                if after_invoices:
                    after_invoice, = after_invoices
                    raise InvoiceNumberError(
                        gettext('account_invoice.msg_invoice_number_after',
                            invoice=invoice.rec_name,
                            sequence=invoice.sequence.rec_name,
                            date=Lang.get().strftime(date),
                            after_invoice=after_invoice.rec_name))
                sequences.add(invoice.sequence)
        cls.save(invoices)

    def get_next_number(self, pattern=None):
        "Return invoice number and sequence used"
        pool = Pool()
        Sequence = pool.get('ir.sequence.strict')
        Period = pool.get('account.period')

        if pattern is None:
            pattern = {}
        else:
            pattern = pattern.copy()

        accounting_date = self.accounting_date or self.invoice_date
        period_id = Period.find(
            self.company.id, date=accounting_date,
            test_state=self.type != 'in')

        period = Period(period_id)
        fiscalyear = period.fiscalyear
        pattern.setdefault('company', self.company.id)
        pattern.setdefault('fiscalyear', fiscalyear.id)
        pattern.setdefault('period', period.id)

        for invoice_sequence in fiscalyear.invoice_sequences:
            if invoice_sequence.match(pattern):
                sequence = getattr(
                    invoice_sequence, self._sequence_field)
                break
        else:
            raise InvoiceNumberError(
                gettext('account_invoice.msg_invoice_no_sequence',
                    invoice=self.rec_name,
                    fiscalyear=fiscalyear.rec_name))
        with Transaction().set_context(date=accounting_date):
            return Sequence.get_id(sequence.id), sequence

    @property
    def _sequence_field(self):
        "Returns the field name of invoice_sequence to use"
        field = self.type
        if (all(l.amount <= 0 for l in self.lines if l.product)
                and self.total_amount < 0):
            field += '_credit_note'
        else:
            field += '_invoice'
        return field + '_sequence'

    @classmethod
    def tax_identifier_types(cls):
        return Pool().get('party.party').tax_identifier_types()

    def get_tax_identifier(self):
        "Return the default computed tax identifier"
        types = self.tax_identifier_types()
        for identifier in self.company.party.identifiers:
            if identifier.type in types:
                return identifier.id

    @property
    def is_modifiable(self):
        return not (self.state in {'posted', 'paid'}
            or (self.state == 'cancelled'
                and (self.move or self.cancel_move or self.number)))

    @classmethod
    def check_modify(cls, invoices):
        '''
        Check if the invoices can be modified
        '''
        for invoice in invoices:
            if not invoice.is_modifiable:
                raise AccessError(
                    gettext('account_invoice.msg_invoice_modify',
                        invoice=invoice.rec_name))

    def get_rec_name(self, name):
        items = []
        if self.number:
            items.append(self.number)
        if self.reference:
            items.append('[%s]' % self.reference)
        if not items:
            items.append('(%s)' % self.id)
        return ' '.join(items)

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('number',) + tuple(clause[1:]),
            ('reference',) + tuple(clause[1:]),
            ('party',) + tuple(clause[1:]),
            ]

    def get_origins(self, name):
        return ', '.join(set(filter(None,
                    (l.origin_name for l in self.lines))))

    @classmethod
    def view_attributes(cls):
        return [
            ('/form//field[@name="comment"]', 'spell', Eval('party_lang')),
            ('/tree', 'visual',
                If((
                        (Eval('type') == 'out')
                        & (Eval('amount_to_pay_today', 0) > 0))
                    | ((Eval('type') == 'in')
                        & (Eval('amount_to_pay_today', 0) < 0)),
                    'danger',
                    If(Eval('state') == 'cancelled', 'muted', ''))),
            ]

    @classmethod
    def delete(cls, invoices):
        cls.check_modify(invoices)
        # Cancel before delete
        cls.cancel(invoices)
        for invoice in invoices:
            if invoice.state != 'cancelled':
                raise AccessError(
                    gettext('account_invoice.msg_invoice_delete_cancel',
                        invoice=invoice.rec_name))
            if invoice.number:
                raise AccessError(
                    gettext('account_invoice.msg_invoice_delete_numbered',
                        invoice=invoice.rec_name))
        super(Invoice, cls).delete(invoices)

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        all_invoices = []
        for invoices, values in zip(actions, actions):
            if set(values) - set(cls._check_modify_exclude):
                cls.check_modify(invoices)
            all_invoices += invoices
        update_tax = [i for i in all_invoices if i.state == 'draft']
        super(Invoice, cls).write(*args)
        if update_tax:
            cls.update_taxes(update_tax)

    @classmethod
    def copy(cls, invoices, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('number', None)
        default.setdefault('sequence')
        default.setdefault('move', None)
        default.setdefault('cancel_move', None)
        default.setdefault('invoice_report_cache', None)
        default.setdefault('invoice_report_cache_id', None)
        default.setdefault('invoice_report_format', None)
        default.setdefault('payment_lines', None)
        default.setdefault('invoice_date', None)
        default.setdefault('accounting_date', None)
        default.setdefault('payment_term_date', None)
        default.setdefault('lines_to_pay', None)
        return super(Invoice, cls).copy(invoices, default=default)

    @classmethod
    def validate(cls, invoices):
        super(Invoice, cls).validate(invoices)
        for invoice in invoices:
            invoice.check_same_account()
            invoice.check_payment_lines()

    def check_same_account(self):
        for line in self.lines:
            if (line.type == 'line'
                    and line.account == self.account):
                raise InvoiceValidationError(
                    gettext('account_invoice.msg_invoice_same_account_line',
                        account=self.account.rec_name,
                        invoice=self.rec_name,
                        line=line.rec_name))

    def check_payment_lines(self):
        amount = sum(l.debit - l.credit for l in self.lines_to_pay)
        payment_amount = sum(l.debit - l.credit for l in self.payment_lines)
        if abs(amount) < abs(payment_amount):
            raise InvoiceValidationError(
                gettext('account_invoice'
                    '.msg_invoice_payment_lines_greater_amount',
                    invoice=self.rec_name))

    def get_reconcile_lines_for_amount(self, amount):
        '''
        Return list of lines and the remainder to make reconciliation.
        '''
        Result = namedtuple('Result', ['lines', 'remainder'])

        lines = [l for l in self.payment_lines + self.lines_to_pay
            if not l.reconciliation]

        best = Result([], self.total_amount)
        for n in range(len(lines), 0, -1):
            for comb_lines in combinations(lines, n):
                remainder = sum((l.debit - l.credit) for l in comb_lines)
                remainder -= amount
                result = Result(list(comb_lines), remainder)
                if self.currency.is_zero(remainder):
                    return result
                if abs(remainder) < abs(best.remainder):
                    best = result
        return best

    def pay_invoice(self, amount, payment_method, date, description=None,
            amount_second_currency=None, second_currency=None, overpayment=0):
        '''
        Adds a payment of amount to an invoice using the journal, date and
        description.
        If overpayment is set, then only the amount minus the overpayment is
        used to pay off the invoice.
        Returns the payment lines.
        '''
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Period = pool.get('account.period')

        pay_line = Line(account=self.account)
        counterpart_line = Line()
        lines = [pay_line, counterpart_line]

        pay_amount = amount - overpayment
        if pay_amount >= 0:
            if self.type == 'out':
                pay_line.debit, pay_line.credit = 0, pay_amount
            else:
                pay_line.debit, pay_line.credit = pay_amount, 0
        else:
            if self.type == 'out':
                pay_line.debit, pay_line.credit = -pay_amount, 0
            else:
                pay_line.debit, pay_line.credit = 0, -pay_amount
        if overpayment:
            overpayment_line = Line(account=self.account)
            lines.insert(1, overpayment_line)
            overpayment_line.debit = (
                abs(overpayment) if pay_line.debit else 0)
            overpayment_line.credit = (
                abs(overpayment) if pay_line.credit else 0)

        counterpart_line.debit = abs(amount) if pay_line.credit else 0
        counterpart_line.credit = abs(amount) if pay_line.debit else 0
        if counterpart_line.debit:
            payment_acccount = 'debit_account'
        else:
            payment_acccount = 'credit_account'
        counterpart_line.account = getattr(
            payment_method, payment_acccount).current(date=date)

        for line in lines:
            if line.account.party_required:
                line.party = self.party
            if amount_second_currency:
                line.amount_second_currency = amount_second_currency.copy_sign(
                    line.debit - line.credit)
                line.second_currency = second_currency

        period_id = Period.find(self.company.id, date=date)

        move = Move(
            journal=payment_method.journal, period=period_id, date=date,
            origin=self, description=description,
            company=self.company, lines=lines)
        move.save()
        Move.post([move])

        payment_lines = [l for l in move.lines if l.account == self.account]
        payment_line = [l for l in payment_lines
            if (l.debit, l.credit) == (pay_line.debit, pay_line.credit)][0]
        self.add_payment_lines({self: [payment_line]})
        return payment_lines

    @classmethod
    def add_payment_lines(cls, payments):
        "Add value lines to the key invoice from the payment dictionary."
        to_write = []
        for invoice, lines in payments.items():
            if invoice.state == 'paid':
                raise AccessError(
                    gettext('account_invoice'
                        '.msg_invoice_payment_lines_add_remove_paid',
                        invoice=invoice.rec_name))
            to_write.append([invoice])
            to_write.append({'payment_lines': [('add', lines)]})
        if to_write:
            cls.write(*to_write)

    @classmethod
    def remove_payment_lines(cls, lines):
        "Remove payment lines from their invoices."
        pool = Pool()
        PaymentLine = pool.get('account.invoice-account.move.line')

        payments = defaultdict(list)
        ids = list(map(int, lines))
        for sub_ids in grouped_slice(ids):
            payment_lines = PaymentLine.search([
                    ('line', 'in', list(sub_ids)),
                    ])
            for payment_line in payment_lines:
                payments[payment_line.invoice].append(payment_line.line)

        to_write = []
        for invoice, lines in payments.items():
            if invoice.state == 'paid':
                raise AccessError(
                    gettext('account_invoice'
                        '.msg_invoice_payment_lines_add_remove_paid',
                        invoice=invoice.rec_name))
            to_write.append([invoice])
            to_write.append({'payment_lines': [('remove', lines)]})
        if to_write:
            cls.write(*to_write)

    def print_invoice(self):
        '''
        Generate invoice report and store it in invoice_report field.
        '''
        if self.invoice_report_cache:
            return
        InvoiceReport = Pool().get('account.invoice', type='report')
        InvoiceReport.execute([self.id], {})

    def _credit(self, **values):
        '''
        Return values to credit invoice.
        '''
        credit = self.__class__(**values)

        for field in [
                'company', 'tax_identifier', 'party', 'party_tax_identifier',
                'invoice_address', 'currency', 'journal', 'account',
                'payment_term', 'description', 'comment', 'type']:
            setattr(credit, field, getattr(self, field))

        credit.lines = [line._credit() for line in self.lines]
        credit.taxes = [tax._credit() for tax in self.taxes if tax.manual]
        return credit

    @classmethod
    def credit(cls, invoices, refund=False, **values):
        '''
        Credit invoices and return ids of new invoices.
        Return the list of new invoice
        '''
        new_invoices = [i._credit(**values) for i in invoices]
        cls.save(new_invoices)
        cls.update_taxes(new_invoices)
        if refund:
            cls.post(new_invoices)
            for invoice, new_invoice in zip(invoices, new_invoices):
                if invoice.state != 'posted':
                    raise AccessError(
                        gettext('account_invoice'
                            '.msg_invoice_credit_refund_not_posted',
                            invoice=invoice.rec_name))
                invoice.cancel_move = new_invoice.move
            cls.save(invoices)
            cls.cancel(invoices)
        return new_invoices

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, invoices):
        Move = Pool().get('account.move')

        moves = []
        for invoice in invoices:
            if invoice.move:
                moves.append(invoice.move)
        if moves:
            Move.delete(moves)

    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    def validate_invoice(cls, invoices):
        pool = Pool()
        Move = pool.get('account.move')

        invoices_in = cls.browse([i for i in invoices if i.type == 'in'])
        cls.set_number(invoices_in)
        moves = []
        for invoice in invoices_in:
            move = invoice.get_move()
            if move != invoice.move:
                invoice.move = move
                moves.append(move)
        if moves:
            Move.save(moves)
        cls.save(invoices_in)

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, invoices):
        Move = Pool().get('account.move')

        cls.set_number(invoices)
        moves = []
        for invoice in invoices:
            move = invoice.get_move()
            if move != invoice.move:
                invoice.move = move
                moves.append(move)
            if invoice.state != 'posted':
                invoice.state = 'posted'
        if moves:
            Move.save(moves)
        cls.save(invoices)
        Move.post([i.move for i in invoices if i.move.state != 'posted'])
        reconciled = []
        for invoice in invoices:
            if invoice.type == 'out':
                invoice.print_invoice()
            if invoice.reconciled:
                reconciled.append(invoice)
        if reconciled:
            cls.__queue__.process(reconciled)

    @classmethod
    @ModelView.button_action('account_invoice.wizard_pay')
    def pay(cls, invoices):
        pass

    @classmethod
    def process(cls, invoices):
        paid = []
        posted = []
        for invoice in invoices:
            if invoice.state not in ('posted', 'paid'):
                continue
            if invoice.reconciled:
                paid.append(invoice)
            else:
                posted.append(invoice)
        cls.paid(paid)
        cls.post(posted)

    @classmethod
    @Workflow.transition('paid')
    def paid(cls, invoices):
        # Remove links to lines which actually do not pay the invoice
        cls._clean_payments(invoices)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, invoices):
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')

        cancel_moves = []
        delete_moves = []
        to_save = []
        for invoice in invoices:
            if invoice.move:
                if invoice.move.state == 'draft':
                    delete_moves.append(invoice.move)
                elif not invoice.cancel_move:
                    if (invoice.type == 'out'
                            and not invoice.company.cancel_invoice_out):
                        raise AccessError(
                            gettext('account_invoice'
                                '.msg_invoice_customer_cancel_move',
                                invoice=invoice.rec_name))
                    invoice.cancel_move = invoice.move.cancel()
                    to_save.append(invoice)
                    cancel_moves.append(invoice.cancel_move)
        if cancel_moves:
            Move.save(cancel_moves)
        cls.save(to_save)
        if delete_moves:
            Move.delete(delete_moves)
        if cancel_moves:
            Move.post(cancel_moves)
        # Write state before reconcile to prevent invoice to go to paid state
        cls.write(invoices, {
                'state': 'cancelled',
                })

        for invoice in invoices:
            if not invoice.move or not invoice.cancel_move:
                continue
            to_reconcile = []
            for line in invoice.move.lines + invoice.cancel_move.lines:
                if line.account == invoice.account:
                    to_reconcile.append(line)
            Line.reconcile(to_reconcile)

        cls._clean_payments(invoices)

    @classmethod
    def _clean_payments(cls, invoices):
        to_write = []
        for invoice in invoices:
            to_remove = []
            reconciliations = [l.reconciliation for l in invoice.lines_to_pay]
            for payment_line in invoice.payment_lines:
                if payment_line.reconciliation not in reconciliations:
                    to_remove.append(payment_line.id)
            if to_remove:
                to_write.append([invoice])
                to_write.append({
                        'payment_lines': [('remove', to_remove)],
                        })
        if to_write:
            cls.write(*to_write)


class InvoicePaymentLine(ModelSQL):
    'Invoice - Payment Line'
    __name__ = 'account.invoice-account.move.line'
    invoice = fields.Many2One('account.invoice', 'Invoice', ondelete='CASCADE',
            select=True, required=True)
    invoice_account = fields.Function(
        fields.Many2One('account.account', "Invoice Account"),
        'get_invoice')
    invoice_party = fields.Function(
        fields.Many2One('party.party', "Invoice Party"), 'get_invoice')
    line = fields.Many2One(
        'account.move.line', 'Payment Line', ondelete='CASCADE',
        select=True, required=True,
        domain=[
            ('account', '=', Eval('invoice_account')),
            ('party', '=', Eval('invoice_party')),
            ],
        depends=['invoice_account', 'invoice_party'])

    @classmethod
    def __setup__(cls):
        super(InvoicePaymentLine, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('line_unique', Unique(t, t.line),
                'account_invoice.msg_invoice_payment_line_unique'),
            ]

    @classmethod
    def get_invoice(cls, records, names):
        result = {}
        for name in names:
            result[name] = {}
        invoice_account = 'invoice_account' in result
        invoice_party = 'invoice_party' in result
        for record in records:
            if invoice_account:
                result['invoice_account'][record.id] = (
                    record.invoice.account.id)
            if invoice_party:
                if record.invoice.account.party_required:
                    party = record.invoice.party.id
                else:
                    party = None
                result['invoice_party'][record.id] = party
        return result


class InvoiceLine(sequence_ordered(), ModelSQL, ModelView, TaxableMixin):
    'Invoice Line'
    __name__ = 'account.invoice.line'
    _states = {
        'readonly': Eval('invoice_state') != 'draft',
        }
    _depends = ['invoice_state']

    invoice = fields.Many2One('account.invoice', 'Invoice', ondelete='CASCADE',
        select=True, states={
            'required': (~Eval('invoice_type') & Eval('party')
                & Eval('currency') & Eval('company')),
            'invisible': Bool(Eval('context', {}).get('standalone')),
            'readonly': _states['readonly'] & Bool(Eval('invoice')),
            },
        depends=['invoice_type', 'party', 'company', 'currency'] + _depends)
    invoice_state = fields.Function(
        fields.Selection('get_invoice_states', "Invoice State"),
        'on_change_with_invoice_state')
    invoice_type = fields.Selection('get_invoice_types', "Invoice Type",
        select=True,
        states={
            'readonly': Eval('context', {}).get('type') | Eval('type'),
            'required': ~Eval('invoice'),
            },
        depends=['invoice', 'type'])
    party = fields.Many2One('party.party', 'Party', select=True,
        states={
            'required': ~Eval('invoice'),
            'readonly': _states['readonly'],
            },
        depends=['invoice'] + _depends)
    party_lang = fields.Function(fields.Char('Party Language'),
        'on_change_with_party_lang')
    currency = fields.Many2One(
        'currency.currency', "Currency", required=True,
        states=_states, depends=_depends)
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    company = fields.Many2One('company.company', 'Company', required=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ], select=True, states=_states, depends=_depends)
    type = fields.Selection([
        ('line', 'Line'),
        ('subtotal', 'Subtotal'),
        ('title', 'Title'),
        ('comment', 'Comment'),
        ], 'Type', select=True, required=True, states={
            'invisible': Bool(Eval('context', {}).get('standalone')),
            'readonly': _states['readonly'],
            }, depends=_depends)
    quantity = fields.Float('Quantity',
        digits=(16, Eval('unit_digits', 2)),
        states={
            'invisible': Eval('type') != 'line',
            'required': Eval('type') == 'line',
            'readonly': _states['readonly'],
            },
        depends=['type', 'unit_digits'] + _depends)
    unit = fields.Many2One('product.uom', 'Unit', ondelete='RESTRICT',
        states={
            'required': Bool(Eval('product')),
            'invisible': Eval('type') != 'line',
            'readonly': _states['readonly'],
            },
        domain=[
            If(Bool(Eval('product_uom_category')),
                ('category', '=', Eval('product_uom_category')),
                ('category', '!=', -1)),
            ],
        depends=['product', 'type', 'product_uom_category'] + _depends)
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
        'on_change_with_unit_digits')
    product = fields.Many2One('product.product', 'Product',
        ondelete='RESTRICT',
        domain=[
            If(Bool(Eval('product_uom_category')),
                ('default_uom_category', '=', Eval('product_uom_category')),
                ()),
            ],
        states={
            'invisible': Eval('type') != 'line',
            'readonly': _states['readonly'],
            },
        context={
            'company': Eval('company', None),
            },
        depends=['type', 'product_uom_category', 'company'] + _depends)
    product_uom_category = fields.Function(
        fields.Many2One('product.uom.category', 'Product Uom Category'),
        'on_change_with_product_uom_category')
    account = fields.Many2One('account.account', 'Account',
        ondelete='RESTRICT',
        states={
            'invisible': Eval('type') != 'line',
            'required': Eval('type') == 'line',
            'readonly': _states['readonly'],
            },
        context={
            'date': If(Eval('_parent_invoice', {}).get('accounting_date'),
                Eval('_parent_invoice', {}).get('accounting_date'),
                Eval('_parent_invoice', {}).get('invoice_date')),
            },
        depends=['type', 'invoice_type', 'company'] + _depends)
    unit_price = fields.Numeric('Unit Price', digits=price_digits,
        states={
            'invisible': Eval('type') != 'line',
            'required': Eval('type') == 'line',
            'readonly': _states['readonly'],
            },
        depends=['type'] + _depends)
    amount = fields.Function(fields.Numeric('Amount',
            digits=(16, Eval('_parent_invoice', {}).get('currency_digits',
                    Eval('currency_digits', 2))),
            states={
                'invisible': ~Eval('type').in_(['line', 'subtotal']),
                },
            depends=['type', 'currency_digits']), 'get_amount')
    description = fields.Text('Description', size=None,
        states=_states, depends=_depends)
    note = fields.Text('Note')
    taxes = fields.Many2Many('account.invoice.line-account.tax',
        'line', 'tax', 'Taxes',
        order=[('tax.sequence', 'ASC'), ('tax.id', 'ASC')],
        domain=[('parent', '=', None), ['OR',
                ('group', '=', None),
                ('group.kind', 'in',
                    If(Bool(Eval('_parent_invoice')),
                        If(Eval('_parent_invoice', {}).get('type') == 'out',
                            ['sale', 'both'],
                            ['purchase', 'both']),
                        If(Eval('invoice_type') == 'out',
                            ['sale', 'both'],
                            ['purchase', 'both']))
                    )],
            ('company', '=', Eval('company', -1)),
            ],
        states={
            'invisible': Eval('type') != 'line',
            'readonly': _states['readonly'] | ~Bool(Eval('account')),
            },
        depends=['type', 'invoice_type', 'company', 'account'] + _depends)
    taxes_date = fields.Date(
        "Taxes Date",
        states={
            'invisible': Eval('type') != 'line',
            'readonly': _states['readonly'],
            },
        depends=['type'] + _depends,
        help="The date at which the taxes are computed.\n"
        "Leave empty for the accounting date.")
    invoice_taxes = fields.Function(fields.Many2Many('account.invoice.tax',
        None, None, 'Invoice Taxes'), 'get_invoice_taxes')
    origin = fields.Reference('Origin', selection='get_origin', select=True,
        states=_states, depends=_depends)

    del _states, _depends

    @classmethod
    def __setup__(cls):
        super(InvoiceLine, cls).__setup__()
        cls._check_modify_exclude = {'note', 'origin'}

        # Set account domain dynamically for kind
        cls.account.domain = [
            ('closed', '!=', True),
            ('company', '=', Eval('company', -1)),
            If(Bool(Eval('_parent_invoice')),
                If(Eval('_parent_invoice', {}).get('type') == 'out',
                    cls._account_domain('out'),
                    If(Eval('_parent_invoice', {}).get('type') == 'in',
                        cls._account_domain('in'),
                        ['OR',
                            cls._account_domain('out'),
                            cls._account_domain('in')])),
                If(Eval('invoice_type') == 'out',
                    cls._account_domain('out'),
                    If(Eval('invoice_type') == 'in',
                        cls._account_domain('in'),
                        ['OR',
                            cls._account_domain('out'),
                            cls._account_domain('in')]))),
            ]
        cls.account.depends += ['company', 'invoice_type']
        cls.sequence.states.update({
                'invisible': Bool(Eval('context', {}).get('standalone')),
                })

    @staticmethod
    def _account_domain(type_):
        if type_ == 'out':
            return ['OR', ('type.revenue', '=', True)]
        elif type_ == 'in':
            return ['OR', ('type.expense', '=', True)]

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        invoice = Invoice.__table__()
        sql_table = cls.__table__()
        super(InvoiceLine, cls).__register__(module_name)
        cursor = Transaction().connection.cursor()
        table = cls.__table_handler__(module_name)

        # Migration from 3.4: company is required
        cursor.execute(*sql_table.join(invoice,
                condition=sql_table.invoice == invoice.id
                ).select(sql_table.id, invoice.company,
                where=sql_table.company == Null))
        for line_id, company_id in cursor.fetchall():
            cursor.execute(*sql_table.update([sql_table.company], [company_id],
                    where=sql_table.id == line_id))

        # Migration from 4.6: drop required on description
        table.not_null_action('description', action='remove')

        # Migration from 5.0: remove check constraints
        table.drop_constraint('type_account')
        table.drop_constraint('type_invoice')

    @classmethod
    def get_invoice_types(cls):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        return Invoice.fields_get(['type'])['type']['selection'] + [(None, '')]

    @fields.depends(
        'invoice', '_parent_invoice.currency', '_parent_invoice.company')
    def on_change_invoice(self):
        if self.invoice:
            self.currency = self.invoice.currency
            self.company = self.invoice.company

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = Company(Transaction().context['company'])
            return company.currency.id

    @staticmethod
    def default_currency_digits():
        Company = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = Company(Transaction().context['company'])
            return company.currency.digits
        return 2

    @staticmethod
    def default_unit_digits():
        return 2

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_type():
        return 'line'

    @classmethod
    def default_invoice_state(cls):
        return 'draft'

    @classmethod
    def get_invoice_states(cls):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        return Invoice.fields_get(['state'])['state']['selection']

    @fields.depends('invoice', '_parent_invoice.state')
    def on_change_with_invoice_state(self, name=None):
        if self.invoice:
            return self.invoice.state
        return 'draft'

    @fields.depends('party')
    def on_change_with_party_lang(self, name=None):
        Config = Pool().get('ir.configuration')
        if self.party and self.party.lang:
            return self.party.lang.code
        return Config.get_language()

    @fields.depends('unit')
    def on_change_with_unit_digits(self, name=None):
        if self.unit:
            return self.unit.digits
        return 2

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2

    @fields.depends('type', 'quantity', 'unit_price', 'invoice',
        '_parent_invoice.currency', 'currency')
    def on_change_with_amount(self):
        if self.type == 'line':
            currency = (self.invoice.currency if self.invoice
                else self.currency)
            amount = (Decimal(str(self.quantity or '0.0'))
                * (self.unit_price or Decimal('0.0')))
            if currency:
                return currency.round(amount)
            return amount
        return Decimal('0.0')

    def get_amount(self, name):
        if self.type == 'line':
            return self.on_change_with_amount()
        elif self.type == 'subtotal':
            subtotal = Decimal(0)
            for line2 in self.invoice.lines:
                if line2.type == 'line':
                    subtotal += line2.invoice.currency.round(
                        Decimal(str(line2.quantity)) * line2.unit_price)
                elif line2.type == 'subtotal':
                    if self == line2:
                        break
                    subtotal = Decimal(0)
            return subtotal
        else:
            return Decimal(0)

    @property
    def origin_name(self):
        if isinstance(self.origin, self.__class__):
            return self.origin.invoice.rec_name
        return self.origin.rec_name if self.origin else None

    @property
    def taxable_lines(self):
        # In case we're called from an on_change we have to use some sensible
        # defaults
        return [(
                getattr(self, 'taxes', None) or [],
                getattr(self, 'unit_price', None) or Decimal(0),
                getattr(self, 'quantity', None) or 0,
                getattr(self, 'tax_date', None),
                )]

    @property
    def tax_date(self):
        return self.taxes_date or self.invoice.tax_date

    def _get_tax_context(self):
        if self.invoice:
            return self.invoice._get_tax_context()
        else:
            return {}

    def get_invoice_taxes(self, name):
        if not self.invoice:
            return
        taxes_keys = list(self._get_taxes().keys())
        taxes = []
        for tax in self.invoice.taxes:
            if tax.manual:
                continue
            key = tax._key
            if key in taxes_keys:
                taxes.append(tax.id)
        return taxes

    @fields.depends('invoice',
        '_parent_invoice.accounting_date', '_parent_invoice.invoice_date')
    def _get_tax_rule_pattern(self):
        '''
        Get tax rule pattern
        '''
        if self.invoice:
            date = self.invoice.accounting_date or self.invoice.invoice_date
        else:
            date = None
        return {
            'date': date,
            }

    @fields.depends('product', 'unit', '_parent_invoice.type',
        '_parent_invoice.party', 'party', 'invoice', 'invoice_type',
        '_parent_invoice.invoice_date', '_parent_invoice.accounting_date',
        methods=['_get_tax_rule_pattern'])
    def on_change_product(self):
        if not self.product:
            return

        party = None
        if self.invoice and self.invoice.party:
            party = self.invoice.party
        elif self.party:
            party = self.party

        date = (self.invoice.accounting_date or self.invoice.invoice_date
            if self.invoice else None)
        if self.invoice and self.invoice.type:
            type_ = self.invoice.type
        else:
            type_ = self.invoice_type
        if type_ == 'in':
            with Transaction().set_context(date=date):
                self.account = self.product.account_expense_used
            taxes = []
            pattern = self._get_tax_rule_pattern()
            for tax in self.product.supplier_taxes_used:
                if party and party.supplier_tax_rule:
                    tax_ids = party.supplier_tax_rule.apply(tax, pattern)
                    if tax_ids:
                        taxes.extend(tax_ids)
                    continue
                taxes.append(tax)
            if party and party.supplier_tax_rule:
                tax_ids = party.supplier_tax_rule.apply(None, pattern)
                if tax_ids:
                    taxes.extend(tax_ids)
            self.taxes = taxes
        else:
            with Transaction().set_context(date=date):
                self.account = self.product.account_revenue_used
            taxes = []
            pattern = self._get_tax_rule_pattern()
            for tax in self.product.customer_taxes_used:
                if party and party.customer_tax_rule:
                    tax_ids = party.customer_tax_rule.apply(tax, pattern)
                    if tax_ids:
                        taxes.extend(tax_ids)
                    continue
                taxes.append(tax.id)
            if party and party.customer_tax_rule:
                tax_ids = party.customer_tax_rule.apply(None, pattern)
                if tax_ids:
                    taxes.extend(tax_ids)
            self.taxes = taxes

        category = self.product.default_uom.category
        if not self.unit or self.unit.category != category:
            self.unit = self.product.default_uom.id
            self.unit_digits = self.product.default_uom.digits

    @fields.depends('product')
    def on_change_with_product_uom_category(self, name=None):
        if self.product:
            return self.product.default_uom_category.id

    @fields.depends('account', 'product', 'invoice',
        '_parent_invoice.party', '_parent_invoice.type',
        'party', 'invoice', 'invoice_type',
        methods=['_get_tax_rule_pattern'])
    def on_change_account(self):
        if self.product:
            return
        taxes = []
        party = None
        if self.invoice and self.invoice.party:
            party = self.invoice.party
        elif self.party:
            party = self.party

        if self.invoice and self.invoice.type:
            type_ = self.invoice.type
        else:
            type_ = self.invoice_type
        if party and type_:
            if type_ == 'in':
                tax_rule = party.supplier_tax_rule
            else:
                tax_rule = party.customer_tax_rule
        else:
            tax_rule = None

        if self.account:
            pattern = self._get_tax_rule_pattern()
            for tax in self.account.taxes:
                if tax_rule:
                    tax_ids = tax_rule.apply(tax, pattern)
                    if tax_ids:
                        taxes.extend(tax_ids)
                    continue
                taxes.append(tax)
            if tax_rule:
                tax_ids = tax_rule.apply(None, pattern)
                if tax_ids:
                    taxes.extend(tax_ids)
        self.taxes = taxes

    @classmethod
    def _get_origin(cls):
        'Return list of Model names for origin Reference'
        return [cls.__name__]

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        models = cls._get_origin()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [(None, '')] + [(m.model, m.name) for m in models]

    def get_rec_name(self, name):
        pool = Pool()
        Lang = pool.get('ir.lang')
        if self.product:
            lang = Lang.get()
            prefix = (lang.format(
                    '%.*f', (self.unit.digits, self.quantity or 0))
                + '%s %s' % (self.unit.symbol, self.product.rec_name))
        elif self.account:
            prefix = self.account.rec_name
        else:
            prefix = '(%s)' % self.id
        if self.invoice:
            return '%s @ %s' % (prefix, self.invoice.rec_name)
        else:
            return prefix

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            ('invoice.rec_name',) + tuple(clause[1:]),
            ('product.rec_name',) + tuple(clause[1:]),
            ('account.rec_name',) + tuple(clause[1:]),
            ]

    @classmethod
    def check_modify(cls, lines, fields=None):
        '''
        Check if the lines can be modified
        '''
        if fields is None or fields - cls._check_modify_exclude:
            for line in lines:
                if line.invoice and not line.invoice.is_modifiable:
                    raise AccessError(
                        gettext('account_invoice.msg_invoice_line_modify',
                            line=line.rec_name,
                            invoice=line.invoice.rec_name))

    @classmethod
    def view_attributes(cls):
        return [
            ('/form//field[@name="note"]|/form//field[@name="description"]',
                'spell', If(Bool(Eval('_parent_invoice')),
                    Eval('_parent_invoice', {}).get('party_lang'),
                    Eval('party_lang')))]

    @classmethod
    def delete(cls, lines):
        cls.check_modify(lines)
        super(InvoiceLine, cls).delete(lines)

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        for lines, values in zip(actions, actions):
            cls.check_modify(lines, set(values))
        super(InvoiceLine, cls).write(*args)

    @classmethod
    def create(cls, vlist):
        Invoice = Pool().get('account.invoice')
        invoice_ids = []
        for vals in vlist:
            if vals.get('invoice'):
                invoice_ids.append(vals.get('invoice'))
        for invoice in Invoice.browse(invoice_ids):
            if invoice.state in ('posted', 'paid', 'cancelled'):
                raise AccessError(
                    gettext('account_invoice.msg_invoice_line_create',
                        invoice=invoice.rec_name))
        return super(InvoiceLine, cls).create(vlist)

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('origin', None)
        return super(InvoiceLine, cls).copy(lines, default=default)

    @classmethod
    def validate(cls, lines):
        super(InvoiceLine, cls).validate(lines)
        for line in lines:
            line.check_same_account()

    def check_same_account(self):
        if self.type == 'line':
            if (self.invoice
                    and self.account == self.invoice.account):
                raise InvoiceLineValidationError(
                    gettext('account_invoice.msg_invoice_same_account_line',
                        account=self.account.rec_name,
                        invoice=self.invoice.rec_name,
                        lines=self.rec_name))

    def _compute_taxes(self):
        pool = Pool()
        Currency = pool.get('currency.currency')
        TaxLine = pool.get('account.tax.line')

        tax_lines = []
        if self.type != 'line':
            return tax_lines
        taxes = self._get_taxes().values()
        for tax in taxes:
            amount = tax['base']
            with Transaction().set_context(
                    date=self.invoice.currency_date):
                amount = Currency.compute(
                    self.invoice.currency, amount,
                    self.invoice.company.currency)
            tax_line = TaxLine()
            tax_line.amount = amount
            tax_line.type = 'base'
            tax_line.tax = tax['tax']
            tax_lines.append(tax_line)
        return tax_lines

    def get_move_lines(self):
        '''
        Return a list of move lines instances for invoice line
        '''
        pool = Pool()
        Currency = pool.get('currency.currency')
        MoveLine = pool.get('account.move.line')
        if self.type != 'line':
            return []
        line = MoveLine()
        if self.invoice.currency != self.invoice.company.currency:
            with Transaction().set_context(date=self.invoice.currency_date):
                amount = Currency.compute(self.invoice.currency,
                    self.amount, self.invoice.company.currency)
            line.amount_second_currency = self.amount
            line.second_currency = self.invoice.currency
        else:
            amount = self.amount
            line.amount_second_currency = None
            line.second_currency = None
        if amount >= 0:
            if self.invoice.type == 'out':
                line.debit, line.credit = 0, amount
            else:
                line.debit, line.credit = amount, 0
        else:
            if self.invoice.type == 'out':
                line.debit, line.credit = -amount, 0
            else:
                line.debit, line.credit = 0, -amount
        if line.amount_second_currency:
            line.amount_second_currency = (
                line.amount_second_currency.copy_sign(
                    line.debit - line.credit))
        line.account = self.account
        if self.account.party_required:
            line.party = self.invoice.party
        line.origin = self
        line.tax_lines = self._compute_taxes()
        return [line]

    def _credit(self):
        '''
        Return credit line.
        '''
        line = self.__class__()
        line.origin = self
        if self.quantity:
            line.quantity = -self.quantity
        else:
            line.quantity = self.quantity

        for field in [
                'sequence', 'type', 'invoice_type', 'party', 'currency',
                'company', 'unit_price', 'description', 'unit', 'product',
                'account']:
            setattr(line, field, getattr(self, field))
        line.taxes_date = self.tax_date
        line.taxes = self.taxes
        return line


class InvoiceLineTax(ModelSQL):
    'Invoice Line - Tax'
    __name__ = 'account.invoice.line-account.tax'
    _table = 'account_invoice_line_account_tax'
    line = fields.Many2One('account.invoice.line', 'Invoice Line',
            ondelete='CASCADE', select=True, required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
            required=True)


class InvoiceTax(sequence_ordered(), ModelSQL, ModelView):
    'Invoice Tax'
    __name__ = 'account.invoice.tax'
    _rec_name = 'description'
    _states = {
        'readonly': Eval('invoice_state') != 'draft',
        }
    _depends = ['invoice_state']

    invoice = fields.Many2One('account.invoice', 'Invoice', ondelete='CASCADE',
            select=True,
        states={
            'readonly': _states['readonly'] & Bool(Eval('invoice')),
            },
        depends=_depends)
    invoice_state = fields.Function(
        fields.Selection('get_invoice_states', "Invoice State"),
        'on_change_with_invoice_state')
    description = fields.Char('Description', size=None, required=True,
        states=_states, depends=_depends)
    sequence_number = fields.Function(fields.Integer('Sequence Number'),
            'get_sequence_number')
    account = fields.Many2One('account.account', 'Account', required=True,
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', '=', Eval('_parent_invoice', {}).get('company', 0)),
            ],
        states=_states, depends=_depends)
    base = fields.Numeric('Base', required=True,
        digits=(16, Eval('_parent_invoice', {}).get('currency_digits', 2)),
        states=_states, depends=_depends)
    amount = fields.Numeric('Amount', required=True,
        digits=(16, Eval('_parent_invoice', {}).get('currency_digits', 2)),
        states=_states,
        depends=['tax', 'base', 'manual'] + _depends)
    currency = fields.Function(fields.Many2One('currency.currency',
        'Currency'), 'on_change_with_currency')
    manual = fields.Boolean('Manual', states=_states, depends=_depends)
    tax = fields.Many2One('account.tax', 'Tax',
        ondelete='RESTRICT',
        domain=[
            ('company', '=', Eval('_parent_invoice', {}).get('company', 0)),
            ],
        states={
            'readonly': ~Eval('manual', False) | _states['readonly'],
            },
        depends=['manual'] + _depends)
    legal_notice = fields.Text("Legal Notice", states=_states,
        depends=_depends)

    del _states, _depends

    @classmethod
    def __register__(cls, module_name):
        super(InvoiceTax, cls).__register__(module_name)

        table = cls.__table_handler__(module_name)

        # Migration from 4.6: drop base_sign and tax_sign
        table.not_null_action('base_sign', action='remove')
        table.not_null_action('tax_sign', action='remove')

    @staticmethod
    def default_base():
        return Decimal('0.0')

    @staticmethod
    def default_amount():
        return Decimal('0.0')

    @staticmethod
    def default_manual():
        return True

    @classmethod
    def default_invoice_state(cls):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        return Invoice.default_state()

    @classmethod
    def get_invoice_states(cls):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        return Invoice.fields_get(['state'])['state']['selection']

    @fields.depends('invoice', '_parent_invoice.state')
    def on_change_with_invoice_state(self, name=None):
        if self.invoice:
            return self.invoice.state

    @fields.depends('invoice', '_parent_invoice.currency')
    def on_change_with_currency(self, name=None):
        if self.invoice:
            return self.invoice.currency.id

    @fields.depends('tax', 'invoice', '_parent_invoice.party', 'base')
    def on_change_tax(self):
        Tax = Pool().get('account.tax')
        if not self.tax:
            return
        if self.invoice:
            context = self.invoice._get_tax_context()
        else:
            context = {}
        with Transaction().set_context(**context):
            tax = Tax(self.tax.id)
        self.description = tax.description
        if self.base is not None:
            if self.base >= 0:
                self.account = tax.invoice_account
            else:
                self.account = tax.credit_note_account

    @fields.depends('tax', 'base', 'amount', 'manual', 'invoice',
        '_parent_invoice.currency')
    def on_change_with_amount(self):
        Tax = Pool().get('account.tax')
        if self.tax and self.manual:
            tax = self.tax
            base = self.base or Decimal(0)
            for values in Tax.compute([tax], base, 1):
                if (values['tax'] == tax
                        and values['base'] == base):
                    amount = values['amount']
                    if self.invoice.currency:
                        amount = self.invoice.currency.round(amount)
                    return amount
        return self.amount

    @property
    def _key(self):
        # Same as _TaxKey
        tax_id = self.tax.id if self.tax else -1
        return (self.account.id, tax_id, self.base >= 0)

    @classmethod
    def check_modify(cls, taxes):
        '''
        Check if the taxes can be modified
        '''
        for tax in taxes:
            if not tax.invoice.is_modifiable:
                raise AccessError(
                    gettext('account_invoice.msg_invoice_tax_modify',
                        tax=tax.rec_name,
                        invoice=tax.invoice.rec_name))

    def get_sequence_number(self, name):
        i = 1
        for tax in self.invoice.taxes:
            if tax == self:
                return i
            i += 1
        return 0

    @classmethod
    def delete(cls, taxes):
        cls.check_modify(taxes)
        super(InvoiceTax, cls).delete(taxes)

    @classmethod
    def write(cls, *args):
        taxes = sum(args[0::2], [])
        cls.check_modify(taxes)
        super(InvoiceTax, cls).write(*args)

    @classmethod
    def create(cls, vlist):
        Invoice = Pool().get('account.invoice')
        invoice_ids = []
        for vals in vlist:
            if vals.get('invoice'):
                invoice_ids.append(vals['invoice'])
        for invoice in Invoice.browse(invoice_ids):
            if invoice.state in ('posted', 'paid', 'cancelled'):
                raise AccessError(
                    gettext('account_invoice.msg_invoice_tax_create',
                        invoice=invoice.rec_name))
        return super(InvoiceTax, cls).create(vlist)

    def get_move_lines(self):
        '''
        Return a list of move lines instances for invoice tax
        '''
        Currency = Pool().get('currency.currency')
        pool = Pool()
        Currency = pool.get('currency.currency')
        MoveLine = pool.get('account.move.line')
        TaxLine = pool.get('account.tax.line')
        line = MoveLine()
        if not self.amount:
            return []
        line.description = self.description
        if self.invoice.currency != self.invoice.company.currency:
            with Transaction().set_context(date=self.invoice.currency_date):
                amount = Currency.compute(self.invoice.currency, self.amount,
                    self.invoice.company.currency)
            line.amount_second_currency = self.amount
            line.second_currency = self.invoice.currency
        else:
            amount = self.amount
            line.amount_second_currency = None
            line.second_currency = None
        if amount >= 0:
            if self.invoice.type == 'out':
                line.debit, line.credit = 0, amount
            else:
                line.debit, line.credit = amount, 0
        else:
            if self.invoice.type == 'out':
                line.debit, line.credit = -amount, 0
            else:
                line.debit, line.credit = 0, -amount
        if line.amount_second_currency:
            line.amount_second_currency = (
                line.amount_second_currency.copy_sign(
                    line.debit - line.credit))
        line.account = self.account
        if self.account.party_required:
            line.party = self.invoice.party
        line.origin = self
        if self.tax:
            tax_line = TaxLine()
            tax_line.amount = amount
            tax_line.type = 'tax'
            tax_line.tax = self.tax
            line.tax_lines = [tax_line]
        return [line]

    def _credit(self):
        '''
        Return credit tax.
        '''
        line = self.__class__()
        line.base = -self.base
        line.amount = -self.amount

        for field in ['description', 'sequence', 'manual', 'account', 'tax']:
            setattr(line, field, getattr(self, field))
        return line


class PaymentMethod(DeactivableMixin, ModelSQL, ModelView):
    'Payment Method'
    __name__ = 'account.invoice.payment.method'
    company = fields.Many2One('company.company', "Company", required=True)
    name = fields.Char("Name", required=True, translate=True)
    journal = fields.Many2One('account.journal', "Journal", required=True,
        domain=[('type', '=', 'cash')])
    credit_account = fields.Many2One('account.account', "Credit Account",
        required=True,
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', '=', Eval('company')),
            ],
        depends=['company'])
    debit_account = fields.Many2One('account.account', "Debit Account",
        required=True,
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', '=', Eval('company')),
            ],
        depends=['company'])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')


class InvoiceReport(Report):
    __name__ = 'account.invoice'

    @classmethod
    def __setup__(cls):
        super(InvoiceReport, cls).__setup__()
        cls.__rpc__['execute'] = RPC(False)

    @classmethod
    def _execute(cls, records, data, action):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        # Re-instantiate because records are TranslateModel
        invoice, = Invoice.browse(records)
        if invoice.invoice_report_cache:
            return (
                invoice.invoice_report_format,
                bytes(invoice.invoice_report_cache))
        else:
            result = super(InvoiceReport, cls)._execute(records, data, action)
            # If the invoice is posted or paid and the report not saved in
            # invoice_report_cache there was an error somewhere. So we save it
            # now in invoice_report_cache
            if invoice.state in {'posted', 'paid'} and invoice.type == 'out':
                format_, data = result
                invoice.invoice_report_format = format_
                invoice.invoice_report_cache = \
                    Invoice.invoice_report_cache.cast(data)
                invoice.save()
            return result

    @classmethod
    def render(cls, *args, **kwargs):
        # Reset to default language to always have header and footer rendered
        # in the default language
        with Transaction().set_context(language=False):
            return super().render(*args, **kwargs)

    @classmethod
    def execute(cls, ids, data):
        with Transaction().set_context(address_with_party=True):
            return super().execute(ids, data)

    @classmethod
    def get_context(cls, records, data):
        pool = Pool()
        Date = pool.get('ir.date')
        context = super(InvoiceReport, cls).get_context(records, data)
        context['invoice'] = context['record']
        context['today'] = Date.today()
        return context


class PayInvoiceStart(ModelView):
    'Pay Invoice'
    __name__ = 'account.invoice.pay.start'
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'], required=True)
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    currency_digits = fields.Integer('Currency Digits', readonly=True)
    description = fields.Char('Description', size=None)
    company = fields.Many2One('company.company', "Company", readonly=True)
    invoice_account = fields.Many2One(
        'account.account', "Invoice Account", readonly=True)
    payment_method = fields.Many2One(
        'account.invoice.payment.method', "Payment Method", required=True,
        domain=[
            ('company', '=', Eval('company')),
            ('debit_account', '!=', Eval('invoice_account')),
            ('credit_account', '!=', Eval('invoice_account')),
            ],
        depends=['company', 'amount', 'invoice_account'])
    date = fields.Date('Date', required=True)

    @staticmethod
    def default_date():
        Date = Pool().get('ir.date')
        return Date.today()

    @staticmethod
    def default_currency_digits():
        return 2

    @fields.depends('currency')
    def on_change_with_currency_digits(self):
        if self.currency:
            return self.currency.digits
        return 2


class PayInvoiceAsk(ModelView):
    'Pay Invoice'
    __name__ = 'account.invoice.pay.ask'
    type = fields.Selection([
            ('writeoff', "Write-Off"),
            ('partial', "Partial Payment"),
            ('overpayment', "Overpayment"),
            ], 'Type', required=True)
    writeoff = fields.Many2One(
        'account.move.reconcile.write_off', "Write Off",
        domain=[
            ('company', '=', Eval('company')),
            ],
        states={
            'invisible': Eval('type') != 'writeoff',
            'required': Eval('type') == 'writeoff',
            },
        depends=['company', 'type'])
    amount = fields.Numeric('Payment Amount',
            digits=(16, Eval('currency_digits', 2)),
            readonly=True, depends=['currency_digits'])
    currency = fields.Many2One('currency.currency', 'Payment Currency',
            readonly=True)
    currency_digits = fields.Integer('Payment Currency Digits', readonly=True)
    amount_writeoff = fields.Numeric('Write-Off Amount',
        digits=(16, Eval('currency_digits_writeoff', 2)), readonly=True,
        depends=['currency_digits_writeoff', 'type'], states={
            'invisible': Eval('type') != 'writeoff',
            })
    currency_writeoff = fields.Many2One('currency.currency',
        'Write-Off Currency', readonly=True, states={
            'invisible': Eval('type') != 'writeoff',
            }, depends=['type'])
    currency_digits_writeoff = fields.Integer('Write-Off Currency Digits',
            required=True, readonly=True)
    lines_to_pay = fields.Many2Many('account.move.line', None, None,
            'Lines to Pay', readonly=True)
    lines = fields.Many2Many('account.move.line', None, None, 'Lines',
        domain=[
            ('id', 'in', Eval('lines_to_pay')),
            ('reconciliation', '=', None),
            ],
        states={
            'invisible': Eval('type') != 'writeoff',
            },
        depends=['lines_to_pay', 'type'])
    payment_lines = fields.Many2Many('account.move.line', None, None,
        'Payment Lines', readonly=True,
        states={
            'invisible': Eval('type') != 'writeoff',
            }, depends=['type'])
    company = fields.Many2One('company.company', 'Company', readonly=True)
    invoice = fields.Many2One('account.invoice', 'Invoice', readonly=True)
    date = fields.Date('Date', readonly=True)

    @staticmethod
    def default_type():
        return 'partial'

    @fields.depends('lines', 'amount', 'currency', 'currency_writeoff',
        'invoice', 'payment_lines', 'date')
    def on_change_lines(self):
        Currency = Pool().get('currency.currency')

        if self.currency and self.currency_writeoff:
            with Transaction().set_context(date=self.date):
                amount = Currency.compute(self.currency, self.amount,
                    self.currency_writeoff)
        else:
            amount = self.amount

        self.amount_writeoff = Decimal('0.0')
        if not self.invoice:
            return
        for line in self.lines:
            self.amount_writeoff += line.debit - line.credit
        for line in self.payment_lines:
            self.amount_writeoff += line.debit - line.credit
        if self.invoice.type == 'in':
            self.amount_writeoff = - self.amount_writeoff - amount
        else:
            self.amount_writeoff = self.amount_writeoff - amount


class PayInvoice(Wizard):
    'Pay Invoice'
    __name__ = 'account.invoice.pay'
    start = StateView('account.invoice.pay.start',
        'account_invoice.pay_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'choice', 'tryton-ok', default=True),
            ])
    choice = StateTransition()
    ask = StateView('account.invoice.pay.ask',
        'account_invoice.pay_ask_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'pay', 'tryton-ok', default=True),
            ])
    pay = StateTransition()

    @classmethod
    def __setup__(cls):
        super(PayInvoice, cls).__setup__()
        cls.__rpc__['create'].fresh_session = True

    def get_reconcile_lines_for_amount(self, invoice, amount):
        if invoice.type == 'in':
            amount *= -1
        return invoice.get_reconcile_lines_for_amount(amount)

    def default_start(self, fields):
        default = {}
        invoice = self.record
        default['company'] = invoice.company.id
        default['currency'] = invoice.currency.id
        default['currency_digits'] = invoice.currency.digits
        default['amount'] = (invoice.amount_to_pay_today
            or invoice.amount_to_pay)
        default['invoice_account'] = invoice.account.id
        return default

    def transition_choice(self):
        pool = Pool()
        Currency = pool.get('currency.currency')

        invoice = self.record

        with Transaction().set_context(date=self.start.date):
            amount = Currency.compute(self.start.currency,
                self.start.amount, invoice.company.currency)
            amount_invoice = Currency.compute(
                self.start.currency, self.start.amount, invoice.currency)
        _, remainder = self.get_reconcile_lines_for_amount(invoice, amount)
        if (remainder == Decimal('0.0')
                and amount_invoice <= invoice.amount_to_pay):
            return 'pay'
        return 'ask'

    def default_ask(self, fields):
        pool = Pool()
        Currency = pool.get('currency.currency')

        default = {}
        invoice = self.record
        default['lines_to_pay'] = [x.id for x in invoice.lines_to_pay
                if not x.reconciliation]

        default['amount'] = self.start.amount
        default['date'] = self.start.date
        default['currency'] = self.start.currency.id
        default['currency_digits'] = self.start.currency_digits
        default['company'] = invoice.company.id

        with Transaction().set_context(date=self.start.date):
            amount = Currency.compute(self.start.currency,
                self.start.amount, invoice.company.currency)
            amount_invoice = Currency.compute(
                self.start.currency, self.start.amount, invoice.currency)

        if invoice.company.currency.is_zero(amount):
            lines = invoice.lines_to_pay
        else:
            lines, _ = self.get_reconcile_lines_for_amount(invoice, amount)
        default['lines'] = [x.id for x in lines]

        for line_id in default['lines'][:]:
            if line_id not in default['lines_to_pay']:
                default['lines'].remove(line_id)

        default['payment_lines'] = [x.id for x in invoice.payment_lines
                if not x.reconciliation]

        default['currency_writeoff'] = invoice.company.currency.id
        default['currency_digits_writeoff'] = invoice.company.currency.digits
        default['invoice'] = invoice.id

        if (amount_invoice > invoice.amount_to_pay
                or invoice.company.currency.is_zero(amount)):
            default['type'] = 'writeoff'
        return default

    def transition_pay(self):
        pool = Pool()
        Currency = pool.get('currency.currency')
        MoveLine = pool.get('account.move.line')
        Lang = pool.get('ir.lang')

        invoice = self.record

        with Transaction().set_context(date=self.start.date):
            amount = Currency.compute(self.start.currency,
                self.start.amount, invoice.company.currency)
            amount_invoice = Currency.compute(
                self.start.currency, self.start.amount, invoice.currency)

        reconcile_lines, remainder = \
            self.get_reconcile_lines_for_amount(invoice, amount)

        amount_second_currency = None
        second_currency = None
        if self.start.currency != invoice.company.currency:
            amount_second_currency = self.start.amount
            second_currency = self.start.currency

        overpayment = 0
        if (0 <= invoice.amount_to_pay < amount_invoice
                or amount_invoice < invoice.amount_to_pay <= 0):
            if self.ask.type == 'partial':
                lang = Lang.get()
                raise PayInvoiceError(
                    gettext('account_invoice'
                        '.msg_invoice_pay_amount_greater_amount_to_pay',
                        invoice=invoice.rec_name,
                        amount_to_pay=lang.currency(
                            invoice.amount_to_pay, invoice.currency)))
            else:
                overpayment = amount_invoice - invoice.amount_to_pay

        lines = []
        if not invoice.company.currency.is_zero(amount):
            lines = invoice.pay_invoice(amount,
                self.start.payment_method, self.start.date,
                self.start.description, amount_second_currency,
                second_currency, overpayment)

        if remainder:
            if self.ask.type != 'partial':
                to_reconcile = {l for l in self.ask.lines}
                to_reconcile.update(
                    l for l in invoice.payment_lines
                    if not l.reconciliation)
                if self.ask.type == 'writeoff':
                    to_reconcile.update(lines)
                if to_reconcile:
                    MoveLine.reconcile(
                        to_reconcile,
                        writeoff=self.ask.writeoff,
                        date=self.start.date)
        else:
            reconcile_lines += lines
            if reconcile_lines:
                MoveLine.reconcile(reconcile_lines)
        return 'end'


class CreditInvoiceStart(ModelView):
    'Credit Invoice'
    __name__ = 'account.invoice.credit.start'
    invoice_date = fields.Date("Invoice Date")
    with_refund = fields.Boolean('With Refund',
        states={
            'readonly': ~Eval('with_refund_allowed'),
            'invisible': ~Eval('with_refund_allowed'),
            },
        depends=['with_refund_allowed'],
        help='If true, the current invoice(s) will be cancelled.')
    with_refund_allowed = fields.Boolean("With Refund Allowed", readonly=True)


class CreditInvoice(Wizard):
    'Credit Invoice'
    __name__ = 'account.invoice.credit'
    start = StateView('account.invoice.credit.start',
        'account_invoice.credit_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Credit', 'credit', 'tryton-ok', default=True),
            ])
    credit = StateAction('account_invoice.act_invoice_form')

    def default_start(self, fields):
        default = {
            'with_refund': True,
            'with_refund_allowed': True,
            }
        for invoice in self.records:
            if invoice.state != 'posted' or invoice.type == 'in':
                default['with_refund'] = False
                default['with_refund_allowed'] = False
                break
            if invoice.payment_lines:
                default['with_refund'] = False
        return default

    @property
    def _credit_options(self):
        return dict(
            refund=self.start.with_refund,
            invoice_date=self.start.invoice_date,
            )

    def do_credit(self, action):
        credit_invoices = self.model.credit(
            self.records, **self._credit_options)

        data = {'res_id': [i.id for i in credit_invoices]}
        if len(credit_invoices) == 1:
            action['views'].reverse()
        return action, data
