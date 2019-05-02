# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from collections import defaultdict, namedtuple
from itertools import combinations

from sql import Null
from sql.aggregate import Sum
from sql.conditionals import Coalesce, Case
from sql.functions import Round

from trytond.model import Workflow, ModelView, ModelSQL, fields, Check, \
    sequence_ordered, Unique, DeactivableMixin
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

__all__ = ['Invoice', 'InvoicePaymentLine', 'InvoiceLine',
    'InvoiceLineTax', 'InvoiceTax', 'PaymentMethod',
    'InvoiceReport',
    'PayInvoiceStart', 'PayInvoiceAsk', 'PayInvoice',
    'CreditInvoiceStart', 'CreditInvoice']

_STATES = {
    'readonly': Eval('state') != 'draft',
}
_DEPENDS = ['state']

_TYPE = [
    ('out', 'Customer'),
    ('in', 'Supplier'),
]

_TYPE2JOURNAL = {
    'out': 'revenue',
    'in': 'expense',
}

_ZERO = Decimal('0.0')
STATES = [
    ('draft', 'Draft'),
    ('validated', 'Validated'),
    ('posted', 'Posted'),
    ('paid', 'Paid'),
    ('cancel', 'Canceled'),
    ]

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
    company = fields.Many2One('company.company', 'Company', required=True,
        states=_STATES, select=True, domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        depends=_DEPENDS)
    company_party = fields.Function(
        fields.Many2One('party.party', "Company Party"),
        'on_change_with_company_party')
    tax_identifier = fields.Many2One(
        'party.identifier', "Tax Identifier",
        states=_STATES, depends=_DEPENDS)
    type = fields.Selection(_TYPE, 'Type', select=True,
        required=True, states={
            'readonly': ((Eval('state') != 'draft')
                | Eval('context', {}).get('type')
                | (Eval('lines', [0]) & Eval('type'))),
            }, depends=['state'])
    type_name = fields.Function(fields.Char('Type'), 'get_type_name')
    number = fields.Char('Number', size=None, readonly=True, select=True)
    reference = fields.Char('Reference', size=None, states=_STATES,
        depends=_DEPENDS)
    description = fields.Char('Description', size=None, states=_STATES,
        depends=_DEPENDS)
    state = fields.Selection(STATES, 'State', readonly=True)
    invoice_date = fields.Date('Invoice Date',
        states={
            'readonly': Eval('state').in_(['posted', 'paid', 'cancel']),
            'required': Eval('state').in_(
                If(Eval('type') == 'in',
                    ['validated', 'posted', 'paid'],
                    ['posted', 'paid'])),
            },
        depends=['state'])
    accounting_date = fields.Date('Accounting Date', states=_STATES,
        depends=_DEPENDS)
    party = fields.Many2One('party.party', 'Party',
        required=True, states=_STATES, depends=_DEPENDS)
    party_tax_identifier = fields.Many2One(
        'party.identifier', "Party Tax Identifier",
        states=_STATES,
        domain=[
            ('party', '=', Eval('party', -1)),
            ],
        depends=_DEPENDS + ['party'])
    party_lang = fields.Function(fields.Char('Party Language'),
        'on_change_with_party_lang')
    invoice_address = fields.Many2One('party.address', 'Invoice Address',
        required=True, states=_STATES, depends=['state', 'party'],
        domain=[('party', '=', Eval('party'))])
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states=_STATES, depends=_DEPENDS)
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    currency_date = fields.Function(fields.Date('Currency Date'),
        'on_change_with_currency_date')
    journal = fields.Many2One('account.journal', 'Journal', required=True,
        states=_STATES, depends=_DEPENDS)
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
            'invisible': Eval('type') == 'out',
            },
        depends=['company'])
    account = fields.Many2One('account.account', 'Account', required=True,
        states=_STATES, depends=_DEPENDS + ['type', 'company'],
        domain=[
            ('company', '=', Eval('company', -1)),
            If(Eval('type') == 'out',
                ('kind', '=', 'receivable'),
                ('kind', '=', 'payable')),
            ])
    payment_term = fields.Many2One('account.invoice.payment_term',
        'Payment Term', states=_STATES, depends=_DEPENDS)
    lines = fields.One2Many('account.invoice.line', 'invoice', 'Lines',
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        states={
            'readonly': (Eval('state') != 'draft') | ~Eval('company'),
            },
        depends=['state', 'company'])
    taxes = fields.One2Many('account.invoice.tax', 'invoice', 'Tax Lines',
        states=_STATES, depends=_DEPENDS)
    comment = fields.Text('Comment', states=_STATES, depends=_DEPENDS)
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
    lines_to_pay = fields.Function(fields.One2Many('account.move.line', None,
        'Lines to Pay'), 'get_lines_to_pay')
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

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls._check_modify_exclude = ['state', 'payment_lines', 'cancel_move',
                'invoice_report_cache', 'invoice_report_format']
        cls._order = [
            ('number', 'DESC'),
            ('id', 'DESC'),
            ]
        cls.tax_identifier.domain = [
            ('party', '=', Eval('company_party', -1)),
            ('type', 'in', cls._tax_identifier_types()),
            ]
        cls.tax_identifier.depends += ['company_party']
        cls._error_messages.update({
                'missing_tax_line': ('Invoice "%s" has taxes defined but not '
                    'on invoice lines.\nRe-compute the invoice.'),
                'diff_tax_line': ('Invoice "%s" tax bases are different from '
                    'invoice lines.\nRe-compute the invoice.'),
                'missing_tax_line2': (
                    'Invoice "%s" has taxes on invoice lines '
                    'that are not in the invoice.\nRe-compute the invoice.'),
                'no_invoice_sequence': ('Missing invoice sequence for '
                    'invoice "%(invoice)s" on fiscalyear "%(fiscalyear)s".'),
                'modify_invoice': ('You can not modify invoice "%s" because '
                    'it is posted, paid or cancelled.'),
                'same_account_on_line': ('Invoice "%(invoice)s" uses the same '
                    'account "%(account)s" for the invoice and in line '
                    '"%(line)s".'),
                'delete_cancel': ('Invoice "%s" must be cancelled before '
                    'deletion.'),
                'delete_numbered': ('The numbered invoice "%s" can not be '
                    'deleted.'),
                'customer_invoice_cancel_move': (
                    'Customer invoice/credit note '
                    '"%s" can not be cancelled once posted.'),
                'payment_lines_greater_amount': (
                    'The payment lines on invoice "%(invoice)s" can not be '
                    'greater than the invoice amount.'),
                'modify_payment_lines_invoice_paid': (
                    'Payment lines can not be modified '
                    'on a paid invoice "%(invoice)s"'),
                })
        cls._transitions |= set((
                ('draft', 'validated'),
                ('validated', 'posted'),
                ('draft', 'posted'),
                ('posted', 'paid'),
                ('validated', 'draft'),
                ('paid', 'posted'),
                ('draft', 'cancel'),
                ('validated', 'cancel'),
                ('posted', 'cancel'),
                ('cancel', 'draft'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': (~Eval('state').in_(['draft', 'validated'])
                        & ~((Eval('state') == 'posted')
                            & (Eval('type') == 'in'))),
                    'help': 'Cancel the invoice',
                    'depends': ['state', 'type'],
                    },
                'draft': {
                    'invisible': (~Eval('state').in_(['cancel', 'validated'])
                        | ((Eval('state') == 'cancel')
                            & Eval('cancel_move', -1))),
                    'icon': If(Eval('state') == 'cancel', 'tryton-undo',
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

    @fields.depends('party', 'type', 'accounting_date', 'invoice_date')
    def _get_account_payment_term(self):
        '''
        Return default account and payment term
        '''
        self.account = None
        if self.party:
            with Transaction().set_context(
                    date=self.accounting_date or self.invoice_date):
                if self.type == 'out':
                    self.account = self.party.account_receivable_used
                    if self.party.customer_payment_term:
                        self.payment_term = self.party.customer_payment_term
                elif self.type == 'in':
                    self.account = self.party.account_payable_used
                    if self.party.supplier_payment_term:
                        self.payment_term = self.party.supplier_payment_term

    @fields.depends('type', methods=['_get_account_payment_term'])
    def on_change_type(self):
        Journal = Pool().get('account.journal')
        journals = Journal.search([
                ('type', '=', _TYPE2JOURNAL.get(self.type or 'out',
                        'revenue')),
                ], limit=1)
        if journals:
            self.journal, = journals
        self._get_account_payment_term()

    @fields.depends('party', methods=['_get_account_payment_term'])
    def on_change_party(self):
        self.invoice_address = None
        self._get_account_payment_term()

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

    @fields.depends('lines', 'taxes', 'currency', 'party', 'type',
        'accounting_date', 'invoice_date')
    def on_change_lines(self):
        self._on_change_lines_taxes()

    @fields.depends('lines', 'taxes', 'currency', 'party', 'type',
        'accounting_date', 'invoice_date')
    def on_change_taxes(self):
        self._on_change_lines_taxes()

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
                return amount != Decimal('0.0')

        tax_keys = []
        taxes = list(self.taxes or [])
        for tax in (self.taxes or []):
            if tax.manual:
                self.tax_amount += tax.amount or Decimal('0.0')
                continue
            tax_id = tax.tax.id if tax.tax else None
            key = (tax.account.id, tax_id)
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
                value = InvoiceTax.default_get(list(InvoiceTax._fields.keys()))
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

        untaxed_amount = dict((i.id, _ZERO) for i in invoices)
        tax_amount = dict((i.id, _ZERO) for i in invoices)
        total_amount = dict((i.id, _ZERO) for i in invoices)

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
                            Case((line.second_currency == invoice.currency,
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
                    if line.type == 'line'), _ZERO)
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
        reconciliations = [l.reconciliation for l in self.lines_to_pay]
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
                        where=(line.maturity_date != Null) & red_sql,
                        order_by=(invoice.id, line.maturity_date)))
            for invoice_id, line_id in cursor.fetchall():
                lines[invoice_id].append(line_id)
        return lines

    @classmethod
    def get_amount_to_pay(cls, invoices, name):
        pool = Pool()
        Currency = pool.get('currency.currency')
        Date = pool.get('ir.date')

        today = Date.today()
        res = dict((x.id, _ZERO) for x in invoices)
        for invoice in invoices:
            if invoice.state != 'posted':
                continue
            amount = _ZERO
            amount_currency = _ZERO
            for line in invoice.lines_to_pay:
                if line.reconciliation:
                    continue
                if (name == 'amount_to_pay_today'
                        and line.maturity_date > today):
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
            if amount != _ZERO:
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
        if backend.name() == 'sqlite':
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
        if backend.name() == 'sqlite':
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
        if backend.name() == 'sqlite':
            value = float(value)

        query = tax.select(tax.invoice,
            where=tax.invoice.in_(invoice_query),
            group_by=tax.invoice,
            having=Operator(Coalesce(Sum(tax.amount), 0).cast(type_name),
                value))
        return [('id', 'in', query)]

    @property
    def taxable_lines(self):
        taxable_lines = []
        # In case we're called from an on_change we have to use some sensible
        # defaults
        for line in self.lines:
            if getattr(line, 'type', None) != 'line':
                continue
            taxable_lines.append(tuple())
            for attribute, default_value in [
                    ('taxes', []),
                    ('unit_price', Decimal(0)),
                    ('quantity', 0.),
                    ]:
                value = getattr(line, attribute, None)
                taxable_lines[-1] += (
                    value if value is not None else default_value,)
        return taxable_lines

    @property
    def tax_date(self):
        return self.accounting_date or self.invoice_date

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

    @classmethod
    def update_taxes(cls, invoices, exception=False):
        Tax = Pool().get('account.invoice.tax')
        to_create = []
        to_delete = []
        to_write = []
        for invoice in invoices:
            if invoice.state in ('posted', 'paid', 'cancel'):
                continue
            computed_taxes = invoice._compute_taxes()
            if not invoice.taxes:
                to_create.extend(computed_taxes.values())
            else:
                tax_keys = []
                for tax in invoice.taxes:
                    if tax.manual:
                        continue
                    tax_id = tax.tax.id if tax.tax else None
                    key = (tax.account.id, tax_id)
                    if (key not in computed_taxes) or (key in tax_keys):
                        if exception:
                            cls.raise_user_error('missing_tax_line',
                                (invoice.rec_name,))
                        to_delete.append(tax)
                        continue
                    tax_keys.append(key)
                    if not invoice.currency.is_zero(
                            computed_taxes[key]['base'] - tax.base):
                        if exception:
                            cls.raise_user_error('diff_tax_line',
                                (invoice.rec_name,))
                        to_write.extend(([tax], computed_taxes[key]))
                for key in computed_taxes:
                    if key not in tax_keys:
                        if exception:
                            cls.raise_user_error('missing_tax_line2',
                                (invoice.rec_name,))
                        to_create.append(computed_taxes[key])
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
        self.update_taxes([self], exception=True)
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
                invoice.invoice_date = Date.today()
            invoice.number = invoice.get_next_number()
        cls.save(invoices)

    def get_next_number(self, pattern=None):
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
        invoice_type = self.type
        if (all(l.amount < 0 for l in self.lines if l.product)
                and self.total_amount < 0):
            invoice_type += '_credit_note'
        else:
            invoice_type += '_invoice'

        for invoice_sequence in fiscalyear.invoice_sequences:
            if invoice_sequence.match(pattern):
                sequence = getattr(
                    invoice_sequence, '%s_sequence' % invoice_type)
                break
        else:
            self.raise_user_error('no_invoice_sequence', {
                    'invoice': self.rec_name,
                    'fiscalyear': fiscalyear.rec_name,
                    })
        with Transaction().set_context(date=accounting_date):
            return Sequence.get_id(sequence.id)

    @classmethod
    def _tax_identifier_types(cls):
        return ['eu_vat']

    def get_tax_identifier(self):
        "Return the default computed tax identifier"
        types = self._tax_identifier_types()
        for identifier in self.company.party.identifiers:
            if identifier.type in types:
                return identifier.id

    @classmethod
    def check_modify(cls, invoices):
        '''
        Check if the invoices can be modified
        '''
        for invoice in invoices:
            if (invoice.state in ('posted', 'paid')
                    or (invoice.state == 'cancel'
                        and invoice.cancel_move)):
                cls.raise_user_error('modify_invoice', (invoice.rec_name,))

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
        return [('/form//field[@name="comment"]', 'spell', Eval('party_lang'))]

    @classmethod
    def delete(cls, invoices):
        cls.check_modify(invoices)
        # Cancel before delete
        cls.cancel(invoices)
        for invoice in invoices:
            if invoice.state != 'cancel':
                cls.raise_user_error('delete_cancel', (invoice.rec_name,))
            if invoice.number:
                cls.raise_user_error('delete_numbered', (invoice.rec_name,))
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
        default.setdefault('move', None)
        default.setdefault('cancel_move', None)
        default.setdefault('invoice_report_cache', None)
        default.setdefault('invoice_report_format', None)
        default.setdefault('payment_lines', None)
        default.setdefault('invoice_date', None)
        default.setdefault('accounting_date', None)
        default.setdefault('lines_to_pay', None)
        return super(Invoice, cls).copy(invoices, default=default)

    @classmethod
    def validate(cls, invoices):
        super(Invoice, cls).validate(invoices)
        for invoice in invoices:
            invoice.check_same_account()
            invoice.check_cancel_move()
            invoice.check_payment_lines()

    def check_same_account(self):
        for line in self.lines:
            if (line.type == 'line'
                    and line.account == self.account):
                self.raise_user_error('same_account_on_line', {
                        'invoice': self.rec_name,
                        'account': self.account.rec_name,
                        'line': line.rec_name,
                        })

    def check_cancel_move(self):
        if self.type == 'out' and self.cancel_move:
            self.raise_user_error('customer_invoice_cancel_move',
                self.rec_name)

    def check_payment_lines(self):
        amount = sum(l.debit - l.credit for l in self.lines_to_pay)
        payment_amount = sum(l.debit - l.credit for l in self.payment_lines)
        if abs(amount) < abs(payment_amount):
            self.raise_user_error('payment_lines_greater_amount', {
                    'invoice': self.rec_name,
                    })

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

    def pay_invoice(self, amount, payment_method, date, description,
            amount_second_currency=None, second_currency=None):
        '''
        Adds a payment of amount to an invoice using the journal, date and
        description.
        Returns the payment line.
        '''
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Period = pool.get('account.period')

        line1 = Line(account=self.account)
        line2 = Line()
        lines = [line1, line2]

        if amount >= 0:
            if self.type == 'out':
                line1.debit, line1.credit = 0, amount
            else:
                line1.debit, line1.credit = amount, 0
        else:
            if self.type == 'out':
                line1.debit, line1.credit = -amount, 0
            else:
                line1.debit, line1.credit = 0, -amount

        line2.debit, line2.credit = line1.credit, line1.debit
        if line2.debit:
            payment_acccount = 'debit_account'
        else:
            payment_acccount = 'credit_account'
        line2.account = getattr(payment_method, payment_acccount)

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

        for line in move.lines:
            if line.account == self.account:
                self.add_payment_lines({self: [line]})
                return line
        raise Exception('Missing account')

    @classmethod
    def add_payment_lines(cls, payments):
        "Add value lines to the key invoice from the payment dictionary."
        to_write = []
        for invoice, lines in payments.items():
            if invoice.state == 'paid':
                cls.raise_user_error('modify_payment_lines_invoice_paid', {
                        'invoice': invoice.rec_name,
                        })
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
                cls.raise_user_error('modify_payment_lines_invoice_paid', {
                        'invoice': invoice.rec_name,
                        })
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

    def _credit(self):
        '''
        Return values to credit invoice.
        '''
        credit = self.__class__()

        for field in ('company', 'party', 'invoice_address', 'currency',
               'journal', 'account', 'payment_term', 'description',
               'comment', 'type'):
            setattr(credit, field, getattr(self, field))

        credit.lines = [line._credit() for line in self.lines]
        credit.taxes = [tax._credit() for tax in self.taxes if tax.manual]
        return credit

    @classmethod
    def credit(cls, invoices, refund=False):
        '''
        Credit invoices and return ids of new invoices.
        Return the list of new invoice
        '''
        MoveLine = Pool().get('account.move.line')

        new_invoices = [i._credit() for i in invoices]
        cls.save(new_invoices)
        cls.update_taxes(new_invoices)
        if refund:
            cls.post(new_invoices)
            for invoice, new_invoice in zip(invoices, new_invoices):
                if new_invoice.state == 'posted':
                    MoveLine.reconcile([l for l in invoice.lines_to_pay
                            if not l.reconciliation] +
                        [l for l in new_invoice.lines_to_pay
                            if not l.reconciliation])
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
        for invoice in invoices:
            if invoice.type == 'out':
                invoice.print_invoice()

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
        to_write = []
        for invoice in invoices:
            to_remove = []
            reconciliations = [l.reconciliation for l in invoice.lines_to_pay]
            for payment_line in invoice.payment_lines:
                if payment_line.reconciliation not in reconciliations:
                    to_remove.append(payment_line)
            if to_remove:
                to_write.append([invoice])
                to_write.append({
                        'payment_lines': [('remove', to_remove)],
                        })
        if to_write:
            cls.write(*to_write)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
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
                'state': 'cancel',
                })
        # Reconcile lines to pay with the cancellation ones if possible
        for invoice in invoices:
            if not invoice.move or not invoice.cancel_move:
                continue
            to_reconcile = []
            for line in invoice.move.lines + invoice.cancel_move.lines:
                if line.account == invoice.account:
                    if line.reconciliation:
                        break
                    to_reconcile.append(line)
            else:
                if to_reconcile:
                    Line.reconcile(to_reconcile)


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
                "A payment line can be linked to only one invoice."),
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
    invoice_state = fields.Function(fields.Selection(STATES, 'Invoice State'),
        'on_change_with_invoice_state')
    invoice_type = fields.Selection(_TYPE + [(None, '')], 'Invoice Type',
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
    currency = fields.Many2One('currency.currency', 'Currency',
        states={
            'required': ~Eval('invoice'),
            'readonly': _states['readonly'],
            },
        depends=['invoice'] + _depends)
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
        states={
            'invisible': Eval('type') != 'line',
            'readonly': _states['readonly'],
            },
        depends=['type'] + _depends)
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
            'date': If(Bool(Eval('_parent_invoice.accounting_date')),
                Eval('_parent_invoice.accounting_date'),
                Eval('_parent_invoice.invoice_date')),
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
    invoice_taxes = fields.Function(fields.One2Many('account.invoice.tax',
        None, 'Invoice Taxes'), 'get_invoice_taxes')
    origin = fields.Reference('Origin', selection='get_origin', select=True,
        states=_states, depends=_depends)

    del _states, _depends

    @classmethod
    def __setup__(cls):
        super(InvoiceLine, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('type_account',
                Check(t, ((t.type == 'line') & (t.account != Null))
                    | (t.type != 'line')),
                'Line with "line" type must have an account.'),
            ('type_invoice',
                Check(t, ((t.type != 'line') & (t.invoice != Null))
                    | (t.type == 'line')),
                'Line without "line" type must have an invoice.'),
            ]
        cls._error_messages.update({
                'modify': ('You can not modify line "%(line)s" from invoice '
                    '"%(invoice)s" that is posted or paid.'),
                'create': ('You can not add a line to invoice "%(invoice)s" '
                    'that is posted, paid or cancelled.'),
                'same_account_on_invoice': ('You can not create invoice line '
                    '"%(line)s" on invoice "%(invoice)s" because the invoice '
                    'uses the same account (%(account)s).'),
                })

        cls._check_modify_exclude = {'note', 'origin'}

        # Set account domain dynamically for kind
        cls.account.domain = [
            ('company', '=', Eval('company', -1)),
            If(Bool(Eval('_parent_invoice')),
                If(Eval('_parent_invoice', {}).get('type') == 'out',
                    ('kind', 'in', cls._account_domain('out')),
                    If(Eval('_parent_invoice', {}).get('type') == 'in',
                        ('kind', 'in', cls._account_domain('in')),
                        ('kind', 'in',
                            cls._account_domain('out')
                            + cls._account_domain('in')))),
                If(Eval('invoice_type') == 'out',
                    ('kind', 'in', cls._account_domain('out')),
                    If(Eval('invoice_type') == 'in',
                        ('kind', 'in', cls._account_domain('in')),
                        ('kind', 'in',
                            cls._account_domain('out')
                            + cls._account_domain('in'))))),
            ]
        cls.account.depends += ['company', 'invoice_type']
        cls.sequence.states.update({
                'invisible': Bool(Eval('context', {}).get('standalone')),
                })

    @staticmethod
    def _account_domain(type_):
        if type_ == 'out':
            return ['revenue']
        elif type_ == 'in':
            return ['expense']

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
            subtotal = _ZERO
            for line2 in self.invoice.lines:
                if line2.type == 'line':
                    subtotal += line2.invoice.currency.round(
                        Decimal(str(line2.quantity)) * line2.unit_price)
                elif line2.type == 'subtotal':
                    if self == line2:
                        break
                    subtotal = _ZERO
            return subtotal
        else:
            return _ZERO

    @property
    def origin_name(self):
        if isinstance(self.origin, self.__class__):
            return self.origin.invoice.rec_name
        return self.origin.rec_name if self.origin else None

    @property
    def taxable_lines(self):
        return [(self.taxes, self.unit_price, self.quantity)]

    @property
    def tax_date(self):
        return self.invoice.tax_date

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
            tax_id = tax.tax.id if tax.tax else None
            key = (tax.account.id, tax_id)
            if key in taxes_keys:
                taxes.append(tax.id)
        return taxes

    def _get_tax_rule_pattern(self):
        '''
        Get tax rule pattern
        '''
        return {}

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

    @classmethod
    def check_modify(cls, lines, fields=None):
        '''
        Check if the lines can be modified
        '''
        if fields is None or fields - cls._check_modify_exclude:
            for line in lines:
                if (line.invoice
                        and line.invoice.state in ('posted', 'paid')):
                    cls.raise_user_error('modify', {
                            'line': line.rec_name,
                            'invoice': line.invoice.rec_name
                            })

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
            if invoice.state in ('posted', 'paid', 'cancel'):
                cls.raise_user_error('create', (invoice.rec_name,))
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
                self.raise_user_error('same_account_on_invoice', {
                        'line': self.rec_name,
                        'invoice': self.invoice.rec_name,
                        'account': self.account.rec_name,
                        })

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

        for field in ('sequence', 'type', 'invoice_type', 'unit_price',
                'description', 'unit', 'product', 'account'):
            setattr(line, field, getattr(self, field))
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
    invoice_state = fields.Function(fields.Selection(STATES, 'Invoice State'),
        'on_change_with_invoice_state')
    description = fields.Char('Description', size=None, required=True,
        states=_states, depends=_depends)
    sequence_number = fields.Function(fields.Integer('Sequence Number'),
            'get_sequence_number')
    account = fields.Many2One('account.account', 'Account', required=True,
        domain=[
            ('kind', '!=', 'view'),
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
    def __setup__(cls):
        super(InvoiceTax, cls).__setup__()
        cls._error_messages.update({
                'modify': ('You can not modify tax "%(tax)s" from invoice '
                    '"%(invoice)s" because it is posted or paid.'),
                'create': ('You can not add tax to invoice '
                    '"%(invoice)s" because it is posted, paid or canceled.'),
                })

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

    @fields.depends('invoice', '_parent_invoice.state')
    def on_change_with_invoice_state(self, name=None):
        if self.invoice:
            return self.invoice.state

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

    @classmethod
    def check_modify(cls, taxes):
        '''
        Check if the taxes can be modified
        '''
        for tax in taxes:
            if tax.invoice.state in ('posted', 'paid'):
                cls.raise_user_error('modify', {
                        'tax': tax.rec_name,
                        'invoice': tax.invoice.rec_name,
                        })

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
            if invoice.state in ('posted', 'paid', 'cancel'):
                cls.raise_user_error('create', {
                        'invoice': invoice.rec_name,
                        })
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
            ('kind', '!=', 'view'),
            ('company', '=', Eval('company')),
            ],
        depends=['company'])
    debit_account = fields.Many2One('account.account', "Debit Account",
        required=True,
        domain=[
            ('kind', '!=', 'view'),
            ('company', '=', Eval('company')),
            ],
        depends=['company'])

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
    def execute(cls, ids, data):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        with Transaction().set_context(
                language=False,
                address_with_party=True):
            result = super(InvoiceReport, cls).execute(ids, data)
            if len(ids) == 1:
                invoice, = Invoice.browse(ids)
                if invoice.number:
                    result = result[:3] + (result[3] + ' - ' + invoice.number,)
            return result

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
        'account.invoice.payment.method', "Payment Method",  required=True,
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
        ('writeoff', 'Write-Off'),
        ('partial', 'Partial Payment'),
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
        cls._error_messages.update({
                'amount_greater_amount_to_pay': ('On invoice "%s" you can not '
                    'create a partial payment with an amount greater than the '
                    'amount to pay.'),
                })
        cls.__rpc__['create'].fresh_session = True

    def get_reconcile_lines_for_amount(self, invoice, amount):
        if invoice.type == 'in':
            amount *= -1
        return invoice.get_reconcile_lines_for_amount(amount)

    def default_start(self, fields):
        Invoice = Pool().get('account.invoice')
        default = {}
        invoice = Invoice(Transaction().context['active_id'])
        default['company'] = invoice.company.id
        default['currency'] = invoice.currency.id
        default['currency_digits'] = invoice.currency.digits
        default['amount'] = (invoice.amount_to_pay_today
            or invoice.amount_to_pay)
        default['invoice_account'] = invoice.account.id
        return default

    def transition_choice(self):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Currency = pool.get('currency.currency')

        invoice = Invoice(Transaction().context['active_id'])

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
        Invoice = pool.get('account.invoice')
        Currency = pool.get('currency.currency')

        default = {}
        invoice = Invoice(Transaction().context['active_id'])
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
        Invoice = pool.get('account.invoice')
        Currency = pool.get('currency.currency')
        MoveLine = pool.get('account.move.line')

        invoice = Invoice(Transaction().context['active_id'])

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

        if (amount_invoice > invoice.amount_to_pay
                and self.ask.type != 'writeoff'):
            self.raise_user_error('amount_greater_amount_to_pay',
                (invoice.rec_name,))

        line = None
        if not invoice.company.currency.is_zero(amount):
            line = invoice.pay_invoice(amount,
                self.start.payment_method, self.start.date,
                self.start.description, amount_second_currency,
                second_currency)

        if remainder != Decimal('0.0'):
            if self.ask.type == 'writeoff':
                lines = [l for l in self.ask.lines] + \
                    [l for l in invoice.payment_lines
                        if not l.reconciliation]
                if line and line not in lines:
                    # Add new payment line if payment_lines was cached before
                    # its creation
                    lines += [line]
                if lines:
                    MoveLine.reconcile(lines,
                        writeoff=self.ask.writeoff,
                        date=self.start.date)
        else:
            if line:
                reconcile_lines += [line]
            if reconcile_lines:
                MoveLine.reconcile(reconcile_lines)
        return 'end'


