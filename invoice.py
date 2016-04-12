# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from collections import defaultdict, namedtuple
from itertools import combinations
import base64
import itertools

from sql import Literal, Null
from sql.aggregate import Count, Sum
from sql.conditionals import Coalesce, Case
from sql.functions import Round

from trytond.model import Workflow, ModelView, ModelSQL, fields, Check
from trytond.report import Report
from trytond.wizard import Wizard, StateView, StateTransition, StateAction, \
    StateReport, Button
from trytond import backend
from trytond.pyson import If, Eval, Bool, Id
from trytond.tools import reduce_ids, grouped_slice
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.rpc import RPC

from trytond.modules.account.tax import TaxableMixin
from trytond.modules.product import price_digits

__all__ = ['Invoice', 'InvoicePaymentLine', 'InvoiceLine',
    'InvoiceLineTax', 'InvoiceTax',
    'PrintInvoiceWarning', 'PrintInvoice', 'InvoiceReport',
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
    state = fields.Selection([
        ('draft', 'Draft'),
        ('validated', 'Validated'),
        ('posted', 'Posted'),
        ('paid', 'Paid'),
        ('cancel', 'Canceled'),
        ], 'State', readonly=True)
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
    party_lang = fields.Function(fields.Char('Party Language'),
        'on_change_with_party_lang')
    invoice_address = fields.Many2One('party.address', 'Invoice Address',
        required=True, states=_STATES, depends=['state', 'party'],
        domain=[('party', '=', Eval('party'))])
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states={
            'readonly': ((Eval('state') != 'draft')
                | (Eval('lines', [0]) & Eval('currency'))),
            }, depends=['state'])
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
        'Payment Term', required=True, states=_STATES, depends=_DEPENDS)
    lines = fields.One2Many('account.invoice.line', 'invoice', 'Lines',
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        states=_STATES, depends=['state', 'currency_date', 'company'])
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
    reconciled = fields.Function(fields.Boolean('Reconciled'),
            'get_reconciled')
    lines_to_pay = fields.Function(fields.One2Many('account.move.line', None,
        'Lines to Pay'), 'get_lines_to_pay')
    payment_lines = fields.Many2Many('account.invoice-account.move.line',
        'invoice', 'line', readonly=True, string='Payment Lines',
        domain=[
            ('move.company', '=', Eval('company', -1)),
            ],
        states={
            'invisible': (Eval('state') == 'paid') | ~Eval('payment_lines'),
            },
        depends=['state', 'company'])
    amount_to_pay_today = fields.Function(fields.Numeric('Amount to Pay Today',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_amount_to_pay')
    amount_to_pay = fields.Function(fields.Numeric('Amount to Pay',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_amount_to_pay')
    invoice_report_cache = fields.Binary('Invoice Report', readonly=True)
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
        cls._error_messages.update({
                'missing_tax_line': ('Invoice "%s" has taxes defined but not '
                    'on invoice lines.\nRe-compute the invoice.'),
                'diff_tax_line': ('Invoice "%s" tax bases are different from '
                    'invoice lines.\nRe-compute the invoice.'),
                'missing_tax_line2': (
                    'Invoice "%s" has taxes on invoice lines '
                    'that are not in the invoice.\nRe-compute the invoice.'),
                'no_invoice_sequence': ('There is no invoice sequence for '
                    'invoice "%(invoice)s" on the period/fiscal year '
                    '"%(period)s".'),
                'modify_invoice': ('You can not modify invoice "%s" because '
                    'it is posted, paid or cancelled.'),
                'same_debit_account': ('The debit account on journal '
                    '"%(journal)s" is the same as invoice "%(invoice)s"\'s '
                    'account.'),
                'missing_debit_account': ('The debit account on journal "%s" '
                    'is missing.'),
                'same_credit_account': ('The credit account on journal '
                    '"%(journal)s" is the same as invoice "%(invoice)s"\'s '
                    'account.'),
                'missing_credit_account': ('The credit account on journal '
                    '"%s" is missing.'),
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
                    },
                'draft': {
                    'invisible': (~Eval('state').in_(['cancel', 'validated'])
                        | ((Eval('state') == 'cancel') & Eval('cancel_move'))),
                    'icon': If(Eval('state') == 'cancel', 'tryton-clear',
                        'tryton-go-previous'),
                    },
                'validate_invoice': {
                    'pre_validate':
                        ['OR',
                            ('invoice_date', '!=', None),
                            ('type', '!=', 'in'),
                        ],
                    'invisible': Eval('state') != 'draft',
                    },
                'post': {
                    'pre_validate':
                        ['OR',
                            ('invoice_date', '!=', None),
                            ('type', '!=', 'in'),
                        ],
                    'invisible': ~Eval('state').in_(['draft', 'validated']),
                    },
                'pay': {
                    'invisible': Eval('state') != 'posted',
                    'readonly': ~Eval('groups', []).contains(
                        Id('account', 'group_account')),
                    },
                })

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Line = pool.get('account.invoice.line')
        Tax = pool.get('account.invoice.tax')
        TableHandler = backend.get('TableHandler')
        sql_table = cls.__table__()
        line = Line.__table__()
        tax = Tax.__table__()

        super(Invoice, cls).__register__(module_name)
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        table = TableHandler(cls, module_name)

        # Migration from 1.2 invoice_date is no more required
        table.not_null_action('invoice_date', action='remove')

        # Migration from 2.0 invoice_report renamed into invoice_report_cache
        # to remove base64 encoding

        if (table.column_exist('invoice_report')
                and table.column_exist('invoice_report_cache')):
            limit = transaction.database.IN_MAX
            cursor.execute(*sql_table.select(Count(Literal(1))))
            invoice_count, = cursor.fetchone()
            for offset in range(0, invoice_count, limit):
                cursor.execute(*sql_table.select(
                        sql_table.id, sql_table.invoice_report,
                        order_by=sql_table.id,
                        limit=limit, offset=offset))
                for invoice_id, report in cursor.fetchall():
                    if report:
                        report = fields.Binary.cast(
                            base64.decodestring(bytes(report)))
                        cursor.execute(*sql_table.update(
                                columns=[sql_table.invoice_report_cache],
                                values=[report],
                                where=sql_table.id == invoice_id))
            table.drop_column('invoice_report')

        # Migration from 2.6:
        # - proforma renamed into validated
        # - open renamed into posted
        cursor.execute(*sql_table.update(
                columns=[sql_table.state],
                values=['validated'],
                where=sql_table.state == 'proforma'))
        cursor.execute(*sql_table.update(
                columns=[sql_table.state],
                values=['posted'],
                where=sql_table.state == 'open'))

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

    @classmethod
    def default_payment_term(cls):
        PaymentTerm = Pool().get('account.invoice.payment_term')
        payment_terms = PaymentTerm.search(cls.payment_term.domain)
        if len(payment_terms) == 1:
            return payment_terms[0].id

    def __get_account_payment_term(self):
        '''
        Return default account and payment term
        '''
        self.account = None
        if self.party:
            if self.type == 'out':
                self.account = self.party.account_receivable
                if self.party.customer_payment_term:
                    self.payment_term = self.party.customer_payment_term
            elif self.type == 'in':
                self.account = self.party.account_payable
                if self.party.supplier_payment_term:
                    self.payment_term = self.party.supplier_payment_term

    @fields.depends('type', 'party', 'company')
    def on_change_type(self):
        Journal = Pool().get('account.journal')
        journals = Journal.search([
                ('type', '=', _TYPE2JOURNAL.get(self.type or 'out',
                        'revenue')),
                ], limit=1)
        if journals:
            self.journal, = journals
        self.__get_account_payment_term()

    @fields.depends('party', 'payment_term', 'type', 'company')
    def on_change_party(self):
        self.invoice_address = None
        self.__get_account_payment_term()

        if self.party:
            self.invoice_address = self.party.address_get(type='invoice')

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
    def get_type_name(self, invoices, name):
        type_names = {}
        type2name = {}
        for type, name in self.fields_get(fields_names=['type']
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
            key = (tax.base_code.id if tax.base_code else None, tax.base_sign,
                tax.tax_code.id if tax.tax_code else None, tax.tax_sign,
                tax.account.id if tax.account else None,
                tax.tax.id if tax.tax else None)
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
                value = InvoiceTax.default_get(InvoiceTax._fields.keys())
                value.update(computed_taxes[key])
                taxes.append(InvoiceTax(**value))
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
        for key in result.keys():
            if key not in names:
                del result[key]
        return result

    def get_reconciled(self, name):
        if not self.lines_to_pay:
            return False
        for line in self.lines_to_pay:
            if not line.reconciliation:
                return False
        return True

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
            if invoice.type == 'in':
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
        for tax in taxes.itervalues():
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
                to_create.extend([tax for tax in computed_taxes.values()])
            else:
                tax_keys = []
                for tax in invoice.taxes:
                    if tax.manual:
                        continue
                    base_code_id = tax.base_code.id if tax.base_code else None
                    tax_code_id = tax.tax_code.id if tax.tax_code else None
                    tax_id = tax.tax.id if tax.tax else None
                    key = (base_code_id, tax.base_sign,
                        tax_code_id, tax.tax_sign,
                        tax.account.id, tax_id)
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

    def _get_move_line_invoice_line(self):
        '''
        Return list of move line values for each invoice lines
        '''
        res = []
        for line in self.lines:
            val = line.get_move_line()
            if val:
                res.extend(val)
        return res

    def _get_move_line_invoice_tax(self):
        '''
        Return list of move line values for each invoice taxes
        '''
        res = []
        for tax in self.taxes:
            val = tax.get_move_line()
            if val:
                res.extend(val)
        return res

    def _get_move_line(self, date, amount):
        '''
        Return move line
        '''
        Currency = Pool().get('currency.currency')
        res = {}
        if self.currency.id != self.company.currency.id:
            with Transaction().set_context(date=self.currency_date):
                res['amount_second_currency'] = Currency.compute(
                    self.company.currency, amount, self.currency)
            res['second_currency'] = self.currency.id
        else:
            res['amount_second_currency'] = None
            res['second_currency'] = None
        if amount <= 0:
            res['debit'], res['credit'] = -amount, 0
        else:
            res['debit'], res['credit'] = 0, amount
        if res['amount_second_currency']:
            res['amount_second_currency'] = (
                res['amount_second_currency'].copy_sign(
                    res['debit'] - res['credit']))
        res['account'] = self.account.id
        if self.account.party_required:
            res['party'] = self.party.id
        res['maturity_date'] = date
        res['description'] = self.description
        return res

    def create_move(self):
        '''
        Create account move for the invoice and return the created move
        '''
        pool = Pool()
        Move = pool.get('account.move')
        Period = pool.get('account.period')
        Date = pool.get('ir.date')

        if self.move:
            return self.move
        self.update_taxes([self], exception=True)
        move_lines = self._get_move_line_invoice_line()
        move_lines += self._get_move_line_invoice_tax()

        total = Decimal('0.0')
        total_currency = Decimal('0.0')
        for line in move_lines:
            total += line['debit'] - line['credit']
            if line['amount_second_currency']:
                total_currency += line['amount_second_currency']

        term_lines = self.payment_term.compute(total, self.company.currency,
            self.invoice_date)
        remainder_total_currency = total_currency
        if not term_lines:
            term_lines = [(Date.today(), total)]
        for date, amount in term_lines:
            val = self._get_move_line(date, amount)
            if val['amount_second_currency']:
                remainder_total_currency += val['amount_second_currency']
            move_lines.append(val)
        if not self.currency.is_zero(remainder_total_currency):
            move_lines[-1]['amount_second_currency'] -= \
                remainder_total_currency

        accounting_date = self.accounting_date or self.invoice_date
        period_id = Period.find(self.company.id, date=accounting_date)

        move, = Move.create([{
                    'journal': self.journal.id,
                    'period': period_id,
                    'date': accounting_date,
                    'origin': str(self),
                    'company': self.company.id,
                    'lines': [('create', move_lines)],
                    }])
        self.write([self], {
                'move': move.id,
                })
        return move

    def set_number(self):
        '''
        Set number to the invoice
        '''
        pool = Pool()
        Period = pool.get('account.period')
        Sequence = pool.get('ir.sequence.strict')
        Date = pool.get('ir.date')

        if self.number:
            return

        test_state = True
        if self.type == 'in':
            test_state = False

        accounting_date = self.accounting_date or self.invoice_date
        period_id = Period.find(self.company.id,
            date=accounting_date, test_state=test_state)
        period = Period(period_id)
        invoice_type = self.type
        if all(l.amount <= 0 for l in self.lines):
            invoice_type += '_credit_note'
        else:
            invoice_type += '_invoice'
        sequence = period.get_invoice_sequence(invoice_type)
        if not sequence:
            self.raise_user_error('no_invoice_sequence', {
                    'invoice': self.rec_name,
                    'period': period.rec_name,
                    })
        with Transaction().set_context(
                date=self.invoice_date or Date.today()):
            number = Sequence.get_id(sequence.id)
            vals = {'number': number}
            if not self.invoice_date and self.type == 'out':
                vals['invoice_date'] = Transaction().context['date']
        self.write([self], vals)

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
        return (self.number or unicode(self.id)
            + (self.reference and (' ' + self.reference) or '')
            + ' ' + self.party.rec_name)

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
        return ', '.join(set(itertools.ifilter(None,
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
        default = default.copy()
        default['state'] = 'draft'
        default['number'] = None
        default['move'] = None
        default['cancel_move'] = None
        default['invoice_report_cache'] = None
        default['invoice_report_format'] = None
        default['payment_lines'] = None
        default.setdefault('invoice_date', None)
        default.setdefault('accounting_date', None)
        default['lines_to_pay'] = None
        return super(Invoice, cls).copy(invoices, default=default)

    @classmethod
    def validate(cls, invoices):
        super(Invoice, cls).validate(invoices)
        for invoice in invoices:
            invoice.check_same_account()
            invoice.check_cancel_move()

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

    def get_reconcile_lines_for_amount(self, amount):
        '''
        Return list of lines and the remainder to make reconciliation.
        '''
        Result = namedtuple('Result', ['lines', 'remainder'])

        lines = [l for l in self.payment_lines + self.lines_to_pay
            if not l.reconciliation]

        best = Result([], self.total_amount)
        for n in xrange(len(lines), 0, -1):
            for comb_lines in combinations(lines, n):
                remainder = sum((l.debit - l.credit) for l in comb_lines)
                remainder -= amount
                result = Result(list(comb_lines), remainder)
                if self.currency.is_zero(remainder):
                    return result
                if abs(remainder) < abs(best.remainder):
                    best = result
        return result

    def pay_invoice(self, amount, journal, date, description,
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

        line1 = Line(description=description, account=self.account)
        line2 = Line(description=description)
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
                line1.debit, line2.credit = 0, -amount

        line2.debit, line2.credit = line1.credit, line1.debit
        if line2.debit:
            account_journal = 'debit_account'
        else:
            account_journal = 'credit_account'
        line2.account = getattr(journal, account_journal)
        if self.account == line2.account:
            self.raise_user_error('same_%s' % account_journal, {
                    'journal': journal.rec_name,
                    'invoice': self.rec_name,
                    })
        if not line2.account:
            self.raise_user_error('missing_%s' % account_journal,
                (journal.rec_name,))

        for line in lines:
            if line.account.party_required:
                line.party = self.party
            if amount_second_currency:
                line.amount_second_currency = amount_second_currency.copy_sign(
                    line.debit - line.credit)
                line.second_currency = second_currency

        period_id = Period.find(self.company.id, date=date)

        move = Move(journal=journal, period=period_id, date=date,
            company=self.company, lines=lines)
        move.save()
        Move.post([move])

        for line in move.lines:
            if line.account == self.account:
                self.write([self], {
                        'payment_lines': [('add', [line.id])],
                        })
                return line
        raise Exception('Missing account')

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
        res = {}
        for field in ('type', 'description', 'comment'):
            res[field] = getattr(self, field)

        for field in ('company', 'party', 'invoice_address', 'currency',
                'journal', 'account', 'payment_term'):
            res[field] = getattr(self, field).id

        res['lines'] = []
        if self.lines:
            res['lines'].append(('create',
                    [line._credit() for line in self.lines]))

        res['taxes'] = []
        to_create = [tax._credit() for tax in self.taxes if tax.manual]
        if to_create:
            res['taxes'].append(('create', to_create))
        return res

    @classmethod
    def credit(cls, invoices, refund=False):
        '''
        Credit invoices and return ids of new invoices.
        Return the list of new invoice
        '''
        MoveLine = Pool().get('account.move.line')

        new_invoices = []
        for invoice in invoices:
            new_invoice, = cls.create([invoice._credit()])
            new_invoices.append(new_invoice)
            if refund:
                cls.post([new_invoice])
                if new_invoice.state == 'posted':
                    MoveLine.reconcile([l for l in invoice.lines_to_pay
                            if not l.reconciliation] +
                        [l for l in new_invoice.lines_to_pay
                            if not l.reconciliation])
        cls.update_taxes(new_invoices)
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
        for invoice in invoices:
            if invoice.type == 'in':
                invoice.set_number()
                invoice.create_move()

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, invoices):
        Move = Pool().get('account.move')

        moves = []
        for invoice in invoices:
            invoice.set_number()
            moves.append(invoice.create_move())
        cls.write([i for i in invoices if i.state != 'posted'], {
                'state': 'posted',
                })
        Move.post([m for m in moves if m.state != 'posted'])
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
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, invoices):
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')

        cancel_moves = []
        delete_moves = []
        for invoice in invoices:
            if invoice.move:
                if invoice.move.state == 'draft':
                    delete_moves.append(invoice.move)
                elif not invoice.cancel_move:
                    invoice.cancel_move = invoice.move.cancel()
                    invoice.save()
                    cancel_moves.append(invoice.cancel_move)
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
    line = fields.Many2One('account.move.line', 'Payment Line',
            ondelete='CASCADE', select=True, required=True)


class InvoiceLine(ModelSQL, ModelView, TaxableMixin):
    'Invoice Line'
    __name__ = 'account.invoice.line'
    _rec_name = 'description'
    invoice = fields.Many2One('account.invoice', 'Invoice', ondelete='CASCADE',
        select=True, states={
            'required': (~Eval('invoice_type') & Eval('party')
                & Eval('currency') & Eval('company')),
            'invisible': Bool(Eval('context', {}).get('standalone')),
            },
        depends=['invoice_type', 'party', 'company', 'currency'])
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
            },
        depends=['invoice'])
    party_lang = fields.Function(fields.Char('Party Language'),
        'on_change_with_party_lang')
    currency = fields.Many2One('currency.currency', 'Currency',
        states={
            'required': ~Eval('invoice'),
            },
        depends=['invoice'])
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    company = fields.Many2One('company.company', 'Company', required=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ], select=True)
    sequence = fields.Integer('Sequence',
        states={
            'invisible': Bool(Eval('context', {}).get('standalone')),
            })
    type = fields.Selection([
        ('line', 'Line'),
        ('subtotal', 'Subtotal'),
        ('title', 'Title'),
        ('comment', 'Comment'),
        ], 'Type', select=True, required=True, states={
            'invisible': Bool(Eval('context', {}).get('standalone')),
        })
    quantity = fields.Float('Quantity',
        digits=(16, Eval('unit_digits', 2)),
        states={
            'invisible': Eval('type') != 'line',
            'required': Eval('type') == 'line',
            },
        depends=['type', 'unit_digits'])
    unit = fields.Many2One('product.uom', 'Unit', ondelete='RESTRICT',
        states={
            'required': Bool(Eval('product')),
            'invisible': Eval('type') != 'line',
            },
        domain=[
            If(Bool(Eval('product_uom_category')),
                ('category', '=', Eval('product_uom_category')),
                ('category', '!=', -1)),
            ],
        depends=['product', 'type', 'product_uom_category'])
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
        'on_change_with_unit_digits')
    product = fields.Many2One('product.product', 'Product',
        ondelete='RESTRICT',
        states={
            'invisible': Eval('type') != 'line',
            },
        depends=['type'])
    product_uom_category = fields.Function(
        fields.Many2One('product.uom.category', 'Product Uom Category'),
        'on_change_with_product_uom_category')
    account = fields.Many2One('account.account', 'Account',
        ondelete='RESTRICT',
        states={
            'invisible': Eval('type') != 'line',
            'required': Eval('type') == 'line',
            },
        depends=['type', 'invoice_type', 'company'])
    unit_price = fields.Numeric('Unit Price', digits=price_digits,
        states={
            'invisible': Eval('type') != 'line',
            'required': Eval('type') == 'line',
            },
        depends=['type'])
    amount = fields.Function(fields.Numeric('Amount',
            digits=(16, Eval('_parent_invoice', {}).get('currency_digits',
                    Eval('currency_digits', 2))),
            states={
                'invisible': ~Eval('type').in_(['line', 'subtotal']),
                },
            depends=['type', 'currency_digits']), 'get_amount')
    description = fields.Text('Description', size=None, required=True)
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
            },
        depends=['type', 'invoice_type', 'company'])
    invoice_taxes = fields.Function(fields.One2Many('account.invoice.tax',
        None, 'Invoice Taxes'), 'get_invoice_taxes')
    origin = fields.Reference('Origin', selection='get_origin', select=True,
        states={
            'readonly': Eval('_parent_invoice', {}
                ).get('state') != 'draft',
            })

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
        cls._order.insert(0, ('sequence', 'ASC'))
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
        TableHandler = backend.get('TableHandler')
        sql_table = cls.__table__()
        super(InvoiceLine, cls).__register__(module_name)
        cursor = Transaction().connection.cursor()
        table = TableHandler(cls, module_name)

        # Migration from 1.0 invoice is no more required
        table.not_null_action('invoice', action='remove')

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')

        # Migration from 3.4: company is required
        cursor.execute(*sql_table.join(invoice,
                condition=sql_table.invoice == invoice.id
                ).select(sql_table.id, invoice.company,
                where=sql_table.company == Null))
        for line_id, company_id in cursor.fetchall():
            cursor.execute(*sql_table.update([sql_table.company], [company_id],
                    where=sql_table.id == line_id))

    @staticmethod
    def order_sequence(tables):
        table, _ = tables[None]
        return [Case((table.sequence == Null, 0), else_=1), table.sequence]

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

    @fields.depends('type', 'quantity', 'unit_price',
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
        taxes_keys = self._get_taxes().keys()
        taxes = []
        for tax in self.invoice.taxes:
            if tax.manual:
                continue
            base_code_id = tax.base_code.id if tax.base_code else None
            tax_code_id = tax.tax_code.id if tax.tax_code else None
            tax_id = tax.tax.id if tax.tax else None
            key = (base_code_id, tax.base_sign,
                tax_code_id, tax.tax_sign,
                tax.account.id, tax_id)
            if key in taxes_keys:
                taxes.append(tax.id)
        return taxes

    def _get_tax_rule_pattern(self):
        '''
        Get tax rule pattern
        '''
        return {}

    @fields.depends('product', 'unit', 'description', '_parent_invoice.type',
        '_parent_invoice.party', 'party', 'invoice', 'invoice_type')
    def on_change_product(self):
        pool = Pool()
        Product = pool.get('product.product')

        if not self.product:
            return

        context = {}
        party = None
        if self.invoice and self.invoice.party:
            party = self.invoice.party
        elif self.party:
            party = self.party
        if party and party.lang:
            context['language'] = party.lang.code

        if self.invoice and self.invoice.type:
            type_ = self.invoice.type
        else:
            type_ = self.invoice_type
        if type_ == 'in':
            try:
                self.account = self.product.account_expense_used
            except Exception:
                pass
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
            try:
                self.account = self.product.account_revenue_used
            except Exception:
                pass
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

        if not self.description:
            with Transaction().set_context(**context):
                self.description = Product(self.product.id).rec_name

        category = self.product.default_uom.category
        if not self.unit or self.unit not in category.uoms:
            self.unit = self.product.default_uom.id
            self.unit_digits = self.product.default_uom.digits

    @fields.depends('product')
    def on_change_with_product_uom_category(self, name=None):
        if self.product:
            return self.product.default_uom_category.id

    @fields.depends('account', 'product', '_parent_invoice.party',
        '_parent_invoice.type')
    def on_change_account(self):
        if self.product:
            return
        taxes = []
        if (self.invoice and self.invoice.party
                and self.invoice.type):
            party = self.invoice.party
            if self.invoice.type == 'in':
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

        res = []
        if self.type != 'line':
            return res
        taxes = self._get_taxes().values()
        for tax in taxes:
            if tax['base'] >= 0:
                base_code = tax['base_code']
                amount = tax['base'] * tax['base_sign']
            else:
                base_code = tax['base_code']
                amount = tax['base'] * tax['base_sign']
            if base_code:
                with Transaction().set_context(
                        date=self.invoice.currency_date):
                    amount = Currency.compute(self.invoice.currency,
                        amount, self.invoice.company.currency)
                res.append({
                        'code': base_code,
                        'amount': amount,
                        'tax': tax['tax'],
                        })
        return res

    def get_move_line(self):
        '''
        Return a list of move lines values for invoice line
        '''
        Currency = Pool().get('currency.currency')
        res = {}
        if self.type != 'line':
            return []
        res['description'] = self.description
        if self.invoice.currency != self.invoice.company.currency:
            with Transaction().set_context(date=self.invoice.currency_date):
                amount = Currency.compute(self.invoice.currency,
                    self.amount, self.invoice.company.currency)
            res['amount_second_currency'] = self.amount
            res['second_currency'] = self.invoice.currency.id
        else:
            amount = self.amount
            res['amount_second_currency'] = None
            res['second_currency'] = None
        if amount >= 0:
            if self.invoice.type == 'out':
                res['debit'], res['credit'] = 0, amount
            else:
                res['debit'], res['credit'] = amount, 0
        else:
            if self.invoice.type == 'out':
                res['debit'], res['credit'] = -amount, 0
            else:
                res['debit'], res['credit'] = 0, -amount
        if res['amount_second_currency']:
            res['amount_second_currency'] = (
                res['amount_second_currency'].copy_sign(
                    res['debit'] - res['credit']))
        res['account'] = self.account.id
        if self.account.party_required:
            res['party'] = self.invoice.party.id
        computed_taxes = self._compute_taxes()
        if computed_taxes:
            res['tax_lines'] = [('create', [tax for tax in computed_taxes])]
        return [res]

    def _credit(self):
        '''
        Return values to credit line.
        '''
        res = {}
        res['origin'] = str(self)
        res['quantity'] = -self.quantity

        for field in ('sequence', 'type', 'invoice_type', 'unit_price',
                'description'):
            res[field] = getattr(self, field)

        for field in ('unit', 'product', 'account'):
            res[field] = getattr(getattr(self, field), 'id', None)

        res['taxes'] = []
        if self.taxes:
            res['taxes'].append(('add', [tax.id for tax in self.taxes]))
        return res


class InvoiceLineTax(ModelSQL):
    'Invoice Line - Tax'
    __name__ = 'account.invoice.line-account.tax'
    _table = 'account_invoice_line_account_tax'
    line = fields.Many2One('account.invoice.line', 'Invoice Line',
            ondelete='CASCADE', select=True, required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
            required=True)


class InvoiceTax(ModelSQL, ModelView):
    'Invoice Tax'
    __name__ = 'account.invoice.tax'
    _rec_name = 'description'
    invoice = fields.Many2One('account.invoice', 'Invoice', ondelete='CASCADE',
            select=True)
    description = fields.Char('Description', size=None, required=True)
    sequence = fields.Integer('Sequence')
    sequence_number = fields.Function(fields.Integer('Sequence Number'),
            'get_sequence_number')
    account = fields.Many2One('account.account', 'Account', required=True,
        domain=[
            ('kind', '!=', 'view'),
            ('company', '=', Eval('_parent_invoice', {}).get('company', 0)),
            ])
    base = fields.Numeric('Base', required=True,
        digits=(16, Eval('_parent_invoice', {}).get('currency_digits', 2)))
    amount = fields.Numeric('Amount', required=True,
        digits=(16, Eval('_parent_invoice', {}).get('currency_digits', 2)),
        depends=['tax', 'base', 'manual'])
    manual = fields.Boolean('Manual')
    base_code = fields.Many2One('account.tax.code', 'Base Code',
        domain=[
            ('company', '=', Eval('_parent_invoice', {}).get('company', 0)),
            ])
    base_sign = fields.Numeric('Base Sign', digits=(2, 0), required=True)
    tax_code = fields.Many2One('account.tax.code', 'Tax Code',
        domain=[
            ('company', '=', Eval('_parent_invoice', {}).get('company', 0)),
            ])
    tax_sign = fields.Numeric('Tax Sign', digits=(2, 0), required=True)
    tax = fields.Many2One('account.tax', 'Tax',
        ondelete='RESTRICT',
        domain=[
            ('company', '=', Eval('_parent_invoice', {}).get('company', 0)),
            ],
        states={
            'readonly': ~Eval('manual', False),
            },
        depends=['manual'])

    @classmethod
    def __setup__(cls):
        super(InvoiceTax, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))
        cls._error_messages.update({
                'modify': ('You can not modify tax "%(tax)s" from invoice '
                    '"%(invoice)s" because it is posted or paid.'),
                'create': ('You can not add tax to invoice '
                    '"%(invoice)s" because it is posted, paid or canceled.'),
                'invalid_base_code_company': ('You can not create invoice '
                    '"%(invoice)s" on company "%(invoice_company)s" '
                    'using base tax code "%(base_code)s" from company '
                    '"%(base_code_company)s".'),
                'invalid_tax_code_company': ('You can not create invoice '
                    '"%(invoice)s" on company "%(invoice_company)s" using tax '
                    'code "%(tax_code)s" from company '
                    '"%(tax_code_company)s".'),
                })

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        table = TableHandler(cls, module_name)

        super(InvoiceTax, cls).__register__(module_name)

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')

    @staticmethod
    def order_sequence(tables):
        table, _ = tables[None]
        return [Case((table.sequence == Null, 0), else_=1), table.sequence]

    @staticmethod
    def default_base():
        return Decimal('0.0')

    @staticmethod
    def default_amount():
        return Decimal('0.0')

    @staticmethod
    def default_manual():
        return True

    @staticmethod
    def default_base_sign():
        return Decimal('1')

    @staticmethod
    def default_tax_sign():
        return Decimal('1')

    @fields.depends('tax', '_parent_invoice.party', 'base')
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
            self.base_code = tax.invoice_base_code
            self.base_sign = tax.invoice_base_sign
            self.tax_code = tax.invoice_tax_code
            self.tax_sign = tax.invoice_tax_sign
            self.account = tax.invoice_account
        else:
            self.base_code = tax.credit_note_base_code
            self.base_sign = tax.credit_note_base_sign
            self.tax_code = tax.credit_note_tax_code
            self.tax_sign = tax.credit_note_tax_sign
            self.account = tax.credit_note_account

    @fields.depends('tax', 'base', 'amount', 'manual',
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

    def get_move_line(self):
        '''
        Return a list of move lines values for invoice tax
        '''
        Currency = Pool().get('currency.currency')
        res = {}
        if not self.amount:
            return []
        res['description'] = self.description
        if self.invoice.currency != self.invoice.company.currency:
            with Transaction().set_context(date=self.invoice.currency_date):
                amount = Currency.compute(self.invoice.currency, self.amount,
                    self.invoice.company.currency)
            res['amount_second_currency'] = self.amount
            res['second_currency'] = self.invoice.currency.id
        else:
            amount = self.amount
            res['amount_second_currency'] = None
            res['second_currency'] = None
        if amount >= 0:
            if self.invoice.type == 'out':
                res['debit'], res['credit'] = 0, amount
            else:
                res['debit'], res['credit'] = amount, 0
        else:
            if self.invoice.type == 'out':
                res['debit'], res['credit'] = -amount, 0
            else:
                res['debit'], res['credit'] = 0, -amount
        if res['amount_second_currency']:
            res['amount_second_currency'] = (
                res['amount_second_currency'].copy_sign(
                    res['debit'] - res['credit']))
        res['account'] = self.account.id
        if self.account.party_required:
            res['party'] = self.invoice.party.id
        if self.tax_code:
            res['tax_lines'] = [('create', [{
                            'code': self.tax_code.id,
                            'amount': amount * self.tax_sign,
                            'tax': self.tax and self.tax.id or None
                            }])]
        return [res]

    def _credit(self):
        '''
        Return values to credit tax.
        '''
        res = {}
        res['base'] = -self.base
        res['amount'] = -self.amount

        for field in ('description', 'sequence', 'manual', 'base_sign',
                'tax_sign'):
            res[field] = getattr(self, field)

        for field in ('account', 'base_code', 'tax_code', 'tax'):
            res[field] = getattr(self, field).id
        return res


class PrintInvoiceWarning(ModelView):
    'Print Invoice Report Warning'
    __name__ = 'account.invoice.print.warning'


class PrintInvoice(Wizard):
    'Print Invoice Report'
    __name__ = 'account.invoice.print'
    start = StateTransition()
    warning = StateView('account.invoice.print.warning',
        'account_invoice.print_warning_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateReport('account.invoice')

    def transition_start(self):
        if len(Transaction().context['active_ids']) > 1:
            return 'warning'
        return 'print_'

    def do_print_(self, action):
        data = {}
        data['id'] = Transaction().context['active_ids'].pop()
        data['ids'] = [data['id']]
        return action, data

    def transition_print_(self):
        if Transaction().context['active_ids']:
            return 'print_'
        return 'end'


class InvoiceReport(Report):
    __name__ = 'account.invoice'

    @classmethod
    def __setup__(cls):
        super(InvoiceReport, cls).__setup__()
        cls.__rpc__['execute'] = RPC(False)

    @classmethod
    def execute(cls, ids, data):
        Invoice = Pool().get('account.invoice')

        result = super(InvoiceReport, cls).execute(ids, data)
        invoice = Invoice(ids[0])

        if len(ids) > 1:
            result = result[:2] + (True,) + result[3:]
        else:
            if invoice.number:
                result = result[:3] + (result[3] + ' - ' + invoice.number,)

        if invoice.invoice_report_cache:
            result = (invoice.invoice_report_format,
                invoice.invoice_report_cache) + result[2:]
        else:
            # If the invoice is posted or paid and the report not saved in
            # invoice_report_cache there was an error somewhere. So we save it
            # now in invoice_report_cache
            if invoice.state in {'posted', 'paid'} and invoice.type == 'out':
                invoice.invoice_report_format, invoice.invoice_report_cache = \
                    result[:2]
                invoice.save()
        return result

    @classmethod
    def _get_records(cls, ids, model, data):
        with Transaction().set_context(language=False):
            return super(InvoiceReport, cls)._get_records(ids[:1], model, data)

    @classmethod
    def get_context(cls, records, data):
        report_context = super(InvoiceReport, cls).get_context(records, data)
        report_context['company'] = report_context['user'].company
        return report_context


class PayInvoiceStart(ModelView):
    'Pay Invoice'
    __name__ = 'account.invoice.pay.start'
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'], required=True)
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    currency_digits = fields.Integer('Currency Digits', readonly=True)
    description = fields.Char('Description', size=None)
    journal = fields.Many2One('account.journal', 'Journal', required=True,
            domain=[('type', '=', 'cash')])
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
    journal_writeoff = fields.Many2One('account.journal', 'Write-Off Journal',
        domain=[
            ('type', '=', 'write-off'),
            ],
        states={
            'invisible': Eval('type') != 'writeoff',
            'required': Eval('type') == 'writeoff',
            }, depends=['type'])
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

    @staticmethod
    def default_type():
        return 'partial'

    @fields.depends('lines', 'amount', 'currency', 'currency_writeoff',
        'invoice', 'payment_lines')
    def on_change_lines(self):
        Currency = Pool().get('currency.currency')

        with Transaction().set_context(date=self.invoice.currency_date):
            amount = Currency.compute(self.currency, self.amount,
                self.currency_writeoff)

        self.amount_writeoff = Decimal('0.0')
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

    def get_reconcile_lines_for_amount(self, invoice, amount):
        if invoice.type == 'in':
            amount *= -1
        return invoice.get_reconcile_lines_for_amount(amount)

    def default_start(self, fields):
        Invoice = Pool().get('account.invoice')
        default = {}
        invoice = Invoice(Transaction().context['active_id'])
        default['currency'] = invoice.currency.id
        default['currency_digits'] = invoice.currency.digits
        default['amount'] = (invoice.amount_to_pay_today
            or invoice.amount_to_pay)
        default['description'] = invoice.number
        return default

    def transition_choice(self):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Currency = pool.get('currency.currency')

        invoice = Invoice(Transaction().context['active_id'])

        with Transaction().set_context(date=self.start.date):
            amount = Currency.compute(self.start.currency,
                self.start.amount, invoice.company.currency)
        _, remainder = self.get_reconcile_lines_for_amount(invoice, amount)
        if remainder == Decimal('0.0') and amount <= invoice.amount_to_pay:
            return 'pay'
        return 'ask'

    def default_ask(self, fields):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Currency = pool.get('currency.currency')
        Line = pool.get('account.move.line')

        default = {}
        invoice = Invoice(Transaction().context['active_id'])
        default['lines_to_pay'] = [x.id for x in invoice.lines_to_pay
                if not x.reconciliation]

        default['amount'] = self.start.amount
        default['currency'] = self.start.currency.id
        default['currency_digits'] = self.start.currency_digits
        default['company'] = invoice.company.id

        with Transaction().set_context(date=self.start.date):
            amount = Currency.compute(self.start.currency,
                self.start.amount, invoice.company.currency)

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

        default['amount_writeoff'] = Decimal('0.0')
        for line in Line.browse(default['lines']):
            default['amount_writeoff'] += line.debit - line.credit
        for line in Line.browse(default['payment_lines']):
            default['amount_writeoff'] += line.debit - line.credit
        if invoice.type == 'in':
            default['amount_writeoff'] = - default['amount_writeoff'] - amount
        else:
            default['amount_writeoff'] = default['amount_writeoff'] - amount

        default['currency_writeoff'] = invoice.company.currency.id
        default['currency_digits_writeoff'] = invoice.company.currency.digits
        default['invoice'] = invoice.id

        if (amount > invoice.amount_to_pay
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

        reconcile_lines, remainder = \
            self.get_reconcile_lines_for_amount(invoice, amount)

        amount_second_currency = None
        second_currency = None
        if self.start.currency != invoice.company.currency:
            amount_second_currency = self.start.amount
            second_currency = self.start.currency

        if (abs(amount) > abs(invoice.amount_to_pay)
                and self.ask.type != 'writeoff'):
            self.raise_user_error('amount_greater_amount_to_pay',
                (invoice.rec_name,))

        line = None
        if not invoice.company.currency.is_zero(amount):
            line = invoice.pay_invoice(amount,
                self.start.journal, self.start.date,
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
                        journal=self.ask.journal_writeoff,
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
        help='If true, the current invoice(s) will be paid.')


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
            }
        for invoice in Invoice.browse(Transaction().context['active_ids']):
            if (invoice.state != 'posted'
                    or invoice.payment_lines
                    or invoice.type == 'in'):
                default['with_refund'] = False
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
