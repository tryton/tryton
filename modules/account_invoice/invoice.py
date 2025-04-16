# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt
from collections import defaultdict, namedtuple
from decimal import Decimal
from itertools import chain, combinations, groupby

from genshi.template.text import TextTemplate
from sql import Null
from sql.aggregate import Sum
from sql.conditionals import Coalesce
from sql.functions import CharLength, Round
from sql.operators import Exists

from trytond import backend
from trytond.config import config
from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, Index, ModelSQL, ModelView, Unique, Workflow, dualmethod,
    fields, sequence_ordered)
from trytond.model.exceptions import AccessError
from trytond.modules.account.tax import TaxableMixin
from trytond.modules.company.model import (
    employee_field, reset_employee, set_employee)
from trytond.modules.currency.fields import Monetary
from trytond.modules.product import price_digits
from trytond.pool import Pool
from trytond.pyson import Bool, Eval, Id, If
from trytond.report import Report
from trytond.rpc import RPC
from trytond.tools import firstline, grouped_slice, reduce_ids, slugify
from trytond.transaction import Transaction
from trytond.wizard import (
    Button, StateAction, StateReport, StateTransition, StateView, Wizard)

from .exceptions import (
    InvoiceFutureWarning, InvoiceNumberError, InvoicePaymentTermDateWarning,
    InvoiceSimilarWarning, InvoiceTaxValidationError, InvoiceValidationError,
    PayInvoiceError)

if config.getboolean('account_invoice', 'filestore', default=False):
    file_id = 'invoice_report_cache_id'
    store_prefix = config.get('account_invoice', 'store_prefix', default=None)
else:
    file_id = None
    store_prefix = None


class InvoiceReportMixin:
    __slots__ = ()

    invoice_report_cache = fields.Binary(
        "Invoice Report", readonly=True,
        file_id=file_id, store_prefix=store_prefix)
    invoice_report_cache_id = fields.Char("Invoice Report ID", readonly=True)
    invoice_report_format = fields.Char("Invoice Report Format", readonly=True)