class CreditInvoiceStart(ModelView):
    'Credit Invoice'
    __name__ = 'account.invoice.credit.start'
    with_refund = fields.Boolean('With Refund',
        states={
            'readonly': ~Eval('with_refund_allowed'),
            },
        depends=['with_refund_allowed'],
        help='If true, the current invoice(s) will be paid.')
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

    @classmethod
    def __setup__(cls):
        super(CreditInvoice, cls).__setup__()
        cls._error_messages.update({
                'refund_non_posted': ('You can not credit with refund '
                    'invoice "%s" because it is not posted.'),
                'refund_with_payement': ('You can not credit with refund '
                    'invoice "%s" because it has payments.'),
                'refund_supplier': ('You can not credit with refund '
                    'invoice "%s" because it is a supplier '
                    'invoice/credit note.'),
                })

    def default_start(self, fields):
        Invoice = Pool().get('account.invoice')
        default = {
            'with_refund': True,
            'with_refund_allowed': True,
            }
        for invoice in Invoice.browse(Transaction().context['active_ids']):
            if (invoice.state != 'posted'
                    or invoice.payment_lines
                    or invoice.type == 'in'):
                default['with_refund'] = False
                default['with_refund_allowed'] = False
                break
        return default

    def do_credit(self, action):
        pool = Pool()
        Invoice = pool.get('account.invoice')

        refund = self.start.with_refund
        invoices = Invoice.browse(Transaction().context['active_ids'])

        if refund:
            for invoice in invoices:
                if invoice.state != 'posted':
                    self.raise_user_error('refund_non_posted',
                        (invoice.rec_name,))
                if invoice.payment_lines:
                    self.raise_user_error('refund_with_payement',
                        (invoice.rec_name,))
                if invoice.type == 'in':
                    self.raise_user_error('refund_supplier', invoice.rec_name)

        credit_invoices = Invoice.credit(invoices, refund=refund)

        data = {'res_id': [i.id for i in credit_invoices]}
        if len(credit_invoices) == 1:
            action['views'].reverse()
        return action, data