class Invoice(Workflow, ModelSQL, ModelView, TaxableMixin, InvoiceReportMixin):
    'Invoice'
    __name__ = 'account.invoice'
    _rec_name = 'number'
    _order_name = 'number'

    _states = {
        'readonly': Eval('state') != 'draft',
    }

    company = fields.Many2One(
        'company.company', "Company", required=True,
        states={
            'readonly': (
                _states['readonly']
                | Eval('party', True)
                | Eval('lines', [0])),
            })
    company_party = fields.Function(
        fields.Many2One(
            'party.party', "Company Party",
            context={
                'company': Eval('company', -1),
                },
            depends={'company'}),
        'on_change_with_company_party')
    tax_identifier = fields.Many2One(
        'party.identifier', "Tax Identifier", ondelete='RESTRICT',
        states=_states)
    type = fields.Selection([
            ('out', "Customer"),
            ('in', "Supplier"),
            ], "Type", required=True,
        states={
            'readonly': ((Eval('state') != 'draft')
                | Eval('context', {}).get('type')
                | (Eval('lines', [0]) & Eval('type'))),
            })
    type_name = fields.Function(fields.Char('Type'), 'get_type_name')
    number = fields.Char("Number", readonly=True)
    reference = fields.Char(
        "Reference",
        states={
            'readonly': (
                Eval('has_report_cache', False)
                & ~Id('account', 'group_account_admin').in_(
                    Eval('context', {}).get('groups', []))),
            })
    description = fields.Char("Description", size=None,
        states={
            'readonly': (
                (Eval('state') != 'draft')
                & ~Id('account', 'group_account_admin').in_(
                    Eval('context', {}).get('groups', []))),
            })
    validated_by = employee_field(
        "Validated By",
        states=['validated', 'posted', 'paid', 'cancelled'])
    posted_by = employee_field(
        "Posted By",
        states=['posted', 'paid', 'cancelled'])
    state = fields.Selection([
            ('draft', "Draft"),
            ('validated', "Validated"),
            ('posted', "Posted"),
            ('paid', "Paid"),
            ('cancelled', "Cancelled"),
            ], "State", readonly=True, sort=False)
    invoice_date = fields.Date('Invoice Date',
        states={
            'readonly': Eval('state').in_(['posted', 'paid', 'cancelled']),
            'required': Eval('state').in_(
                If(Eval('type') == 'in',
                    ['validated', 'posted', 'paid'],
                    ['posted', 'paid'])),
            })
    accounting_date = fields.Date('Accounting Date', states=_states)
    payment_term_date = fields.Date(
        "Payment Term Date", states=_states,
        help="The date from which the payment term is calculated.\n"
        "Leave empty to use the invoice date.")
    sequence = fields.Integer("Sequence", readonly=True)
    party = fields.Many2One(
        'party.party', 'Party', required=True, states=_states,
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    party_tax_identifier = fields.Many2One(
        'party.identifier', "Party Tax Identifier", ondelete='RESTRICT',
        states=_states)
    party_lang = fields.Function(fields.Char('Party Language'),
        'on_change_with_party_lang')
    invoice_address = fields.Many2One('party.address', 'Invoice Address',
        required=True, states=_states, domain=[('party', '=', Eval('party'))])
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states={
            'readonly': (
                _states['readonly']
                | (Eval('lines', [0]) & Eval('currency'))),
            })
    currency_date = fields.Function(fields.Date('Currency Date'),
        'on_change_with_currency_date')
    journal = fields.Many2One(
        'account.journal', 'Journal',
        states={
            'readonly': _states['readonly'],
            'required': Eval('state') != 'draft',
            },
        context={
            'company': Eval('company', -1),
            }, depends={'company'})
    move = fields.Many2One('account.move', 'Move', readonly=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ])
    additional_moves = fields.Many2Many(
        'account.invoice-additional-account.move', 'invoice', 'move',
        "Additional Moves", readonly=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        states={
            'invisible': ~Eval('additional_moves'),
            })
    cancel_move = fields.Many2One('account.move', 'Cancel Move', readonly=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        states={
            'invisible': ~Eval('cancel_move'),
            })
    account = fields.Many2One('account.account', 'Account', required=True,
        states=_states,
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
    payment_term = fields.Many2One(
        'account.invoice.payment_term', "Payment Term",
        ondelete='RESTRICT', states=_states)
    alternative_payees = fields.Many2Many(
        'account.invoice.alternative_payee', 'invoice', 'party',
        "Alternative Payee", states=_states,
        size=If(~Eval('move'), 1, None),
        context={
            'company': Eval('company', -1),
            },
        depends=['company'])
    lines = fields.One2Many('account.invoice.line', 'invoice', 'Lines',
        domain=[
            ('company', '=', Eval('company', -1)),
            ('currency', '=', Eval('currency', -1)),
            ['OR',
                ('account', '=', None),
                ('account', '!=', Eval('account', -1)),
                ],
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
                | ~Eval('currency')
                | ~Eval('account')),
            })
    taxes = fields.One2Many(
        'account.invoice.tax', 'invoice', 'Tax Lines',
        domain=[
            ('account', '!=', Eval('account', -1)),
            ],
        states={
            'readonly': (
                (Eval('state') != 'draft')
                | ~Eval('account')),
            })
    comment = fields.Text("Comment",
        states={
            'readonly': (
                (Eval('state') != 'draft')
                & ~Id('account', 'group_account_admin').in_(
                    Eval('context', {}).get('groups', []))),
            })
    origins = fields.Function(fields.Char('Origins'), 'get_origins')
    untaxed_amount = fields.Function(Monetary(
            "Untaxed", currency='currency', digits='currency'),
        'get_amount', searcher='search_untaxed_amount')
    untaxed_amount_cache = fields.Numeric(
        "Untaxed Cache", digits='currency', readonly=True)
    tax_amount = fields.Function(Monetary(
            "Tax", currency='currency', digits='currency'),
        'get_amount', searcher='search_tax_amount')
    tax_amount_cache = fields.Numeric(
        "Tax Cache", digits='currency', readonly=True)
    total_amount = fields.Function(Monetary(
            "Total", currency='currency', digits='currency'),
        'get_amount', searcher='search_total_amount')
    total_amount_cache = fields.Numeric(
        "Total Cache", digits='currency', readonly=True)
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
            ['OR',
                ('currency', '=', Eval('currency', -1)),
                ('second_currency', '=', Eval('currency', -1)),
                ],
            ['OR',
                ('party', 'in', [None, Eval('party', -1)]),
                ('party', 'in', Eval('alternative_payees', [])),
                ],
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
            })
    reconciliation_lines = fields.Function(fields.Many2Many(
            'account.move.line', None, None, "Payment Lines",
            states={
                'invisible': (
                    ~Eval('state').in_(['paid', 'cancelled'])
                    | ~Eval('reconciliation_lines')),
                }),
        'get_reconciliation_lines')
    amount_to_pay_today = fields.Function(Monetary(
            "Amount to Pay Today", currency='currency', digits='currency'),
        'get_amount_to_pay')
    amount_to_pay = fields.Function(Monetary(
            "Amount to Pay", currency='currency', digits='currency'),
        'get_amount_to_pay')
    invoice_report_revisions = fields.One2Many(
        'account.invoice.report.revision', 'invoice',
        "Invoice Report Revisions", readonly=True,
        states={
            'invisible': ~Eval('invoice_report_revisions'),
            })
    allow_cancel = fields.Function(
        fields.Boolean("Allow Cancel Invoice"), 'get_allow_cancel')
    has_payment_method = fields.Function(
        fields.Boolean("Has Payment Method"), 'get_has_payment_method')
    has_report_cache = fields.Function(
        fields.Boolean("Has Report Cached"), 'get_has_report_cache')

    del _states

    @classmethod
    def __setup__(cls):
        pool = Pool()
        Party = pool.get('party.party')
        cls.number.search_unaccented = False
        cls.reference.search_unaccented = False
        super(Invoice, cls).__setup__()
        t = cls.__table__()
        cls._sql_indexes.update({
                Index(t, (t.reference, Index.Similarity())),
                Index(
                    t,
                    (t.state, Index.Equality()),
                    where=t.state.in_(['draft', 'validated', 'posted'])),
                Index(t, (t.total_amount_cache, Index.Range())),
                Index(
                    t,
                    (t.total_amount_cache, Index.Equality()),
                    include=[t.id],
                    where=t.total_amount_cache == Null),
                Index(t, (t.untaxed_amount_cache, Index.Range())),
                Index(
                    t,
                    (t.untaxed_amount_cache, Index.Equality()),
                    include=[t.id],
                    where=t.untaxed_amount_cache == Null),
                Index(t, (t.tax_amount_cache, Index.Range())),
                Index(
                    t,
                    (t.tax_amount_cache, Index.Equality()),
                    include=[t.id],
                    where=t.tax_amount_cache == Null),
                })
        cls._check_modify_exclude = {
            'state', 'alternative_payees', 'payment_lines',
            'move', 'cancel_move', 'additional_moves', 'description',
            'invoice_report_cache', 'invoice_report_format', 'comment',
            'total_amount_cache', 'tax_amount_cache', 'untaxed_amount_cache',
            'lines', 'reference', 'invoice_report_cache_id',
            'invoice_report_revisions'}
        cls._order = [
            ('number', 'DESC NULLS FIRST'),
            ('id', 'DESC'),
            ]
        cls.journal.domain = [
            If(Eval('type') == 'out',
                ('type', 'in', cls._journal_types('out')),
                ('type', 'in', cls._journal_types('in'))),
            ]
        tax_identifier_types = Party.tax_identifier_types()
        cls.tax_identifier.domain = [
            ('party', '=', Eval('company_party', -1)),
            ('type', 'in', tax_identifier_types),
            ]
        cls.party_tax_identifier.domain = [
            ('party', '=', Eval('party', -1)),
            ('type', 'in', tax_identifier_types),
            ]
        cls._transitions |= set((
                ('draft', 'validated'),
                ('validated', 'posted'),
                ('draft', 'posted'),
                ('posted', 'posted'),
                ('posted', 'paid'),
                ('validated', 'draft'),
                ('paid', 'posted'),
                ('draft', 'cancelled'),
                ('validated', 'cancelled'),
                ('posted', 'cancelled'),
                ('cancelled', 'draft'),
                ('cancelled', 'posted'),
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
                    'invisible': (~Eval('state').in_(['draft', 'validated'])
                        | ((Eval('state') == 'posted') & Bool(Eval('move')))),
                    'depends': ['state', 'move'],
                    },
                'pay': {
                    'invisible': (
                        (Eval('state') != 'posted')
                        | ~Eval('has_payment_method', False)),
                    'depends': ['state', 'has_payment_method'],
                    },
                'reschedule_lines_to_pay': {
                    'invisible': (
                        ~Eval('lines_to_pay') | Eval('reconciled', False)),
                    'depends': ['lines_to_pay', 'reconciled'],
                    },
                'delegate_lines_to_pay': {
                    'invisible': (
                        ~Eval('lines_to_pay') | Eval('reconciled', False)),
                    'depends': ['lines_to_pay', 'reconciled'],
                    },
                'process': {
                    'invisible': ~Eval('state').in_(
                        ['posted', 'paid']),
                    'depends': ['state'],
                    },
                })
        cls.__rpc__.update({
                'post': RPC(
                    readonly=False, instantiate=0, fresh_session=True),
                })

    @classmethod
    def __register__(cls, module_name):
        sql_table = cls.__table__()

        super(Invoice, cls).__register__(module_name)
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        table = cls.__table_handler__(module_name)

        # Migration from 5.6: rename state cancel to cancelled
        cursor.execute(*sql_table.update(
                [sql_table.state], ['cancelled'],
                where=sql_table.state == 'cancel'))

        # Migration from 5.8: drop foreign key for sequence
        table.drop_fk('sequence')

        # Migration from 6.6: drop not null on journal
        table.not_null_action('journal', 'remove')

    @classmethod
    def order_number(cls, tables):
        table, _ = tables[None]
        return [CharLength(table.number), table.number]

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
    def default_company():
        return Transaction().context.get('company')

    @fields.depends('company')
    def on_change_with_company_party(self, name=None):
        return self.company.party if self.company else None

    @fields.depends(methods=['set_journal', 'on_change_party'])
    def on_change_type(self):
        self.set_journal()
        self.on_change_party()

    @classmethod
    def _journal_types(cls, invoice_type):
        if invoice_type == 'out':
            return ['revenue']
        else:
            return ['expense']

    @fields.depends('type')
    def set_journal(self, pattern=None):
        pool = Pool()
        Journal = pool.get('account.journal')
        pattern = pattern.copy() if pattern is not None else {}
        pattern.setdefault('type', {
                'out': 'revenue',
                'in': 'expense',
                }.get(self.type))
        self.journal = Journal.find(pattern)

    @classmethod
    def order_accounting_date(cls, tables):
        table, _ = tables[None]
        return [Coalesce(table.accounting_date, table.invoice_date)]

    @fields.depends('party', 'type', methods=['_update_account'])
    def on_change_party(self):
        self.invoice_address = None
        if self.party:
            self.invoice_address = self.party.address_get(type='invoice')
            self.party_tax_identifier = self.party.tax_identifier
            if self.type == 'out':
                self.account = self.party.account_receivable_used
                self.payment_term = self.party.customer_payment_term
            elif self.type == 'in':
                self.account = self.party.account_payable_used
                self.payment_term = self.party.supplier_payment_term
        else:
            self.payment_term = None
            self.account = None
        self._update_account()

    @fields.depends(methods=['_update_account'])
    def on_change_accounting_date(self):
        self._update_account()

    @fields.depends(methods=['_update_account'])
    def on_change_invoice_date(self):
        self._update_account()

    @fields.depends('account', 'accounting_date', 'invoice_date')
    def _update_account(self):
        "Update account to current account"
        if self.account:
            account = self.account.current(
                date=self.accounting_date or self.invoice_date)
            if account != self.account:
                self.account = account

    @fields.depends('invoice_date', 'company')
    def on_change_with_currency_date(self, name=None):
        Date = Pool().get('ir.date')
        if self.company:
            company_id = self.company.id
        else:
            company_id = Transaction().context.get('company')
        with Transaction().set_context(company=company_id):
            return self.invoice_date or Date.today()

    @fields.depends('party')
    def on_change_with_party_lang(self, name=None):
        Config = Pool().get('ir.configuration')
        if self.party and self.party.lang:
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

    @fields.depends(
        'lines', 'taxes', 'currency', methods=['_get_taxes', 'tax_date'])
    def _on_change_lines_taxes(self):
        pool = Pool()
        InvoiceTax = pool.get('account.invoice.tax')

        self.untaxed_amount = Decimal(0)
        self.tax_amount = Decimal(0)
        self.total_amount = Decimal(0)
        computed_taxes = {}

        if self.lines:
            for line in self.lines:
                if getattr(line, 'type', '') == 'line':
                    self.untaxed_amount += getattr(line, 'amount', 0) or 0
            computed_taxes = self._get_taxes()

        def is_zero(amount):
            if self.currency:
                return self.currency.is_zero(amount)
            else:
                return amount == Decimal(0)

        tax_keys = []
        taxes = list(self.taxes or [])
        for tax in (self.taxes or []):
            if tax.manual:
                self.tax_amount += tax.amount or Decimal(0)
                continue
            key = tax._key
            if (key not in computed_taxes) or (key in tax_keys):
                taxes.remove(tax)
                continue
            tax_keys.append(key)
            if not is_zero(computed_taxes[key]['base']
                    - (tax.base or Decimal(0))):
                self.tax_amount += computed_taxes[key]['amount']
                tax.amount = computed_taxes[key]['amount']
                tax.base = computed_taxes[key]['base']
            else:
                self.tax_amount += tax.amount or Decimal(0)
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
        cursor = Transaction().connection.cursor()

        untaxed_amount = {i.id: i.currency.round(Decimal(0)) for i in invoices}
        tax_amount = untaxed_amount.copy()
        total_amount = untaxed_amount.copy()

        invoices_no_cache = []
        for invoice in invoices:
            if (invoice.total_amount_cache is not None
                    and invoice.untaxed_amount_cache is not None
                    and invoice.tax_amount_cache is not None):
                total_amount[invoice.id] = invoice.total_amount_cache
                untaxed_amount[invoice.id] = invoice.untaxed_amount_cache
                tax_amount[invoice.id] = invoice.tax_amount_cache
            else:
                invoices_no_cache.append(invoice.id)
        invoices_no_cache = cls.browse(invoices_no_cache)

        type_name = cls.tax_amount._field.sql_type().base
        tax = InvoiceTax.__table__()
        to_round = False
        for sub_ids in grouped_slice(invoices_no_cache):
            red_sql = reduce_ids(tax.invoice, sub_ids)
            cursor.execute(*tax.select(tax.invoice,
                    Coalesce(Sum(tax.amount), 0).as_(type_name),
                    where=red_sql,
                    group_by=tax.invoice))
            for invoice_id, sum_ in cursor:
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

        for invoice in invoices_no_cache:
            zero = invoice.currency.round(Decimal(0))
            untaxed_amount[invoice.id] = sum(
                (line.amount for line in invoice.lines
                    if line.type == 'line'), zero)
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
        AdditionalMove = pool.get('account.invoice-additional-account.move')
        line = MoveLine.__table__()
        invoice = cls.__table__()
        additional_move = AdditionalMove.__table__()
        cursor = Transaction().connection.cursor()

        lines = defaultdict(list)
        for sub_ids in grouped_slice(invoices):
            red_sql = reduce_ids(invoice.id, sub_ids)
            query = (invoice
                .join(line,
                    condition=((invoice.move == line.move)
                        & (invoice.account == line.account)))
                .select(
                    invoice.id.as_('invoice'),
                    line.id.as_('line'),
                    line.maturity_date.as_('maturity_date'),
                    where=red_sql))
            query |= (invoice
                .join(additional_move,
                    condition=additional_move.invoice == invoice.id)
                .join(line,
                    condition=((additional_move.move == line.move)
                        & (invoice.account == line.account)))
                .select(
                    invoice.id.as_('invoice'),
                    line.id.as_('line'),
                    line.maturity_date.as_('maturity_date'),
                    where=red_sql))
            cursor.execute(*query.select(
                    query.invoice, query.line,
                    order_by=query.maturity_date.nulls_last))
            for invoice_id, line_id in cursor:
                lines[invoice_id].append(line_id)
        return lines

    def get_reconciliation_lines(self, name):
        if not self.move:
            return
        lines = set()
        for move in chain([self.move], self.additional_moves):
            for line in move.lines:
                if line.account == self.account and line.reconciliation:
                    for line in line.reconciliation.lines:
                        if line not in self.lines_to_pay:
                            lines.add(line)
        return [l.id for l in sorted(lines, key=lambda l: l.date)]

    @classmethod
    def get_amount_to_pay(cls, invoices, name):
        pool = Pool()
        Currency = pool.get('currency.currency')
        Date = pool.get('ir.date')

        res = dict((x.id, Decimal(0)) for x in invoices)
        for company, grouped_invoices in groupby(
                invoices, key=lambda i: i.company):
            with Transaction().set_context(company=company.id):
                today = Date.today()
            for invoice in grouped_invoices:
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
        if value is not None and backend.name == 'sqlite':
            value = float(value)

        union = (line.join(invoice, condition=(invoice.id == line.invoice)
                ).join(currency, condition=(currency.id == invoice.currency)
                ).select(line.invoice.as_('invoice'),
                Coalesce(Sum(Round((line.quantity * line.unit_price).cast(
                                type_name),
                                currency.digits)), 0).as_('total_amount'),
                where=(line.invoice.in_(invoice_query)
                    & (invoice.total_amount_cache == Null)),
                group_by=line.invoice)
            | tax.select(tax.invoice.as_('invoice'),
                Coalesce(Sum(tax.amount), 0).as_('total_amount'),
                where=(tax.invoice.in_(invoice_query)
                    & Exists(invoice.select(
                            invoice.id,
                            where=(invoice.total_amount_cache == Null)
                            & (invoice.id == tax.invoice)))),
                group_by=tax.invoice))
        union |= invoice.select(
            invoice.id.as_('invoice'),
            invoice.total_amount_cache.as_('total_amount'),
            where=(invoice.id.in_(invoice_query)
                & (invoice.total_amount_cache != Null)
                & Operator(invoice.total_amount_cache.cast(type_name), value)))
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
        if value is not None and backend.name == 'sqlite':
            value = float(value)

        query = line.join(invoice,
            condition=(invoice.id == line.invoice)
            ).join(currency,
                condition=(currency.id == invoice.currency)
                ).select(line.invoice,
                    where=(line.invoice.in_(invoice_query)
                        & (invoice.untaxed_amount_cache == Null)),
                    group_by=line.invoice,
                    having=Operator(Coalesce(Sum(
                                Round((line.quantity * line.unit_price).cast(
                                        type_name),
                                    currency.digits)), 0).cast(type_name),
                        value))
        query |= invoice.select(invoice.id,
            where=invoice.id.in_(invoice_query)
            & (invoice.untaxed_amount_cache != Null)
            & Operator(invoice.untaxed_amount_cache.cast(type_name), value))
        return [('id', 'in', query)]

    @classmethod
    def search_tax_amount(cls, name, clause):
        pool = Pool()
        Rule = pool.get('ir.rule')
        Tax = pool.get('account.invoice.tax')
        Invoice = pool.get('account.invoice')
        type_name = cls.tax_amount._field.sql_type().base
        tax = Tax.__table__()
        invoice = Invoice.__table__()

        _, operator, value = clause
        invoice_query = Rule.query_get('account.invoice')
        Operator = fields.SQL_OPERATORS[operator]
        # SQLite uses float for sum
        if value is not None and backend.name == 'sqlite':
            value = float(value)

        query = tax.select(tax.invoice,
            where=(tax.invoice.in_(invoice_query)
                & Exists(invoice.select(
                        invoice.id,
                        where=(invoice.tax_amount_cache == Null)
                        & (invoice.id == tax.invoice)))),
            group_by=tax.invoice,
            having=Operator(Coalesce(Sum(tax.amount), 0).cast(type_name),
                value))
        query |= invoice.select(invoice.id,
            where=invoice.id.in_(invoice_query)
            & (invoice.tax_amount_cache != Null)
            & Operator(invoice.tax_amount_cache.cast(type_name), value))
        return [('id', 'in', query)]

    def get_allow_cancel(self, name):
        if self.state in {'draft', 'validated'}:
            return True
        if self.state == 'posted':
            return self.type == 'in' or self.company.cancel_invoice_out
        return False

    @classmethod
    def get_has_payment_method(cls, invoices, name):
        pool = Pool()
        Method = pool.get('account.invoice.payment.method')
        methods = {}
        for (company, account), sub_invoices in groupby(
                invoices, key=lambda i: (i.company, i.account)):
            sub_invoice_ids = [i.id for i in sub_invoices]
            value = bool(Method.search([
                        ('company', '=', company.id),
                        ('debit_account', '!=', account.id),
                        ('credit_account', '!=', account.id),
                        ], limit=1))
            methods.update(dict.fromkeys(sub_invoice_ids, value))
        return methods

    @classmethod
    def get_has_report_cache(cls, invoices, name):
        table = cls.__table__()
        cursor = Transaction().connection.cursor()

        result = {}
        has_cache = (
            (table.invoice_report_cache_id != Null)
            | (table.invoice_report_cache != Null))
        for sub_invoices in grouped_slice(invoices):
            sub_ids = map(int, sub_invoices)
            cursor.execute(*table.select(table.id, has_cache,
                    where=reduce_ids(table.id, sub_ids)))
            result.update(cursor)
        return result

    @property
    def taxable_lines(self):
        taxable_lines = []
        for line in self.lines:
            if getattr(line, 'type', None) == 'line':
                taxable_lines.extend(line.taxable_lines)
        return taxable_lines

    @property
    @fields.depends('accounting_date', 'invoice_date', 'company')
    def tax_date(self):
        pool = Pool()
        Date = pool.get('ir.date')
        context = Transaction().context
        with Transaction().set_context(
                company=self.company.id if self.company
                else context.get('company')):
            today = Date.today()
        return self.accounting_date or self.invoice_date or today

    @fields.depends('party', 'company')
    def _get_tax_context(self):
        context = {}
        if self.party and self.party.lang:
            context['language'] = self.party.lang.code
        if self.company:
            context['company'] = self.company.id
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
            if self.alternative_payees:
                line.party, = self.alternative_payees
            else:
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
        Warning = pool.get('res.user.warning')
        Lang = pool.get('ir.lang')

        if self.move:
            return self.move
        with Transaction().set_context(company=self.company.id):
            today = Date.today()
        self.update_taxes(exception=True)
        move_lines = []
        for line in self.lines:
            move_lines += line.get_move_lines()
        for tax in self.taxes:
            move_lines += tax.get_move_lines()

        total = sum(l.debit - l.credit for l in move_lines)
        if self.payment_term:
            payment_date = self.payment_term_date or self.invoice_date or today
            term_lines = self.payment_term.compute(
                total, self.company.currency, payment_date)
        else:
            term_lines = [(self.payment_term_date or today, total)]
        if self.currency != self.company.currency:
            remainder_total_currency = self.total_amount.copy_sign(total)
        else:
            remainder_total_currency = 0
        past_payment_term_dates = []
        for date, amount in term_lines:
            line = self._get_move_line(date, amount)
            if line.amount_second_currency:
                remainder_total_currency += line.amount_second_currency
            move_lines.append(line)
            if self.type == 'out' and date < today:
                past_payment_term_dates.append(date)
        if any(past_payment_term_dates):
            lang = Lang.get()
            warning_key = Warning.format('invoice_payment_term', [self])
            if Warning.check(warning_key):
                raise InvoicePaymentTermDateWarning(warning_key,
                    gettext('account_invoice'
                        '.msg_invoice_payment_term_date_past',
                        invoice=self.rec_name,
                        date=lang.strftime(min(past_payment_term_dates))))
        if not self.currency.is_zero(remainder_total_currency):
            move_lines[-1].amount_second_currency -= \
                remainder_total_currency

        accounting_date = self.accounting_date or self.invoice_date or today
        period = Period.find(self.company, date=accounting_date)

        move = Move()
        move.journal = self.journal
        move.period = period
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
        Sequence = pool.get('ir.sequence.strict')

        sequences = set()

        for company, grouped_invoices in groupby(
                invoices, key=lambda i: i.company):
            with Transaction().set_context(company=company.id):
                today = Date.today()

            def invoice_date(invoice):
                return invoice.invoice_date or today

            grouped_invoices = sorted(grouped_invoices, key=invoice_date)

            for invoice in grouped_invoices:
                # Posted, paid and cancelled invoices are tested by
                # check_modify so we can not modify tax_identifier nor number
                if invoice.state in {'posted', 'paid', 'cancelled'}:
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
                    date = invoice_date(invoice)
                    # Do not need to lock the table
                    # because sequence.get_id is sequential
                    after_invoices = cls.search([
                            ('sequence', '=', invoice.sequence),
                            ('invoice_date', '>', date),
                            ],
                        limit=1, order=[('invoice_date', 'DESC')])
                    if after_invoices:
                        after_invoice, = after_invoices
                        raise InvoiceNumberError(
                            gettext('account_invoice.msg_invoice_number_after',
                                invoice=invoice.rec_name,
                                sequence=Sequence(invoice.sequence).rec_name,
                                date=Lang.get().strftime(date),
                                after_invoice=after_invoice.rec_name))
                    sequences.add(invoice.sequence)
        cls.save(invoices)

    def get_next_number(self, pattern=None):
        "Return invoice number and sequence id used"
        pool = Pool()
        Period = pool.get('account.period')

        if pattern is None:
            pattern = {}
        else:
            pattern = pattern.copy()

        accounting_date = self.accounting_date or self.invoice_date
        period = Period.find(
            self.company, date=accounting_date,
            test_state=self.type != 'in')

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
        with Transaction().set_context(
                date=accounting_date,
                company=self.company.id):
            return sequence.get(), sequence.id

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

    def get_tax_identifier(self):
        "Return the default computed tax identifier"
        return self.company.party.tax_identifier

    @property
    def invoice_report_versioned(self):
        return self.state in {'posted', 'paid'} and self.type == 'out'

    def create_invoice_report_revision(self):
        pool = Pool()
        InvoiceReportRevision = pool.get('account.invoice.report.revision')
        if not self.invoice_report_versioned:
            return
        invoice_report_revision = InvoiceReportRevision(
            invoice=self,
            invoice_report_cache=self.invoice_report_cache,
            invoice_report_cache_id=self.invoice_report_cache_id,
            invoice_report_format=self.invoice_report_format)
        self.invoice_report_revisions += (invoice_report_revision,)
        self.invoice_report_cache = None
        self.invoice_report_cache_id = None
        self.invoice_report_format = None
        return invoice_report_revision

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
        _, operator, value = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('number', *clause[1:]),
            ('reference', *clause[1:]),
            ]

    def get_origins(self, name):
        return ', '.join(set(filter(None,
                    (l.origin_name for l in self.lines))))

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
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
    def create(cls, vlist):
        invoices = super().create(vlist)
        cls.update_taxes(invoices)
        return invoices

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        all_invoices = []
        for invoices, values in zip(actions, actions):
            if set(values) - cls._check_modify_exclude:
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

        alternative_payees2copy = set()
        for invoice in invoices:
            if len(invoice.alternative_payees) == 1:
                parties = {l.party for l in invoice.lines_to_pay}
                if parties <= set(invoice.alternative_payees):
                    alternative_payees2copy.add(invoice.id)

        def copy_alternative_payees(data):
            if data['id'] in alternative_payees2copy:
                return data.get('alternative_payees', [])
            else:
                return []

        default.setdefault('number', None)
        default.setdefault('sequence')
        default.setdefault('move', None)
        default.setdefault('additional_moves', None)
        default.setdefault('cancel_move', None)
        default.setdefault('invoice_report_cache', None)
        default.setdefault('invoice_report_cache_id', None)
        default.setdefault('invoice_report_format', None)
        default.setdefault('alternative_payees', copy_alternative_payees)
        default.setdefault('payment_lines', None)
        default.setdefault('invoice_date', None)
        default.setdefault('accounting_date', None)
        default.setdefault('payment_term_date', None)
        default.setdefault('total_amount_cache', None)
        default.setdefault('untaxed_amount_cache', None)
        default.setdefault('tax_amount_cache', None)
        default.setdefault('validated_by')
        default.setdefault('posted_by')
        default.setdefault('invoice_report_revisions', None)
        return super(Invoice, cls).copy(invoices, default=default)

    @classmethod
    def validate(cls, invoices):
        super(Invoice, cls).validate(invoices)
        for invoice in invoices:
            invoice.check_payment_lines()

    def check_payment_lines(self):
        def balance(line):
            if self.currency == line.second_currency:
                return line.amount_second_currency
            elif self.currency == self.company.currency:
                return line.debit - line.credit
            else:
                return 0
        amount = sum(map(balance, self.lines_to_pay))
        payment_amount = sum(map(balance, self.payment_lines))
        if abs(amount) < abs(payment_amount):
            raise InvoiceValidationError(
                gettext('account_invoice'
                    '.msg_invoice_payment_lines_greater_amount',
                    invoice=self.rec_name))

    def get_reconcile_lines_for_amount(self, amount, currency, party=None):
        '''
        Return list of lines and the remainder to make reconciliation.
        '''
        Result = namedtuple('Result', ['lines', 'remainder'])

        if party is None:
            party = self.party

        assert currency in [self.currency, self.company.currency]

        def balance(line):
            if currency == line.second_currency:
                return line.amount_second_currency
            elif currency == self.company.currency:
                return line.debit - line.credit
            else:
                return 0

        lines = [
            l for l in self.payment_lines + self.lines_to_pay
            if not l.reconciliation
            and (not self.account.party_required or l.party == party)]

        remainder = sum(map(balance, lines)) - amount
        best = Result(lines, remainder)
        if remainder:
            for n in range(len(lines) - 1, 0, -1):
                for comb_lines in combinations(lines, n):
                    remainder = sum(map(balance, comb_lines)) - amount
                    result = Result(list(comb_lines), remainder)
                    if currency.is_zero(remainder):
                        return result
                    if abs(remainder) < abs(best.remainder):
                        best = result
        return best

    def pay_invoice(
            self, amount, payment_method, date, description=None,
            overpayment=0, party=None):
        '''
        Adds a payment of amount to an invoice using the journal, date and
        description.
        If overpayment is set, then only the amount minus the overpayment is
        used to pay off the invoice.
        Returns the payment lines.
        '''
        pool = Pool()
        Currency = pool.get('currency.currency')
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Period = pool.get('account.period')

        if party is None:
            party = self.party

        pay_line = Line(account=self.account)
        counterpart_line = Line()
        lines = [pay_line, counterpart_line]

        pay_amount = amount - overpayment
        if self.currency != self.company.currency:
            amount_second_currency = pay_amount
            second_currency = self.currency
            overpayment_second_currency = overpayment
            with Transaction().set_context(date=date):
                amount = Currency.compute(
                    self.currency, amount, self.company.currency)
                overpayment = Currency.compute(
                    self.currency, overpayment, self.company.currency)
                pay_amount = amount - overpayment
        else:
            amount_second_currency = None
            second_currency = None
            overpayment_second_currency = None
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
        if amount_second_currency is not None:
            pay_line.amount_second_currency = (
                amount_second_currency.copy_sign(
                    pay_line.debit - pay_line.credit))
            pay_line.second_currency = second_currency

        if overpayment:
            overpayment_line = Line(account=self.account)
            lines.insert(1, overpayment_line)
            overpayment_line.debit = (
                abs(overpayment) if pay_line.debit else 0)
            overpayment_line.credit = (
                abs(overpayment) if pay_line.credit else 0)
            if overpayment_second_currency is not None:
                overpayment_line.amount_second_currency = (
                    overpayment_second_currency.copy_sign(
                        overpayment_line.debit - overpayment_line.credit))
                overpayment_line.second_currency = second_currency

        counterpart_line.debit = abs(amount) if pay_line.credit else 0
        counterpart_line.credit = abs(amount) if pay_line.debit else 0
        if counterpart_line.debit:
            payment_acccount = 'debit_account'
        else:
            payment_acccount = 'credit_account'
        counterpart_line.account = getattr(
            payment_method, payment_acccount).current(date=date)
        if amount_second_currency is not None:
            counterpart_line.amount_second_currency = (
                amount_second_currency.copy_sign(
                    counterpart_line.debit - counterpart_line.credit))
            counterpart_line.second_currency = second_currency

        for line in lines:
            if line.account.party_required:
                line.party = party

        period = Period.find(self.company, date=date)

        move = Move(
            journal=payment_method.journal, period=period, date=date,
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

    @dualmethod
    def print_invoice(cls, invoices):
        '''
        Generate invoice report and store it in invoice_report field.
        '''
        InvoiceReport = Pool().get('account.invoice', type='report')
        for invoice in invoices:
            if not invoice.invoice_report_cache:
                InvoiceReport.execute([invoice.id], {})

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
    def _store_cache(cls, invoices):
        for invoice in invoices:
            if (invoice.untaxed_amount == invoice.untaxed_amount_cache
                    and invoice.tax_amount == invoice.tax_amount_cache
                    and invoice.total_amount == invoice.total_amount_cache):
                continue
            invoice.untaxed_amount_cache = invoice.untaxed_amount
            invoice.tax_amount_cache = invoice.tax_amount
            invoice.total_amount_cache = invoice.total_amount
        cls.save(invoices)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    @reset_employee('validated_by', 'posted_by')
    def draft(cls, invoices):
        Move = Pool().get('account.move')

        cls.write(invoices, {
                'tax_amount_cache': None,
                'untaxed_amount_cache': None,
                'total_amount_cache': None,
                })
        moves = []
        for invoice in invoices:
            if invoice.move:
                moves.append(invoice.move)
            if invoice.additional_moves:
                moves.extend(invoice.additional_moves)
            if len(invoice.alternative_payees) > 1:
                invoice.alternative_payees = []
        cls.save(invoices)
        if moves:
            Move.delete(moves)

    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    @set_employee('validated_by')
    def validate_invoice(cls, invoices):
        pool = Pool()
        Move = pool.get('account.move')

        invoices_in = cls.browse([i for i in invoices if i.type == 'in'])
        cls.set_number(invoices_in)
        cls._store_cache(invoices)
        cls._check_similar(invoices)
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
    @Workflow.transition('posted')
    def post_batch(cls, invoices):
        pool = Pool()
        Date = pool.get('ir.date')
        transaction = Transaction()
        context = transaction.context
        cls.set_number(invoices)
        for company, grouped_invoices in groupby(
                invoices, key=lambda i: i.company):
            with Transaction().set_context(company=company.id):
                today = Date.today()
            for invoice in grouped_invoices:
                if not invoice.payment_term_date:
                    invoice.payment_term_date = today
        cls.save(invoices)
        with transaction.set_context(
                _skip_warnings=True,
                queue_batch=context.get('queue_batch', True)):
            cls.__queue__._post(invoices)

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    @set_employee('posted_by', when='before')
    def post(cls, invoices):
        pool = Pool()
        Date = pool.get('ir.date')
        Warning = pool.get('res.user.warning')
        for company, grouped_invoices in groupby(
                invoices, key=lambda i: i.company):
            with Transaction().set_context(company=company.id):
                today = Date.today()
            future_invoices = [
                i for i in grouped_invoices
                if i.type == 'out'
                and i.invoice_date and i.invoice_date > today]
            if future_invoices:
                names = ', '.join(m.rec_name for m in future_invoices[:5])
                if len(future_invoices) > 5:
                    names += '...'
                warning_key = Warning.format(
                    'invoice_date_future', future_invoices)
                if Warning.check(warning_key):
                    raise InvoiceFutureWarning(warning_key,
                        gettext('account_invoice.msg_invoice_date_future',
                            invoices=names))
        cls._check_similar([i for i in invoices if i.state != 'validated'])
        cls._post(invoices)

    @classmethod
    def _post(cls, invoices):
        pool = Pool()
        Move = pool.get('account.move')
        transaction = Transaction()
        context = transaction.context

        cls.set_number(invoices)
        cls._store_cache(invoices)
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
        to_print = []
        for invoice in invoices:
            if invoice.type == 'out':
                to_print.append(invoice)
            if invoice.reconciled:
                reconciled.append(invoice)
        if to_print:
            cls.__queue__.print_invoice(to_print)
        if reconciled:
            with transaction.set_context(
                    queue_batch=context.get('queue_batch', True)):
                cls.__queue__.process(reconciled)

    @classmethod
    def _check_similar(cls, invoices, type='in'):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        for sub_invoices in grouped_slice(invoices):
            sub_invoices = list(sub_invoices)
            domain = list(filter(None,
                        (i._similar_domain() for i in sub_invoices
                        if i.type == type)))
            if not domain:
                continue
            if cls.search(['OR'] + domain, order=[]):
                for invoice in sub_invoices:
                    domain = invoice._similar_domain()
                    if not domain:
                        continue
                    try:
                        similar, = cls.search(domain, limit=1)
                    except ValueError:
                        continue
                    warning_key = Warning.format(
                        'invoice_similar', [invoice])
                    if Warning.check(warning_key):
                        raise InvoiceSimilarWarning(warning_key,
                            gettext('account_invoice.msg_invoice_similar',
                                similar=similar.rec_name,
                                invoice=invoice.rec_name))

    def _similar_domain(self, delay=None):
        pool = Pool()
        Date = pool.get('ir.date')
        if not self.reference:
            return
        with Transaction().set_context(company=self.company.id):
            invoice_date = self.invoice_date or Date.today()
        if delay is None:
            delay = dt.timedelta(days=60)
        return [
            ('company', '=', self.company.id),
            ('type', '=', self.type),
            ('party', '=', self.party.id),
            ('reference', '=', self.reference),
            ('id', '!=', self.id),
            ['OR',
                ('invoice_date', '=', None),
                [
                    ('invoice_date', '>=', invoice_date - delay),
                    ('invoice_date', '<=', invoice_date + delay),
                    ],
                ],
            ]

    @classmethod
    @ModelView.button_action('account_invoice.wizard_pay')
    def pay(cls, invoices):
        pass

    @classmethod
    @ModelView.button_action(
        'account_invoice.act_reschedule_lines_to_pay_wizard')
    def reschedule_lines_to_pay(cls, invoices):
        pass

    @classmethod
    @ModelView.button_action(
        'account_invoice.act_delegate_lines_to_pay_wizard')
    def delegate_lines_to_pay(cls, invoices):
        pass

    @classmethod
    @ModelView.button
    def process(cls, invoices):
        to_save = []
        paid = []
        posted = []
        for invoice in invoices:
            if invoice.state in {'posted', 'paid'}:
                if invoice.reconciled:
                    paid.append(invoice)
                else:
                    posted.append(invoice)
            elif invoice.state == 'cancelled' and invoice.move:
                if not invoice.reconciled:
                    if invoice.cancel_move:
                        invoice.cancel_move = None
                        invoice.save()
                        to_save.append(invoice)
                    posted.append(invoice)
        cls.save(to_save)
        cls.paid(paid)
        cls._post(posted)

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
            if invoice.move or invoice.number:
                if invoice.move and invoice.move.state == 'draft':
                    delete_moves.append(invoice.move)
                    delete_moves.extend(invoice.additional_moves)
                elif not invoice.cancel_move:
                    if (invoice.type == 'out'
                            and not invoice.company.cancel_invoice_out):
                        raise AccessError(
                            gettext('account_invoice'
                                '.msg_invoice_customer_cancel_move',
                                invoice=invoice.rec_name))
                    if invoice.move:
                        invoice.cancel_move = invoice.move.cancel()
                        additional_cancel_moves = [
                            m.cancel() for m in invoice.additional_moves]
                        invoice.additional_moves += tuple(
                            additional_cancel_moves)
                        to_save.append(invoice)
                        cancel_moves.append(invoice.cancel_move)
                        cancel_moves.extend(additional_cancel_moves)
        if cancel_moves:
            Move.save(cancel_moves)
        cls._store_cache(invoices)
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
            for move in chain(
                    [invoice.move, invoice.cancel_move],
                    invoice.additional_moves):
                for line in move.lines:
                    if (not line.reconciliation
                            and line.account == invoice.account):
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


class InvoiceAdditionalMove(ModelSQL):
    "Invoice Additional Move"
    __name__ = 'account.invoice-additional-account.move'
    invoice = fields.Many2One(
        'account.invoice', "Invoice", ondelete='CASCADE', required=True)
    move = fields.Many2One(
        'account.move', "Additional Move", ondelete='CASCADE')


class AlternativePayee(ModelSQL):
    "Invoice Alternative Payee"
    __name__ = 'account.invoice.alternative_payee'

    invoice = fields.Many2One(
        'account.invoice', "Invoice", ondelete='CASCADE', required=True)
    party = fields.Many2One(
        'party.party', "Payee", ondelete='RESTRICT', required=True)


class InvoicePaymentLine(ModelSQL):
    'Invoice - Payment Line'
    __name__ = 'account.invoice-account.move.line'
    invoice = fields.Many2One(
        'account.invoice', "Invoice", ondelete='CASCADE', required=True)
    invoice_account = fields.Function(
        fields.Many2One('account.account', "Invoice Account"),
        'get_invoice')
    invoice_party = fields.Function(
        fields.Many2One('party.party', "Invoice Party"), 'get_invoice')
    invoice_alternative_payees = fields.Function(
        fields.Many2Many(
            'party.party', None, None, "Invoice Alternative Payees"),
        'get_invoice')
    line = fields.Many2One(
        'account.move.line', "Payment Line", ondelete='CASCADE', required=True,
        domain=[
            ('account', '=', Eval('invoice_account')),
            ['OR',
                ('party', '=', Eval('invoice_party', -1)),
                ('party', 'in', Eval('invoice_alternative_payees', [])),
                ],
            ])

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
        invoice_alternative_payees = 'invoice_alternative_payees' in result
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
            if invoice_alternative_payees:
                result['invoice_alternative_payees'][record.id] = [
                    p.id for p in record.invoice.alternative_payees]
        return result


class InvoiceLine(sequence_ordered(), ModelSQL, ModelView, TaxableMixin):
    'Invoice Line'
    __name__ = 'account.invoice.line'
    _states = {
        'readonly': Eval('invoice_state') != 'draft',
        }

    invoice = fields.Many2One(
        'account.invoice', "Invoice", ondelete='CASCADE',
        states={
            'required': (~Eval('invoice_type') & Eval('party')
                & Eval('currency') & Eval('company')),
            'invisible': Bool(Eval('context', {}).get('standalone')),
            'readonly': _states['readonly'] & Bool(Eval('invoice')),
            })
    invoice_party = fields.Function(
        fields.Many2One(
            'party.party', "Party",
            context={
                'company': Eval('company', -1),
                },
            depends=['company']),
        'on_change_with_invoice_party', searcher='search_invoice_party')
    invoice_description = fields.Function(
        fields.Char("Invoice Description"),
        'on_change_with_invoice_description',
        searcher='search_invoice_description')
    invoice_state = fields.Function(
        fields.Selection('get_invoice_states', "Invoice State"),
        'on_change_with_invoice_state')
    invoice_type = fields.Selection(
        'get_invoice_types', "Invoice Type",
        states={
            'readonly': Eval('context', {}).get('type') | Eval('type'),
            'required': ~Eval('invoice'),
            })
    party = fields.Many2One(
        'party.party', "Party",
        states={
            'required': ~Eval('invoice'),
            'readonly': _states['readonly'],
            },
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    party_lang = fields.Function(fields.Char('Party Language'),
        'on_change_with_party_lang')
    currency = fields.Many2One(
        'currency.currency', "Currency", required=True,
        states=_states)
    company = fields.Many2One(
        'company.company', "Company", required=True,
        states=_states)
    type = fields.Selection([
        ('line', 'Line'),
        ('subtotal', 'Subtotal'),
        ('title', 'Title'),
        ('comment', 'Comment'),
        ], "Type", required=True,
        states={
            'invisible': Bool(Eval('context', {}).get('standalone')),
            'readonly': _states['readonly'],
            })
    quantity = fields.Float(
        "Quantity", digits='unit',
        states={
            'invisible': Eval('type') != 'line',
            'required': Eval('type') == 'line',
            'readonly': _states['readonly'],
            })
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
            ])
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
        depends={'company'})
    product_uom_category = fields.Function(
        fields.Many2One(
            'product.uom.category', "Product UoM Category",
            help="The category of Unit of Measure for the product."),
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
        depends={'invoice'})
    unit_price = Monetary(
        "Unit Price", currency='currency', digits=price_digits,
        states={
            'invisible': Eval('type') != 'line',
            'required': Eval('type') == 'line',
            'readonly': _states['readonly'],
            })
    amount = fields.Function(Monetary(
            "Amount", currency='currency', digits='currency',
            states={
                'invisible': ~Eval('type').in_(['line', 'subtotal']),
                }),
        'get_amount')
    description = fields.Text('Description', size=None, states=_states)
    summary = fields.Function(fields.Char('Summary'), 'on_change_with_summary')
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
        depends={'invoice'})
    taxes_deductible_rate = fields.Numeric(
        "Taxes Deductible Rate", digits=(14, 10),
        domain=[
            ('taxes_deductible_rate', '>=', 0),
            ('taxes_deductible_rate', '<=', 1),
            ],
        states={
            'invisible': (
                (Eval('invoice_type') != 'in')
                | (Eval('type') != 'line')),
            })
    taxes_date = fields.Date(
        "Taxes Date",
        states={
            'invisible': Eval('type') != 'line',
            'readonly': _states['readonly'],
            },
        help="The date at which the taxes are computed.\n"
        "Leave empty for the accounting date.")
    invoice_taxes = fields.Function(fields.Many2Many('account.invoice.tax',
        None, None, 'Invoice Taxes'), 'get_invoice_taxes')
    origin = fields.Reference("Origin", selection='get_origin', states=_states)

    del _states

    @classmethod
    def __setup__(cls):
        super(InvoiceLine, cls).__setup__()
        cls._check_modify_exclude = {'note', 'origin'}

        # Set account domain dynamically for kind
        cls.account.domain = [
            ('closed', '!=', True),
            ('company', '=', Eval('company', -1)),
            ('id', '!=', Eval('_parent_invoice', {}).get('account', -1)),
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
        cls.sequence.states.update({
                'invisible': Bool(Eval('context', {}).get('standalone')),
                })

    @staticmethod
    def _account_domain(type_):
        if type_ == 'out':
            return ['OR', ('type.revenue', '=', True)]
        elif type_ == 'in':
            return ['OR',
                ('type.expense', '=', True),
                ('type.debt', '=', True),
                ]

    @classmethod
    def __register__(cls, module_name):
        super(InvoiceLine, cls).__register__(module_name)
        table = cls.__table_handler__(module_name)
        # Migration from 5.0: remove check constraints
        table.drop_constraint('type_account')
        table.drop_constraint('type_invoice')

    @classmethod
    def get_invoice_types(cls):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        return Invoice.fields_get(['type'])['type']['selection'] + [(None, '')]

    @fields.depends(
        'invoice', '_parent_invoice.currency', '_parent_invoice.company',
        '_parent_invoice.type',
        methods=['on_change_company'])
    def on_change_invoice(self):
        if self.invoice:
            self.currency = self.invoice.currency
            self.company = self.invoice.company
            self.on_change_company()
            self.invoice_type = self.invoice.type

    @fields.depends('company', 'invoice',
        '_parent_invoice.type', 'invoice_type')
    def on_change_company(self):
        invoice_type = self.invoice.type if self.invoice else self.invoice_type
        if (invoice_type == 'in'
                and self.company
                and self.company.purchase_taxes_expense):
            self.taxes_deductible_rate = 0

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = Company(Transaction().context['company'])
            return company.currency.id

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_type():
        return 'line'

    @fields.depends('party', 'invoice', '_parent_invoice.party')
    def on_change_with_invoice_party(self, name=None):
        if self.invoice and self.invoice.party:
            return self.invoice.party
        elif self.party:
            return self.party

    @classmethod
    def search_invoice_party(cls, name, clause):
        nested = clause[0][len(name) + 1:]
        return ['OR',
            ('invoice.party' + nested, *clause[1:]),
            ('party' + nested, *clause[1:]),
            ]

    @fields.depends('invoice', '_parent_invoice.description')
    def on_change_with_invoice_description(self, name=None):
        if self.invoice:
            return self.invoice.description

    @classmethod
    def search_invoice_description(cls, name, clause):
        return [('invoice.description', *clause[1:])]

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
            state = self.invoice.state
            if state == 'cancelled' and self.invoice.cancel_move:
                state = 'paid'
        else:
            state = 'draft'
        return state

    @fields.depends('invoice', '_parent_invoice.party', 'party')
    def on_change_with_party_lang(self, name=None):
        Config = Pool().get('ir.configuration')
        if self.invoice and self.invoice.party:
            party = self.invoice.party
        else:
            party = self.party
        if party and party.lang:
            return party.lang.code
        return Config.get_language()

    @fields.depends('description')
    def on_change_with_summary(self, name=None):
        return firstline(self.description or '')

    @fields.depends(
        'type', 'quantity', 'unit_price', 'taxes_deductible_rate', 'invoice',
        '_parent_invoice.currency', 'currency', 'taxes',
        '_parent_invoice.type', 'invoice_type',
        methods=['_get_taxes'])
    def on_change_with_amount(self):
        if self.type == 'line':
            currency = (self.invoice.currency if self.invoice
                else self.currency)
            amount = (Decimal(str(self.quantity or 0))
                * (self.unit_price or Decimal(0)))
            invoice_type = (
                self.invoice.type if self.invoice else self.invoice_type)
            if (invoice_type == 'in'
                    and self.taxes_deductible_rate is not None
                    and self.taxes_deductible_rate != 1):
                with Transaction().set_context(_deductible_rate=1):
                    tax_amount = sum(
                        t['amount'] for t in self._get_taxes().values())
                non_deductible_amount = (
                    tax_amount * (1 - self.taxes_deductible_rate))
                amount += non_deductible_amount
            if currency:
                return currency.round(amount)
            return amount
        return Decimal(0)

    def get_amount(self, name):
        if self.type == 'line':
            return self.on_change_with_amount()
        elif self.type == 'subtotal':
            subtotal = Decimal(0)
            for line2 in self.invoice.lines:
                if line2.type == 'line':
                    subtotal += line2.on_change_with_amount()
                elif line2.type == 'subtotal':
                    if self == line2:
                        break
                    subtotal = Decimal(0)
            return subtotal
        else:
            return Decimal(0)

    @property
    def origin_name(self):
        if isinstance(self.origin, self.__class__) and self.origin.id >= 0:
            return self.origin.invoice.rec_name
        return self.origin.rec_name if self.origin else None

    @classmethod
    def default_taxes_deductible_rate(cls):
        return 1

    @property
    def taxable_lines(self):
        # In case we're called from an on_change we have to use some sensible
        # defaults
        context = Transaction().context
        if (getattr(self, 'invoice', None)
                and getattr(self.invoice, 'type', None)):
            invoice_type = self.invoice.type
        else:
            invoice_type = getattr(self, 'invoice_type', None)
        if invoice_type == 'in':
            if context.get('_deductible_rate') is not None:
                deductible_rate = context['_deductible_rate']
            else:
                deductible_rate = getattr(self, 'taxes_deductible_rate', 1)
            if deductible_rate is None:
                deductible_rate = 1
            if not deductible_rate:
                return []
        else:
            deductible_rate = 1
        return [(
                list(getattr(self, 'taxes', None)) or [],
                ((getattr(self, 'unit_price', None) or Decimal(0))
                    * deductible_rate),
                getattr(self, 'quantity', None) or 0,
                getattr(self, 'tax_date', None),
                )]

    @property
    def tax_date(self):
        if getattr(self, 'taxes_date', None):
            return self.taxes_date
        elif hasattr(self, 'invoice') and hasattr(self.invoice, 'tax_date'):
            return self.invoice.tax_date

    def _get_tax_context(self):
        if self.invoice:
            return self.invoice._get_tax_context()
        else:
            context = {}
            if self.company:
                context['company'] = self.company.id
            return context

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

    @fields.depends(
        'product', 'unit', 'taxes', '_parent_invoice.type',
        '_parent_invoice.party', 'party', 'invoice', 'invoice_type',
        '_parent_invoice.invoice_date', '_parent_invoice.accounting_date',
        'company',
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
            taxes = set()
            pattern = self._get_tax_rule_pattern()
            for tax in self.product.supplier_taxes_used:
                if party and party.supplier_tax_rule:
                    tax_ids = party.supplier_tax_rule.apply(tax, pattern)
                    if tax_ids:
                        taxes.update(tax_ids)
                    continue
                taxes.add(tax.id)
            if party and party.supplier_tax_rule:
                tax_ids = party.supplier_tax_rule.apply(None, pattern)
                if tax_ids:
                    taxes.update(tax_ids)
            self.taxes = taxes

            if self.company and self.company.purchase_taxes_expense:
                self.taxes_deductible_rate = 0
            else:
                self.taxes_deductible_rate = (
                    self.product.supplier_taxes_deductible_rate_used)
        else:
            with Transaction().set_context(date=date):
                self.account = self.product.account_revenue_used
            taxes = set()
            pattern = self._get_tax_rule_pattern()
            for tax in self.product.customer_taxes_used:
                if party and party.customer_tax_rule:
                    tax_ids = party.customer_tax_rule.apply(tax, pattern)
                    if tax_ids:
                        taxes.update(tax_ids)
                    continue
                taxes.add(tax.id)
            if party and party.customer_tax_rule:
                tax_ids = party.customer_tax_rule.apply(None, pattern)
                if tax_ids:
                    taxes.update(tax_ids)
            self.taxes = taxes

        category = self.product.default_uom.category
        if not self.unit or self.unit.category != category:
            self.unit = self.product.default_uom.id

    @fields.depends('product')
    def on_change_with_product_uom_category(self, name=None):
        return self.product.default_uom_category if self.product else None

    @fields.depends(
        'account', 'product', 'invoice', 'taxes',
        '_parent_invoice.party', '_parent_invoice.type',
        'party', 'invoice', 'invoice_type',
        methods=['_get_tax_rule_pattern'])
    def on_change_account(self):
        if self.product:
            return
        taxes = set()
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
                        taxes.update(tax_ids)
                    continue
                taxes.add(tax.id)
            if tax_rule:
                tax_ids = tax_rule.apply(None, pattern)
                if tax_ids:
                    taxes.update(tax_ids)
        self.taxes = taxes

    @classmethod
    def _get_origin(cls):
        'Return list of Model names for origin Reference'
        return [cls.__name__]

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        get_name = Model.get_name
        models = cls._get_origin()
        return [(None, '')] + [(m, get_name(m)) for m in models]

    def get_rec_name(self, name):
        pool = Pool()
        Lang = pool.get('ir.lang')
        if self.product:
            lang = Lang.get()
            prefix = (lang.format_number_symbol(
                self.quantity or 0, self.unit, digits=self.unit.digits)
                + ' %s' % self.product.rec_name)
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
        _, operator, value = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('invoice.rec_name', *clause[1:]),
            ('product.rec_name', *clause[1:]),
            ('account.rec_name', *clause[1:]),
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
        return super().view_attributes() + [
            ('/form//field[@name="note"]|/form//field[@name="description"]',
                'spell', Eval('party_lang'))]

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
        pool = Pool()
        Invoice = pool.get('account.invoice')
        invoice_ids = filter(None, {v.get('invoice') for v in vlist})
        for invoice in Invoice.browse(list(invoice_ids)):
            if invoice.state != 'draft':
                raise AccessError(
                    gettext('account_invoice.msg_invoice_line_create_draft',
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
                'account', 'taxes_deductible_rate']:
            setattr(line, field, getattr(self, field))
        line.taxes_date = self.tax_date
        line.taxes = self.taxes
        return line


class InvoiceLineTax(ModelSQL):
    'Invoice Line - Tax'
    __name__ = 'account.invoice.line-account.tax'
    _table = 'account_invoice_line_account_tax'
    line = fields.Many2One(
        'account.invoice.line', "Invoice Line",
        ondelete='CASCADE', required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
            required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('line_tax_unique', Unique(t, t.line, t.tax),
                'account_invoice.msg_invoice_line_tax_unique'),
            ]


class InvoiceTax(sequence_ordered(), ModelSQL, ModelView):
    'Invoice Tax'
    __name__ = 'account.invoice.tax'
    _rec_name = 'description'
    _states = {
        'readonly': Eval('invoice_state') != 'draft',
        }

    invoice = fields.Many2One(
        'account.invoice', "Invoice", ondelete='CASCADE', required=True,
        states={
            'readonly': _states['readonly'] & Bool(Eval('invoice')),
            })
    invoice_state = fields.Function(
        fields.Selection('get_invoice_states', "Invoice State"),
        'on_change_with_invoice_state')
    description = fields.Char('Description', size=None, required=True,
        states=_states)
    sequence_number = fields.Function(fields.Integer('Sequence Number'),
            'get_sequence_number')
    account = fields.Many2One('account.account', 'Account', required=True,
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', '=', Eval('_parent_invoice', {}).get('company', 0)),
            ('id', '!=', Eval('_parent_invoice', {}).get('account', -1)),
            ],
        states=_states, depends={'invoice'})
    base = Monetary(
        "Base", currency='currency', digits='currency', required=True,
        states=_states)
    amount = Monetary(
        "Amount", currency='currency', digits='currency', required=True,
        states=_states,
        depends={'tax', 'base', 'manual'})
    currency = fields.Function(fields.Many2One('currency.currency',
        'Currency'), 'on_change_with_currency')
    manual = fields.Boolean('Manual', states=_states)
    tax = fields.Many2One('account.tax', 'Tax',
        ondelete='RESTRICT',
        domain=[
            ['OR',
                ('group', '=', None),
                ('group.kind', 'in',
                    If(Eval('_parent_invoice', {}).get('type') == 'out',
                        ['sale', 'both'],
                        ['purchase', 'both']),
                    )],
            ('company', '=', Eval('_parent_invoice', {}).get('company', 0)),
            ],
        states={
            'readonly': (
                ~Eval('manual', False) | ~Bool(Eval('invoice'))
                | _states['readonly']),
            },
        depends={'invoice'})
    legal_notice = fields.Text("Legal Notice", states=_states)

    del _states

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('invoice')

    @staticmethod
    def default_base():
        return Decimal(0)

    @staticmethod
    def default_amount():
        return Decimal(0)

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
        return self.invoice.currency if self.invoice else None

    @fields.depends(
        'tax', 'invoice', '_parent_invoice.party', 'base',
        methods=['_compute_amount'])
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
        self._compute_amount()

    @fields.depends('base', 'tax', methods=['_compute_amount'])
    def on_change_base(self):
        if self.base is not None and self.tax:
            if self.base >= 0:
                self.account = self.tax.invoice_account
            else:
                self.account = self.tax.credit_note_account
        self._compute_amount()

    @fields.depends(
        'tax', 'base', 'manual', 'invoice', '_parent_invoice.currency',
        # From_date
        '_parent_invoice.accounting_date', '_parent_invoice.invoice_date',
        '_parent_invoice.company')
    def _compute_amount(self):
        pool = Pool()
        Tax = pool.get('account.tax')
        if self.tax and self.manual:
            tax = self.tax
            base = self.base or Decimal(0)
            if self.invoice and self.invoice.tax_date:
                tax_date = self.invoice.tax_date
                for values in Tax.compute([tax], base, 1, tax_date):
                    if (values['tax'] == tax
                            and values['base'] == base):
                        amount = values['amount']
                        if self.invoice.currency:
                            amount = self.invoice.currency.round(amount)
                        self.amount = amount

    @property
    def _key(self):
        # Same as _TaxKey
        tax_id = self.tax.id if getattr(self, 'tax', None) else -1
        account_id = (
            self.account.id if getattr(self, 'account', None) else None)
        return (account_id, tax_id, (getattr(self, 'base', 0) or 0) >= 0)

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
        pool = Pool()
        Invoice = pool.get('account.invoice')
        invoice_ids = filter(None, {v.get('invoice') for v in vlist})
        for invoice in Invoice.browse(list(invoice_ids)):
            if invoice.state != 'draft':
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
                base = Currency.compute(self.invoice.currency, self.base,
                    self.invoice.company.currency)
            line.amount_second_currency = self.amount
            line.second_currency = self.invoice.currency
        else:
            amount = self.amount
            base = self.base
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
            tax_lines = []
            tax_line = TaxLine()
            tax_line.amount = amount
            tax_line.type = 'tax'
            tax_line.tax = self.tax
            tax_lines.append(tax_line)
            if self.manual:
                tax_line = TaxLine()
                tax_line.amount = base
                tax_line.type = 'base'
                tax_line.tax = self.tax
                tax_lines.append(tax_line)
            line.tax_lines = tax_lines
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
    journal = fields.Many2One(
        'account.journal', "Journal", required=True,
        domain=[('type', '=', 'cash')],
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    credit_account = fields.Many2One('account.account', "Credit Account",
        required=True,
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', '=', Eval('company')),
            ])
    debit_account = fields.Many2One('account.account', "Debit Account",
        required=True,
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', '=', Eval('company')),
            ])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')


class InvoiceReportRevision(ModelSQL, ModelView, InvoiceReportMixin):
    "Invoice Report Revision"
    __name__ = 'account.invoice.report.revision'
    invoice = fields.Many2One(
        'account.invoice', "Invoice", required=True, ondelete='CASCADE')
    date = fields.DateTime("Date", required=True, readonly=True)
    filename = fields.Function(fields.Char("File Name"), 'get_filename')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('invoice')
        cls._order.insert(0, ('date', 'DESC'))
        cls.invoice_report_cache.filename = 'filename'

    @classmethod
    def default_date(cls):
        return dt.datetime.now()

    @classmethod
    def get_filename(cls, revisions, name):
        pool = Pool()
        ActionReport = pool.get('ir.action.report')

        action_report, = ActionReport.search([
                ('report_name', '=', 'account.invoice'),
                ], limit=1)

        action_report_name = action_report.name[:100]
        if action_report.record_name:
            template = TextTemplate(action_report.record_name)
        else:
            template = None
        filenames = {}
        for revision in revisions:
            invoice = revision.invoice
            if template:
                record_name = template.generate(record=invoice).render()
            else:
                record_name = invoice.rec_name
            filename = '-'.join([action_report_name, record_name])
            filenames[revision.id] = (
                f'{slugify(filename)}.{revision.invoice_report_format}')
        return filenames


class RefreshInvoiceReport(Wizard):
    "Refresh Invoice Report"
    __name__ = 'account.invoice.refresh_invoice_report'
    start_state = 'archive'
    archive = StateTransition()
    print_ = StateReport('account.invoice')

    def transition_archive(self):
        for record in self.records:
            record.create_invoice_report_revision()
        self.model.save(self.records)
        return 'print_'

    def do_print_(self, action):
        ids = [r.id for r in self.records]
        return action, {'ids': ids}


class InvoiceReport(Report):
    __name__ = 'account.invoice'

    @classmethod
    def __setup__(cls):
        super(InvoiceReport, cls).__setup__()
        cls.__rpc__['execute'] = RPC(False)

    @classmethod
    def _execute(cls, records, header, data, action):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        # Re-instantiate because records are TranslateModel
        invoice, = Invoice.browse(records)
        if invoice.invoice_report_cache:
            return (
                invoice.invoice_report_format,
                invoice.invoice_report_cache)
        else:
            result = super()._execute(records, header, data, action)
            if invoice.invoice_report_versioned:
                format_, data = result
                if isinstance(data, str):
                    data = bytes(data, 'utf-8')
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
    def get_context(cls, records, header, data):
        pool = Pool()
        Date = pool.get('ir.date')
        context = super().get_context(records, header, data)
        context['invoice'] = context['record']
        with Transaction().set_context(company=context['invoice'].company.id):
            context['today'] = Date.today()
        return context


class PayInvoiceStart(ModelView):
    'Pay Invoice'
    __name__ = 'account.invoice.pay.start'

    payee = fields.Many2One(
        'party.party', "Payee", required=True,
        domain=[
            ('id', 'in', Eval('payees', []))
            ],
        context={
            'company': Eval('company', -1),
            },
        depends=['company'])
    payees = fields.Many2Many(
        'party.party', None, None, "Payees", readonly=True,
        context={
            'company': Eval('company', -1),
            },
        depends=['company'])
    amount = Monetary(
        "Amount", currency='currency', digits='currency', required=True)
    currency = fields.Many2One('currency.currency', 'Currency', readonly=True)
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
        depends={'amount'})
    date = fields.Date('Date', required=True)

    @staticmethod
    def default_date():
        Date = Pool().get('ir.date')
        return Date.today()


class PayInvoiceAsk(ModelView):
    'Pay Invoice'
    __name__ = 'account.invoice.pay.ask'
    type = fields.Selection([
            ('writeoff', "Write-Off"),
            ('partial', "Partial Payment"),
            ('overpayment', "Overpayment"),
            ], 'Type', required=True,
        domain=[
            If(Eval('amount_writeoff', 0) >= 0,
                ('type', 'in', ['writeoff', 'partial']),
                ()),
            ])
    writeoff = fields.Many2One(
        'account.move.reconcile.write_off', "Write Off",
        domain=[
            ('company', '=', Eval('company')),
            ],
        states={
            'invisible': Eval('type') != 'writeoff',
            'required': Eval('type') == 'writeoff',
            })
    amount = Monetary(
        "Payment Amount",
        currency='currency', digits='currency', readonly=True)
    currency = fields.Many2One('currency.currency', "Currency", readonly=True)
    amount_writeoff = Monetary(
        "Write-Off Amount",
        currency='currency', digits='currency',
        readonly=True,
        states={
            'invisible': ~Eval('type').in_(['writeoff', 'overpayment']),
            })
    lines_to_pay = fields.Many2Many('account.move.line', None, None,
            'Lines to Pay', readonly=True)
    lines = fields.Many2Many('account.move.line', None, None, 'Lines',
        domain=[
            ('id', 'in', Eval('lines_to_pay')),
            ('reconciliation', '=', None),
            ],
        states={
            'invisible': ~Eval('type').in_(['writeoff', 'overpayment']),
            'required': Eval('type').in_(['writeoff', 'overpayment']),
            })
    payment_lines = fields.Many2Many('account.move.line', None, None,
        'Payment Lines', readonly=True,
        states={
            'invisible': ~Eval('type').in_(['writeoff', 'overpayment']),
            })
    company = fields.Many2One('company.company', 'Company', readonly=True)
    invoice = fields.Many2One('account.invoice', 'Invoice', readonly=True)

    @staticmethod
    def default_type():
        return 'partial'

    @fields.depends(
        'lines', 'amount', 'currency', 'invoice', 'payment_lines', 'company')
    def on_change_lines(self):
        self.amount_writeoff = Decimal(0)
        if not self.invoice:
            return

        def balance(line):
            if self.currency == line.second_currency:
                return line.amount_second_currency
            elif self.currency == self.company.currency:
                return line.debit - line.credit
            else:
                return 0

        for line in self.lines:
            self.amount_writeoff += balance(line)
        for line in self.payment_lines:
            self.amount_writeoff += balance(line)
        if self.invoice.type == 'in':
            self.amount_writeoff = - self.amount_writeoff - self.amount
        else:
            self.amount_writeoff = self.amount_writeoff - self.amount


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

    def get_reconcile_lines_for_amount(self, invoice, amount, currency):
        if invoice.type == 'in':
            amount *= -1
        return invoice.get_reconcile_lines_for_amount(
            amount, currency, party=self.start.payee)

    def default_start(self, fields):
        default = {}
        invoice = self.record
        payee = None
        if not invoice.alternative_payees:
            payee = invoice.party
        else:
            try:
                payee, = invoice.alternative_payees
            except ValueError:
                pass
        if payee:
            default['payee'] = payee.id
        default['payees'] = (
            [invoice.party.id] + [p.id for p in invoice.alternative_payees])
        default['company'] = invoice.company.id
        default['currency'] = invoice.currency.id
        default['amount'] = (invoice.amount_to_pay_today
            or invoice.amount_to_pay)
        default['invoice_account'] = invoice.account.id
        return default

    def transition_choice(self):
        invoice = self.record
        amount = self.start.amount
        currency = self.start.currency
        _, remainder = self.get_reconcile_lines_for_amount(
            invoice, amount, currency)
        if remainder == Decimal(0) and amount <= invoice.amount_to_pay:
            return 'pay'
        return 'ask'

    def default_ask(self, fields):
        default = {}
        invoice = self.record
        amount = self.start.amount
        currency = self.start.currency
        default['lines_to_pay'] = [x.id for x in invoice.lines_to_pay
                if not x.reconciliation]

        default['amount'] = amount
        default['currency'] = currency.id
        default['company'] = invoice.company.id

        if currency.is_zero(amount):
            lines = invoice.lines_to_pay
        else:
            lines, _ = self.get_reconcile_lines_for_amount(
                invoice, amount, currency)
        default['lines'] = [x.id for x in lines]

        for line_id in default['lines'][:]:
            if line_id not in default['lines_to_pay']:
                default['lines'].remove(line_id)

        default['payment_lines'] = [x.id for x in invoice.payment_lines
                if not x.reconciliation]

        default['invoice'] = invoice.id

        if amount >= invoice.amount_to_pay:
            default['type'] = 'overpayment'
        elif currency.is_zero(amount):
            default['type'] = 'writeoff'
        return default

    def transition_pay(self):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Lang = pool.get('ir.lang')

        invoice = self.record
        amount = self.start.amount
        currency = self.start.currency

        reconcile_lines, remainder = (
            self.get_reconcile_lines_for_amount(invoice, amount, currency))

        overpayment = 0
        if (0 <= invoice.amount_to_pay < amount
                or amount < invoice.amount_to_pay <= 0):
            if self.ask.type == 'partial':
                lang = Lang.get()
                raise PayInvoiceError(
                    gettext('account_invoice'
                        '.msg_invoice_pay_amount_greater_amount_to_pay',
                        invoice=invoice.rec_name,
                        amount_to_pay=lang.currency(
                            invoice.amount_to_pay, invoice.currency)))
            else:
                if not invoice.amount_to_pay:
                    raise PayInvoiceError(
                        gettext('account_invoice.msg_invoice_overpay_paid',
                            invoice=invoice.rec_name))
                overpayment = amount - invoice.amount_to_pay

        lines = []
        if not currency.is_zero(amount):
            lines = invoice.pay_invoice(
                amount, self.start.payment_method, self.start.date,
                self.start.description, overpayment, party=self.start.payee)

        if remainder:
            if self.ask.type != 'partial':
                to_reconcile = {l for l in self.ask.lines}
                to_reconcile.update(
                    l for l in invoice.payment_lines
                    if not l.reconciliation
                    and (not invoice.account.party_required
                        or l.party == self.start.payee))
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


class RescheduleLinesToPay(Wizard):
    "Reschedule Lines to Pay"
    __name__ = 'account.invoice.lines_to_pay.reschedule'
    start = StateAction('account.act_reschedule_lines_wizard')

    def do_start(self, action):
        return action, {
            'ids': [
                l.id for l in self.record.lines_to_pay
                if not l.reconciliation],
            'model': 'account.move.line',
            }


class DelegateLinesToPay(Wizard):
    "Delegate Lines to Pay"
    __name__ = 'account.invoice.lines_to_pay.delegate'
    start = StateAction('account.act_delegate_lines_wizard')

    def do_start(self, action):
        return action, {
            'ids': [
                l.id for l in self.record.lines_to_pay
                if not l.reconciliation],
            'model': 'account.move.line',
            }
