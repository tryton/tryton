#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
import base64
import operator
from trytond.model import Workflow, ModelView, ModelSQL, fields
from trytond.report import Report
from trytond.wizard import Wizard, StateView, StateTransition, StateAction, \
    Button
from trytond.backend import TableHandler, FIELDS
from trytond.pyson import If, Eval, Bool, Id
from trytond.tools import reduce_ids
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.rpc import RPC

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
    ('out_invoice', 'Invoice'),
    ('in_invoice', 'Supplier Invoice'),
    ('out_credit_note', 'Credit Note'),
    ('in_credit_note', 'Supplier Credit Note'),
]

_TYPE2JOURNAL = {
    'out_invoice': 'revenue',
    'in_invoice': 'expense',
    'out_credit_note': 'revenue',
    'in_credit_note': 'expense',
}

_ZERO = Decimal('0.0')


class Invoice(Workflow, ModelSQL, ModelView):
    'Invoice'
    __name__ = 'account.invoice'
    _order_name = 'number'
    company = fields.Many2One('company.company', 'Company', required=True,
        states=_STATES, select=True, domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', 0)),
            ],
        depends=_DEPENDS)
    type = fields.Selection(_TYPE, 'Type', select=True, on_change=['type',
            'party', 'company'],
        required=True, states={
            'readonly': ((Eval('state') != 'draft')
                | Eval('context', {}).get('type')
                | (Eval('lines') & Eval('type'))),
            }, depends=['state', 'lines'])
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
                If(Eval('type').in_(['in_invoice', 'in_credit_note']),
                    ['validated', 'posted', 'paid'],
                    ['posted', 'paid'])),
            },
        depends=['state'])
    accounting_date = fields.Date('Accounting Date', states=_STATES,
        depends=_DEPENDS)
    party = fields.Many2One('party.party', 'Party',
        required=True, states=_STATES, depends=_DEPENDS,
        on_change=['party', 'payment_term', 'type', 'company'])
    party_lang = fields.Function(fields.Char('Party Language',
        on_change_with=['party']), 'on_change_with_party_lang')
    invoice_address = fields.Many2One('party.address', 'Invoice Address',
        required=True, states=_STATES, depends=['state', 'party'],
        domain=[('party', '=', Eval('party'))])
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states={
            'readonly': ((Eval('state') != 'draft')
                | (Eval('lines') & Eval('currency'))),
            }, depends=['state', 'lines'])
    currency_digits = fields.Function(fields.Integer('Currency Digits',
        on_change_with=['currency']), 'on_change_with_currency_digits')
    currency_date = fields.Function(fields.Date('Currency Date',
        on_change_with=['invoice_date']), 'on_change_with_currency_date',)
    journal = fields.Many2One('account.journal', 'Journal', required=True,
        states=_STATES, depends=_DEPENDS, domain=[('centralised', '=', False)])
    move = fields.Many2One('account.move', 'Move', readonly=True)
    cancel_move = fields.Many2One('account.move', 'Cancel Move', readonly=True,
        states={
            'invisible': Eval('type').in_(['out_invoice', 'out_credit_note']),
            })
    account = fields.Many2One('account.account', 'Account', required=True,
        states=_STATES, depends=_DEPENDS + ['type'],
        domain=[
            ('company', '=', Eval('context', {}).get('company', 0)),
            If(Eval('type').in_(['out_invoice', 'out_credit_note']),
                ('kind', '=', 'receivable'),
                ('kind', '=', 'payable')),
            ])
    payment_term = fields.Many2One('account.invoice.payment_term',
        'Payment Term', required=True, states=_STATES, depends=_DEPENDS)
    lines = fields.One2Many('account.invoice.line', 'invoice', 'Lines',
        states=_STATES, on_change=[
            'lines', 'taxes', 'currency', 'party', 'type'
        ], depends=['state', 'currency_date'])
    taxes = fields.One2Many('account.invoice.tax', 'invoice', 'Tax Lines',
        states=_STATES, depends=_DEPENDS,
        on_change=['lines', 'taxes', 'currency', 'party', 'type'])
    comment = fields.Text('Comment', states=_STATES, depends=_DEPENDS)
    untaxed_amount = fields.Function(fields.Numeric('Untaxed',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_untaxed_amount', searcher='search_untaxed_amount')
    tax_amount = fields.Function(fields.Numeric('Tax', digits=(16,
                Eval('currency_digits', 2)), depends=['currency_digits']),
        'get_tax_amount', searcher='search_tax_amount')
    total_amount = fields.Function(fields.Numeric('Total', digits=(16,
                Eval('currency_digits', 2)), depends=['currency_digits']),
        'get_total_amount', searcher='search_total_amount')
    reconciled = fields.Function(fields.Boolean('Reconciled'),
            'get_reconciled')
    lines_to_pay = fields.Function(fields.One2Many('account.move.line', None,
        'Lines to Pay'), 'get_lines_to_pay')
    payment_lines = fields.Many2Many('account.invoice-account.move.line',
            'invoice', 'line', readonly=True, string='Payment Lines')
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
        cls._order.insert(0, ('number', 'DESC'))
        cls._order.insert(1, ('id', 'DESC'))
        cls._error_messages.update({
                'missing_tax_line': ('Invoice "%s" has taxes defined but not '
                    'on invoice lines.\nRe-compute the invoice.'),
                'diff_tax_line': ('Invoice "%s" tax bases are different from '
                    'invoice lines.\nRe-compute the invoice.'),
                'missing_tax_line2': ('Invoice "%s" has taxes on invoice lines '
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
                'missing_credit_account': ('The credit account on journal %s" '
                    'is missing.'),
                'account_different_company': ('You can not create invoice '
                    '"%(invoice)s" on company "%(invoice_company)s because '
                    'account "%(account)s has a different company '
                    '(%(account_company)s.)'),
                'same_account_on_line': ('Invoice "%(invoice)s" uses the same '
                    'account "%(account)s" for the invoice and in line '
                    '"%(line)s".'),
                'delete_cancel': ('Invoice "%s" must be cancelled before '
                    'deletion.'),
                'delete_numbered': ('The numbered invoice "%s" can not be '
                    'deleted.'),
                'period_cancel_move': ('The period of Invoice "%s" is closed.\n'
                    'Use the today for cancel move?'),
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
                            & Eval('type').in_(
                                ['in_invoice', 'in_credit_note']))),
                    },
                'draft': {
                    'invisible': (~Eval('state').in_(['cancel', 'validated'])
                        | ((Eval('state') == 'cancel') & Eval('cancel_move'))),
                    'icon': If(Eval('state') == 'cancel', 'tryton-clear',
                        'tryton-go-previous'),
                    },
                'validate_invoice': {
                    'invisible': Eval('state') != 'draft',
                    },
                'post': {
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
        super(Invoice, cls).__register__(module_name)
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

        # Migration from 1.2 invoice_date is no more required
        table.not_null_action('invoice_date', action='remove')

        # Migration from 2.0 invoice_report renamed into invoice_report_cache
        # to remove base64 encoding

        if (table.column_exist('invoice_report')
                and table.column_exist('invoice_report_cache')):
            limit = cursor.IN_MAX
            cursor.execute('SELECT COUNT(id) '
                'FROM "' + cls._table + '"')
            invoice_count, = cursor.fetchone()
            for offset in range(0, invoice_count, limit):
                cursor.execute(cursor.limit_clause(
                    'SELECT id, invoice_report '
                    'FROM "' + cls._table + '"'
                    'ORDER BY id',
                    limit, offset))
                for invoice_id, report in cursor.fetchall():
                    if report:
                        report = buffer(base64.decodestring(str(report)))
                        cursor.execute('UPDATE "' + cls._table + '" '
                            'SET invoice_report_cache = %s '
                            'WHERE id = %s', (report, invoice_id))
            table.drop_column('invoice_report')

        # Migration from 2.6:
        # - proforma renamed into validated
        # - open renamed into posted
        cursor.execute('UPDATE "' + cls._table + '" '
            'SET state = %s WHERE state = %s', ('validated', 'proforma'))
        cursor.execute('UPDATE "' + cls._table + '" '
            'SET state = %s WHERE state = %s', ('posted', 'open'))

        # Add index on create_date
        table.index_action('create_date', action='add')

    @staticmethod
    def default_type():
        return Transaction().context.get('type', 'out_invoice')

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
        account = None
        payment_term = None
        result = {
            'account': None,
            }
        if self.party:
            if self.type in ('out_invoice', 'out_credit_note'):
                account = self.party.account_receivable
                if (self.type == 'out_invoice'
                        and self.party.customer_payment_term):
                    payment_term = self.party.customer_payment_term
            elif self.type in ('in_invoice', 'in_credit_note'):
                account = self.party.account_payable
                if (self.type == 'in_invoice'
                        and self.party.supplier_payment_term):
                    payment_term = self.party.supplier_payment_term
        if self.company and self.type in ('out_credit_note', 'in_credit_note'):
            if self.type == 'out_credit_note':
                payment_term = self.company.party.customer_payment_term
            else:
                payment_term = self.company.party.supplier_payment_term
        if account:
            result['account'] = account.id
            result['account.rec_name'] = account.rec_name
        if payment_term:
            result['payment_term'] = payment_term.id
            result['payment_term.rec_name'] = payment_term.rec_name
        return result

    def on_change_type(self):
        Journal = Pool().get('account.journal')
        res = {}
        journals = Journal.search([
                ('type', '=', _TYPE2JOURNAL.get(self.type or 'out_invoice',
                        'revenue')),
                ], limit=1)
        if journals:
            journal, = journals
            res['journal'] = journal.id
            res['journal.rec_name'] = journal.rec_name
        res.update(self.__get_account_payment_term())
        return res

    def on_change_party(self):
        res = {
            'invoice_address': None,
            }
        res.update(self.__get_account_payment_term())

        if self.party:
            invoice_address = self.party.address_get(type='invoice')
            res['invoice_address'] = invoice_address.id
            res['invoice_address.rec_name'] = invoice_address.rec_name
        return res

    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2

    def on_change_with_currency_date(self, name=None):
        Date = Pool().get('ir.date')
        return self.invoice_date or Date.today()

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

    def on_change_lines(self):
        return self._on_change_lines_taxes()

    def on_change_taxes(self):
        return self._on_change_lines_taxes()

    def _on_change_lines_taxes(self):
        pool = Pool()
        Tax = pool.get('account.tax')
        InvoiceTax = pool.get('account.invoice.tax')
        Account = pool.get('account.account')
        TaxCode = pool.get('account.tax.code')
        res = {
            'untaxed_amount': Decimal('0.0'),
            'tax_amount': Decimal('0.0'),
            'total_amount': Decimal('0.0'),
            'taxes': {},
            }
        computed_taxes = {}
        if self.lines:
            context = self.get_tax_context()
            for line in self.lines:
                if (line.type or 'line') != 'line':
                    continue
                res['untaxed_amount'] += line.amount or 0
                with Transaction().set_context(**context):
                    taxes = Tax.compute(line.taxes,
                        line.unit_price or Decimal('0.0'),
                        line.quantity or 0.0)
                for tax in taxes:
                    key, val = self._compute_tax(tax,
                        self.type or 'out_invoice')
                    if not key in computed_taxes:
                        computed_taxes[key] = val
                    else:
                        computed_taxes[key]['base'] += val['base']
                        computed_taxes[key]['amount'] += val['amount']
        if self.currency:
            for key in computed_taxes:
                for field in ('base', 'amount'):
                    computed_taxes[key][field] = self.currency.round(
                        computed_taxes[key][field])
        tax_keys = []
        for tax in (self.taxes or []):
            if tax.manual:
                res['tax_amount'] += tax.amount or Decimal('0.0')
                continue
            key = (tax.base_code.id if tax.base_code else None, tax.base_sign,
                tax.tax_code.id if tax.tax_code else None, tax.tax_sign,
                tax.account.id if tax.account else None,
                tax.tax.id if tax.tax else None)
            if (key not in computed_taxes) or (key in tax_keys):
                res['taxes'].setdefault('remove', [])
                res['taxes']['remove'].append(tax.id)
                continue
            tax_keys.append(key)
            if self.currency:
                if not self.currency.is_zero(
                        computed_taxes[key]['base']
                        - (tax.base or Decimal('0.0'))):
                    res['tax_amount'] += computed_taxes[key]['amount']
                    res['taxes'].setdefault('update', [])
                    res['taxes']['update'].append({
                            'id': tax.id,
                            'amount': computed_taxes[key]['amount'],
                            'base': computed_taxes[key]['base'],
                            })
                else:
                    res['tax_amount'] += tax.amount or Decimal('0.0')
            else:
                if (computed_taxes[key]['base'] - (tax.base or Decimal('0.0'))
                        != Decimal('0.0')):
                    res['tax_amount'] += computed_taxes[key]['amount']
                    res['taxes'].setdefault('update', [])
                    res['taxes']['update'].append({
                        'id': tax.id,
                        'amount': computed_taxes[key]['amount'],
                        'base': computed_taxes[key]['base'],
                        })
                else:
                    res['tax_amount'] += tax.amount or Decimal('0.0')
        for key in computed_taxes:
            if key not in tax_keys:
                res['tax_amount'] += computed_taxes[key]['amount']
                res['taxes'].setdefault('add', [])
                value = InvoiceTax.default_get(InvoiceTax._fields.keys())
                value.update(computed_taxes[key])
                for field, Target in (
                        ('account', Account),
                        ('base_code', TaxCode),
                        ('tax_code', TaxCode),
                        ('tax', Tax),
                        ):
                    if value.get(field):
                        value[field + '.rec_name'] = \
                            Target(value[field]).rec_name
                res['taxes']['add'].append(value)
        if self.currency:
            res['untaxed_amount'] = self.currency.round(res['untaxed_amount'])
            res['tax_amount'] = self.currency.round(res['tax_amount'])
        res['total_amount'] = res['untaxed_amount'] + res['tax_amount']
        if self.currency:
            res['total_amount'] = self.currency.round(res['total_amount'])
        return res

    def get_untaxed_amount(self, name):
        amount = _ZERO
        for line in self.lines:
            if line.type != 'line':
                continue
            amount += line.amount
        return self.currency.round(amount)

    @classmethod
    def get_tax_amount(cls, invoices, name):
        cursor = Transaction().cursor
        res = {}
        type_name = FIELDS[cls.tax_amount._type].sql_type(cls.tax_amount)[0]
        red_sql, red_ids = reduce_ids('invoice', [i.id for i in invoices])
        cursor.execute('SELECT invoice, '
                    'CAST(COALESCE(SUM(amount), 0) AS ' + type_name + ') '
                'FROM account_invoice_tax '
                'WHERE ' + red_sql + ' '
                'GROUP BY invoice', red_ids)
        for invoice_id, sum in cursor.fetchall():
            # SQLite uses float for SUM
            if not isinstance(sum, Decimal):
                sum = Decimal(str(sum))
            res[invoice_id] = sum

        for invoice in invoices:
            res.setdefault(invoice.id, Decimal('0.0'))
            res[invoice.id] = invoice.currency.round(res[invoice.id])
        return res

    def get_total_amount(self, name):
        return self.currency.round(self.untaxed_amount + self.tax_amount)

    def get_reconciled(self, name):
        if not self.lines_to_pay:
            return False
        for line in self.lines_to_pay:
            if not line.reconciliation:
                return False
        return True

    def get_lines_to_pay(self, name):
        lines = []
        if self.move:
            for line in self.move.lines:
                if (line.account.id == self.account.id
                        and line.maturity_date):
                    lines.append(line)
        lines.sort(key=operator.attrgetter('maturity_date'))
        return [x.id for x in lines]

    @classmethod
    def get_amount_to_pay(cls, invoices, name):
        pool = Pool()
        Currency = pool.get('currency.currency')
        Date = pool.get('ir.date')

        computes = cls.search([
                ('id', 'in', [i.id for i in invoices]),
                ('state', '=', 'posted'),
                ])

        today = Date.today()
        res = dict((x.id, _ZERO) for x in invoices)
        for invoice in computes:
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
                    if line.debit - line.credit > _ZERO:
                        amount_currency += abs(line.amount_second_currency)
                    else:
                        amount_currency -= abs(line.amount_second_currency)
                else:
                    amount += line.debit - line.credit
            for line in invoice.payment_lines:
                if line.reconciliation:
                    continue
                if (line.second_currency
                        and line.second_currency == invoice.currency):
                    if line.debit - line.credit > _ZERO:
                        amount_currency += abs(line.amount_second_currency)
                    else:
                        amount_currency -= abs(line.amount_second_currency)
                else:
                    amount += line.debit - line.credit
            if invoice.type in ('in_invoice', 'out_credit_note'):
                amount = - amount
                amount_currency = - amount_currency
            if amount != _ZERO:
                with Transaction().set_context(date=invoice.currency_date):
                    amount_currency += Currency.compute(
                        invoice.company.currency, amount, invoice.currency)
            if amount_currency < _ZERO:
                amount_currency = _ZERO
            res[invoice.id] = amount_currency
        return res

    @classmethod
    def search_total_amount(cls, name, clause):
        pool = Pool()
        Rule = pool.get('ir.rule')
        Line = pool.get('account.invoice.line')
        Tax = pool.get('account.invoice.tax')
        type_name = FIELDS[cls.total_amount._type].sql_type(
            cls.total_amount)[0]
        cursor = Transaction().cursor

        invoice_query, invoice_val = Rule.domain_get('account.invoice')

        cursor.execute('SELECT invoice FROM ('
                    'SELECT invoice, '
                        'COALESCE(SUM(quantity * unit_price), 0) '
                            'AS total_amount '
                    'FROM "' + Line._table + '" '
                    'JOIN "' + cls._table + '" ON '
                        '("' + cls._table + '".id = '
                            '"' + Line._table + '".invoice) '
                    'WHERE ' + invoice_query + ' '
                    'GROUP BY invoice '
                'UNION '
                    'SELECT invoice, COALESCE(SUM(amount), 0) AS total_amount '
                    'FROM "' + Tax._table + '" '
                    'JOIN "' + cls._table + '" ON '
                        '("' + cls._table + '".id = '
                            '"' + Tax._table + '".invoice) '
                    'WHERE ' + invoice_query + ' '
                    'GROUP BY invoice  '
                ') AS u '
                'GROUP BY u.invoice '
                'HAVING (CAST(SUM(u.total_amount) AS ' + type_name + ') '
                    + clause[1] + ' %s)',
                invoice_val + invoice_val + [str(clause[2])])
        return [('id', 'in', [x[0] for x in cursor.fetchall()])]

    @classmethod
    def search_untaxed_amount(cls, name, clause):
        pool = Pool()
        Rule = pool.get('ir.rule')
        Line = pool.get('account.invoice.line')
        type_name = FIELDS[cls.untaxed_amount._type].sql_type(
                cls.untaxed_amount)[0]
        cursor = Transaction().cursor

        invoice_query, invoice_val = Rule.domain_get('account.invoice')

        cursor.execute('SELECT invoice FROM "' + Line._table + '" '
                'JOIN "' + cls._table + '" ON '
                    '("' + cls._table + '".id = '
                        '"' + Line._table + '".invoice) '
                'WHERE ' + invoice_query + ' '
                'GROUP BY invoice '
                'HAVING (CAST(COALESCE(SUM(quantity * unit_price), 0) '
                    'AS ' + type_name + ') ' + clause[1] + ' %s)',
                invoice_val + [str(clause[2])])
        return [('id', 'in', [x[0] for x in cursor.fetchall()])]

    @classmethod
    def search_tax_amount(cls, name, clause):
        pool = Pool()
        Rule = pool.get('ir.rule')
        Tax = pool.get('account.invoice.tax')
        type_name = FIELDS[cls.tax_amount._type].sql_type(
                cls.tax_amount)[0]
        cursor = Transaction().cursor

        invoice_query, invoice_val = Rule.domain_get('account.invoice')

        cursor.execute('SELECT invoice FROM "' + Tax._table + '" '
                'JOIN "' + cls._table + '" ON '
                    '("' + cls._table + '".id = '
                        '"' + Tax._table + '".invoice) '
                'WHERE ' + invoice_query + ' '
                'GROUP BY invoice '
                'HAVING (CAST(COALESCE(SUM(amount), 0) '
                    'AS ' + type_name + ') ' + clause[1] + ' %s)',
                invoice_val + [str(clause[2])])
        return [('id', 'in', [x[0] for x in cursor.fetchall()])]

    def get_tax_context(self):
        context = {}
        if self.party and self.party.lang:
            context['language'] = self.party.lang.code
        return context

    @staticmethod
    def _compute_tax(invoice_tax, invoice_type):
        val = {}
        tax = invoice_tax['tax']
        val['manual'] = False
        val['description'] = tax.description
        val['base'] = invoice_tax['base']
        val['amount'] = invoice_tax['amount']
        val['tax'] = tax.id if tax else None

        if invoice_type in ('out_invoice', 'in_invoice'):
            val['base_code'] = (tax.invoice_base_code.id
                if tax.invoice_base_code else None)
            val['base_sign'] = tax.invoice_base_sign
            val['tax_code'] = (tax.invoice_tax_code.id
                if tax.invoice_tax_code else None)
            val['tax_sign'] = tax.invoice_tax_sign
            val['account'] = (tax.invoice_account.id
                if tax.invoice_account else None)
        else:
            val['base_code'] = (tax.credit_note_base_code.id
                if tax.credit_note_base_code else None)
            val['base_sign'] = tax.credit_note_base_sign
            val['tax_code'] = (tax.credit_note_tax_code.id
                if tax.credit_note_tax_code else None)
            val['tax_sign'] = tax.credit_note_tax_sign
            val['account'] = (tax.credit_note_account.id
                if tax.credit_note_account else None)
        key = (val['base_code'], val['base_sign'],
            val['tax_code'], val['tax_sign'],
            val['account'], val['tax'])
        return key, val

    def _compute_taxes(self):
        Tax = Pool().get('account.tax')

        context = self.get_tax_context()

        res = {}
        for line in self.lines:
            # Don't round on each line to handle rounding error
            if line.type != 'line':
                continue
            with Transaction().set_context(**context):
                taxes = Tax.compute(line.taxes, line.unit_price,
                        line.quantity)
            for tax in taxes:
                key, val = self._compute_tax(tax, self.type)
                val['invoice'] = self.id
                if not key in res:
                    res[key] = val
                else:
                    res[key]['base'] += val['base']
                    res[key]['amount'] += val['amount']
        for key in res:
            for field in ('base', 'amount'):
                res[key][field] = self.currency.round(res[key][field])
        return res

    @classmethod
    def update_taxes(cls, invoices, exception=False):
        Tax = Pool().get('account.invoice.tax')
        for invoice in invoices:
            if invoice.state in ('posted', 'paid', 'cancel'):
                continue
            computed_taxes = invoice._compute_taxes()
            if not invoice.taxes:
                Tax.create([tax for tax in computed_taxes.values()])
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
                    if (not key in computed_taxes) or (key in tax_keys):
                        if exception:
                            cls.raise_user_error('missing_tax_line',
                                (invoice.rec_name,))
                        Tax.delete([tax])
                        continue
                    tax_keys.append(key)
                    if not invoice.currency.is_zero(
                            computed_taxes[key]['base'] - tax.base):
                        if exception:
                            cls.raise_user_error('diff_tax_line',
                                (invoice.rec_name,))
                        Tax.write([tax], computed_taxes[key])
                for key in computed_taxes:
                    if not key in tax_keys:
                        if exception:
                            cls.raise_user_error('missing_tax_line2',
                                (invoice.rec_name,))
                        Tax.create([computed_taxes[key]])

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
            res['amount_second_currency'] = abs(res['amount_second_currency'])
            res['second_currency'] = self.currency.id
        else:
            res['amount_second_currency'] = Decimal('0.0')
            res['second_currency'] = None
        if amount >= Decimal('0.0'):
            res['debit'] = Decimal('0.0')
            res['credit'] = amount
        else:
            res['debit'] = - amount
            res['credit'] = Decimal('0.0')
        res['account'] = self.account.id
        res['maturity_date'] = date
        res['description'] = self.description
        res['party'] = self.party.id
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
            total_currency += line['amount_second_currency']

        term_lines = self.payment_term.compute(total, self.company.currency,
            self.invoice_date)
        remainder_total_currency = total_currency
        if not term_lines:
            term_lines = [(Date.today(), total)]
        for date, amount in term_lines:
            val = self._get_move_line(date, amount)
            remainder_total_currency -= val['amount_second_currency']
            move_lines.append(val)
        if not self.currency.is_zero(remainder_total_currency):
            move_lines[-1]['amount_second_currency'] += \
                remainder_total_currency

        accounting_date = self.accounting_date or self.invoice_date
        period_id = Period.find(self.company.id, date=accounting_date)

        move, = Move.create([{
                    'journal': self.journal.id,
                    'period': period_id,
                    'date': accounting_date,
                    'origin': str(self),
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
        if self.type in ('in_invoice', 'in_credit_note'):
            test_state = False

        accounting_date = self.accounting_date or self.invoice_date
        period_id = Period.find(self.company.id,
            date=accounting_date, test_state=test_state)
        period = Period(period_id)
        sequence_id = period.get_invoice_sequence(self.type).id
        if not sequence_id:
            self.raise_user_error('no_invoice_sequence', {
                    'invoice': self.rec_name,
                    'period': period.rec_name,
                    })
        with Transaction().set_context(
                date=self.invoice_date or Date.today()):
            number = Sequence.get_id(sequence_id)
            vals = {'number': number}
            if (not self.invoice_date
                    and self.type in ('out_invoice', 'out_credit_note')):
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
        invoices = cls.search(['OR',
                ('number',) + clause[1:],
                ('reference',) + clause[1:],
                ], order=[])
        if invoices:
            return [('id', 'in', [i.id for i in invoices])]
        return [('party',) + clause[1:]]

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
    def write(cls, invoices, vals):
        keys = vals.keys()
        for key in cls._check_modify_exclude:
            if key in keys:
                keys.remove(key)
        if len(keys):
            cls.check_modify(invoices)
        update_tax = [i for i in invoices if i.state == 'draft']
        super(Invoice, cls).write(invoices, vals)
        if update_tax:
            cls.update_taxes(update_tax)

    @classmethod
    def copy(cls, invoices, default=None):
        pool = Pool()
        Line = pool.get('account.invoice.line')
        Tax = pool.get('account.invoice.tax')

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
        default['lines'] = None
        default['taxes'] = None
        default.setdefault('invoice_date', None)
        default.setdefault('accounting_date', None)
        default['lines_to_pay'] = None
        default.setdefault('origin', None)

        new_invoices = []
        for invoice in invoices:
            new_invoice, = super(Invoice, cls).copy([invoice], default=default)
            Line.copy(invoice.lines, default={
                    'invoice': new_invoice.id,
                    })
            Tax.copy(invoice.taxes, default={
                    'invoice': new_invoice.id,
                    })
            new_invoices.append(new_invoice)
        return new_invoices

    @classmethod
    def validate(cls, invoices):
        super(Invoice, cls).validate(invoices)
        for invoice in invoices:
            invoice.check_account()
            invoice.check_same_account()
            invoice.check_cancel_move()

    def check_account(self):
        if self.account.company != self.company:
            self.raise_user_error('check_account', {
                    'invoice': self.rec_name,
                    'invoice_company': self.company.rec_name,
                    'account': self.account.rec_name,
                    'account_company': self.account.company.rec_name,
                    })

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
        if (self.type in ('out_invoice', 'out_credit_note')
                and self.cancel_move):
            return False
        return True

    def get_reconcile_lines_for_amount(self, amount, exclude_lines=None):
        '''
        Return list of lines and the remainder to make reconciliation.
        '''
        if exclude_lines is None:
            exclude_lines = []
        payment_amount = Decimal('0.0')
        remainder = self.total_amount
        lines = []
        payment_lines = []

        for line in self.payment_lines:
            if line.reconciliation:
                continue
            payment_amount += line.debit - line.credit
            payment_lines.append(line)

        if self.type in ('out_invoice', 'in_credit_note'):
            amount = - abs(amount)
        else:
            amount = abs(amount)

        for line in self.lines_to_pay:

            if line.reconciliation:
                continue
            if line in exclude_lines:
                continue

            test_amount = amount + (line.debit - line.credit)
            if self.currency.is_zero(test_amount):
                return ([line], Decimal('0.0'))
            if abs(test_amount) < abs(remainder):
                lines = [line]
                remainder = test_amount

            test_amount = (amount + payment_amount)
            test_amount += (line.debit - line.credit)
            if self.currency.is_zero(test_amount):
                return ([line] + payment_lines, Decimal('0.0'))
            if abs(test_amount) < abs(remainder):
                lines = [line] + payment_lines
                remainder = test_amount

            exclude_lines2 = exclude_lines[:]
            exclude_lines2.append(line)
            lines2, remainder2 = self.get_reconcile_lines_for_amount(
                (amount + (line.debit - line.credit)),
                exclude_lines=exclude_lines2)
            if remainder2 == Decimal('0.0'):
                lines2.append(line)
                return lines2, remainder2
            if abs(remainder2) < abs(remainder):
                lines2.append(line)
                lines, remainder = lines2, remainder2

        return (lines, remainder)

    def pay_invoice(self, amount, journal, date, description,
            amount_second_currency=None, second_currency=None):
        '''
        Adds a payment of amount to an invoice using the journal, date and
        description.
        Returns the payment line.
        '''
        pool = Pool()
        Move = pool.get('account.move')
        Period = pool.get('account.period')

        lines = []

        if self.type in ('out_invoice', 'in_credit_note'):
            if self.account == journal.debit_account:
                self.raise_user_error('same_debit_account', {
                        'journal': journal.rec_name,
                        'invoice': self.rec_name,
                        })
            if not journal.debit_account:
                self.raise_user_error('missing_debit_account',
                    (journal.rec_name,))

            lines.append({
                    'description': description,
                    'account': self.account.id,
                    'party': self.party.id,
                    'debit': Decimal('0.0'),
                    'credit': amount,
                    'amount_second_currency': amount_second_currency,
                    'second_currency': second_currency,
                    })
            lines.append({
                    'description': description,
                    'account': journal.debit_account.id,
                    'party': self.party.id,
                    'debit': amount,
                    'credit': Decimal('0.0'),
                    'amount_second_currency': amount_second_currency,
                    'second_currency': second_currency,
                    })
        else:
            if self.account == journal.credit_account:
                self.raise_user_error('same_credit_account', {
                        'journal': journal.rec_name,
                        'invoice': self.rec_name,
                        })
            if not journal.credit_account:
                self.raise_user_error('missing_credit_account',
                    (journal.rec_name,))

            lines.append({
                    'description': description,
                    'account': self.account.id,
                    'party': self.party.id,
                    'debit': amount,
                    'credit': Decimal('0.0'),
                    'amount_second_currency': amount_second_currency,
                    'second_currency': second_currency,
                    })
            lines.append({
                    'description': description,
                    'account': journal.credit_account.id,
                    'party': self.party.id,
                    'debit': Decimal('0.0'),
                    'credit': amount,
                    'amount_second_currency': amount_second_currency,
                    'second_currency': second_currency,
                    })

        period_id = Period.find(self.company.id, date=date)

        move, = Move.create([{
                    'journal': journal.id,
                    'period': period_id,
                    'date': date,
                    'lines': [('create', lines)],
                    }])
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
        if self.type == 'out_invoice':
            res['type'] = 'out_credit_note'
        elif self.type == 'in_invoice':
            res['type'] = 'in_credit_note'
        elif self.type == 'out_credit_note':
            res['type'] = 'out_invoice'
        elif self.type == 'in_credit_note':
            res['type'] = 'in_invoice'

        for field in ('description', 'comment'):
            res[field] = getattr(self, field)

        res['reference'] = self.number or self.reference

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
            with Transaction().set_user(0, set_context=True):
                Move.delete(moves)

    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    def validate_invoice(cls, invoices):
        for invoice in invoices:
            if invoice.type in ('in_invoice', 'in_credit_note'):
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
        Move.post(moves)
        cls.write(invoices, {
                'state': 'posted',
                })
        for invoice in invoices:
            if invoice.type in ('out_invoice', 'out_credit_note'):
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

    def get_cancel_move(self):
        pool = Pool()
        Date = pool.get('ir.date')
        Move = pool.get('account.move')
        Period = pool.get('account.period')

        move = self.move
        default = {}
        if move.period.state == 'close':
            self.raise_user_warning('%s.get_cancel_move' % self,
                'period_cancel_move', self.rec_name)
            date = Date.today()
            period_id = Period.find(self.company.id, date=date)
            default.update({
                    'date': date,
                    'period': period_id,
                    })

        cancel_move, = Move.copy([move], default=default)
        for line in cancel_move.lines:
            line.debit *= -1
            line.credit *= -1
            line.save()
            for tax_line in line.tax_lines:
                tax_line.amount *= -1
                tax_line.save()
        return cancel_move

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, invoices):
        Move = Pool().get('account.move')

        cancel_moves = []
        delete_moves = []
        for invoice in invoices:
            if invoice.move:
                if invoice.move.state == 'draft':
                    delete_moves.append(invoice.move)
                elif not invoice.cancel_move:
                    invoice.cancel_move = invoice.get_cancel_move()
                    invoice.save()
                    cancel_moves.append(invoice.cancel_move)
        if delete_moves:
            with Transaction().set_user(0, set_context=True):
                Move.delete(delete_moves)
        if cancel_moves:
            Move.post(cancel_moves)


class InvoicePaymentLine(ModelSQL):
    'Invoice - Payment Line'
    __name__ = 'account.invoice-account.move.line'
    invoice = fields.Many2One('account.invoice', 'Invoice', ondelete='CASCADE',
            select=True, required=True)
    line = fields.Many2One('account.move.line', 'Payment Line',
            ondelete='CASCADE', select=True, required=True)


class InvoiceLine(ModelSQL, ModelView):
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
    invoice_type = fields.Selection(_TYPE, 'Invoice Type', select=True,
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
    party_lang = fields.Function(fields.Char('Party Language',
        on_change_with=['party']), 'on_change_with_party_lang')
    currency = fields.Many2One('currency.currency', 'Currency',
        states={
            'required': ~Eval('invoice'),
            },
        depends=['invoice'])
    currency_digits = fields.Function(fields.Integer('Currency Digits',
        on_change_with=['currency']), 'on_change_with_currency_digits')
    company = fields.Many2One('company.company', 'Company',
        states={
            'required': ~Eval('invoice'),
            },
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', 0)),
            ],
        depends=['invoice'], select=True)

    sequence = fields.Integer('Sequence',
        order_field='(%(table)s.sequence IS NULL) %(order)s, '
        '%(table)s.sequence %(order)s',
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
    unit = fields.Many2One('product.uom', 'Unit',
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
    unit_digits = fields.Function(fields.Integer('Unit Digits',
        on_change_with=['unit']), 'on_change_with_unit_digits')
    product = fields.Many2One('product.product', 'Product',
        states={
            'invisible': Eval('type') != 'line',
            },
        on_change=['product', 'unit', 'quantity', 'description',
            '_parent_invoice.type', '_parent_invoice.party',
            '_parent_invoice.currency', '_parent_invoice.currency_date',
            'party', 'currency', 'invoice'],
        depends=['type'])
    product_uom_category = fields.Function(
        fields.Many2One('product.uom.category', 'Product Uom Category',
            on_change_with=['product']),
        'on_change_with_product_uom_category')
    account = fields.Many2One('account.account', 'Account',
        domain=[
            ('company', '=', Eval('_parent_invoice', {}).get('company',
                    Eval('context', {}).get('company', 0))),
            If(Bool(Eval('_parent_invoice')),
                If(Eval('_parent_invoice', {}).get('type').in_(['out_invoice',
                    'out_credit_note']),
                    ('kind', '=', 'revenue'),
                    ('kind', '=', 'expense')),
                If(Eval('invoice_type').in_(['out_invoice',
                            'out_credit_note']),
                    ('kind', '=', 'revenue'),
                    ('kind', '=', 'expense')))
            ],
        on_change=['account', 'product', '_parent_invoice.party',
            '_parent_invoice.type'],
        states={
            'invisible': Eval('type') != 'line',
            'required': Eval('type') == 'line',
            },
        depends=['type', 'invoice_type'])
    unit_price = fields.Numeric('Unit Price', digits=(16, 4),
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
            on_change_with=['type', 'quantity', 'unit_price',
                '_parent_invoice.currency', 'currency'],
            depends=['type', 'currency_digits']), 'get_amount')
    description = fields.Text('Description', size=None, required=True)
    note = fields.Text('Note')
    taxes = fields.Many2Many('account.invoice.line-account.tax',
        'line', 'tax', 'Taxes',
        domain=[('parent', '=', None), ['OR',
                ('group', '=', None),
                ('group.kind', 'in',
                    If(Bool(Eval('_parent_invoice')),
                        If(Eval('_parent_invoice', {}).get('type').in_(
                                ['out_invoice', 'out_credit_note']),
                            ['sale', 'both'],
                            ['purchase', 'both']),
                        If(Eval('invoice_type').in_(
                                ['out_invoice', 'out_credit_note']),
                            ['sale', 'both'],
                            ['purchase', 'both']))
                    )],
            ],
        states={
            'invisible': Eval('type') != 'line',
            },
        depends=['type', 'invoice_type'])
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
        cls._sql_constraints += [
            ('type_account',
                'CHECK((type = \'line\' AND account IS NOT NULL) '
                'OR (type != \'line\'))',
                'Line with "line" type must have an account.'),
            ('type_invoice',
                'CHECK((type != \'line\' AND invoice IS NOT NULL) '
                'OR (type = \'line\'))',
                'Line without "line" type must have an invoice.'),
            ]
        cls._order.insert(0, ('sequence', 'ASC'))
        cls._error_messages.update({
                'modify': ('You can not modify line "%(line)s" from invoice '
                    '"%(invoice)s" that is posted or paid.'),
                'create': ('You can not add a line to invoice "%(invoice)s" '
                    'that is posted, paid or cancelled.'),
                'account_different_company': ('You can not create invoice line '
                    '"%(line)s" on invoice "%(invoice)s of company '
                    '"%(invoice_line_company)s because account "%(account)s '
                    'has company "%(account_company)s".'),
                'same_account_on_invoice': ('You can not create invoice line '
                    '"%(line)s" on invoice "%(invoice)s" because the invoice '
                    'uses the same account (%(account)s).'),
                })

    @classmethod
    def __register__(cls, module_name):
        super(InvoiceLine, cls).__register__(module_name)
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

        # Migration from 1.0 invoice is no more required
        table.not_null_action('invoice', action='remove')

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')

    @staticmethod
    def default_invoice_type():
        return Transaction().context.get('invoice_type', 'out_invoice')

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

    def on_change_with_party_lang(self, name=None):
        Config = Pool().get('ir.configuration')
        if self.party and self.party.lang:
            return self.party.lang.code
        return Config.get_language()

    def on_change_with_unit_digits(self, name=None):
        if self.unit:
            return self.unit.digits
        return 2

    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2

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

    def get_invoice_taxes(self, name):
        pool = Pool()
        Tax = pool.get('account.tax')
        Invoice = pool.get('account.invoice')

        if not self.invoice:
            return
        context = self.invoice.get_tax_context()
        taxes_keys = []
        with Transaction().set_context(**context):
            taxes = Tax.compute(self.taxes, self.unit_price, self.quantity)
        for tax in taxes:
            key, _ = Invoice._compute_tax(tax, self.invoice.type)
            taxes_keys.append(key)
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

    def on_change_product(self):
        pool = Pool()
        Product = pool.get('product.product')
        Company = pool.get('company.company')
        Currency = pool.get('currency.currency')
        Date = pool.get('ir.date')

        if not self.product:
            return {}
        res = {}

        context = {}
        party = None
        if self.invoice and self.invoice.party:
            party = self.invoice.party
        elif self.party:
            party = self.party
        if party and party.lang:
            context['language'] = party.lang.code

        company = None
        if Transaction().context.get('company'):
            company = Company(Transaction().context['company'])
        currency = None
        currency_date = Date.today()
        if self.invoice and self.invoice.currency_date:
            currency_date = self.invoice.currency_date
        #TODO check if today date is correct
        if self.invoice and self.invoice.currency:
            currency = self.invoice.currency
        elif self.currency:
            currency = self.currency

        if self.invoice and self.invoice.type:
            type_ = self.invoice.type
        elif self.invoice_type:
            type_ = self.invoice_type
        if type_ in ('in_invoice', 'in_credit_note'):
            if company and currency:
                with Transaction().set_context(date=currency_date):
                    res['unit_price'] = Currency.compute(
                        company.currency, self.product.cost_price,
                        currency, round=False)
            else:
                res['unit_price'] = self.product.cost_price
            try:
                account_expense = self.product.account_expense_used
                res['account'] = account_expense.id
                res['account.rec_name'] = account_expense.rec_name
            except Exception:
                pass
            res['taxes'] = []
            pattern = self._get_tax_rule_pattern()
            for tax in self.product.supplier_taxes_used:
                if party and party.supplier_tax_rule:
                    tax_ids = party.supplier_tax_rule.apply(tax, pattern)
                    if tax_ids:
                        res['taxes'].extend(tax_ids)
                    continue
                res['taxes'].append(tax.id)
            if party and party.supplier_tax_rule:
                tax_ids = party.supplier_tax_rule.apply(None, pattern)
                if tax_ids:
                    res['taxes'].extend(tax_ids)
        else:
            if company and currency:
                with Transaction().set_context(date=currency_date):
                    res['unit_price'] = Currency.compute(
                        company.currency, self.product.list_price,
                        currency, round=False)
            else:
                res['unit_price'] = self.product.list_price
            try:
                account_revenue = self.product.account_revenue_used
                res['account'] = account_revenue.id
                res['account.rec_name'] = account_revenue.rec_name
            except Exception:
                pass
            res['taxes'] = []
            pattern = self._get_tax_rule_pattern()
            for tax in self.product.customer_taxes_used:
                if party and party.customer_tax_rule:
                    tax_ids = party.customer_tax_rule.apply(tax, pattern)
                    if tax_ids:
                        res['taxes'].extend(tax_ids)
                    continue
                res['taxes'].append(tax.id)
            if party and party.customer_tax_rule:
                tax_ids = party.customer_tax_rule.apply(None, pattern)
                if tax_ids:
                    res['taxes'].extend(tax_ids)

        if not self.description:
            with Transaction().set_context(**context):
                res['description'] = Product(self.product.id).rec_name

        category = self.product.default_uom.category
        if not self.unit or self.unit not in category.uoms:
            res['unit'] = self.product.default_uom.id
            res['unit.rec_name'] = self.product.default_uom.rec_name
            res['unit_digits'] = self.product.default_uom.digits

        self.unit_price = res['unit_price']
        self.type = 'line'
        res['amount'] = self.on_change_with_amount()
        return res

    def on_change_with_product_uom_category(self, name=None):
        if self.product:
            return self.product.default_uom_category.id

    def on_change_account(self):
        if self.product:
            return {}
        taxes = []
        result = {
            'taxes': taxes,
            }
        if (self.invoice and self.invoice.party
                and self.invoice.type):
            party = self.invoice.party
            if self.invoice.type in ('in_invoice', 'in_credit_note'):
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
                taxes.append(tax.id)
        return result

    @staticmethod
    def _get_origin():
        'Return list of Model names for origin Reference'
        return []

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        models = cls._get_origin()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [(None, '')] + [(m.model, m.name) for m in models]

    @classmethod
    def check_modify(cls, lines):
        '''
        Check if the lines can be modified
        '''
        for line in lines:
            if (line.invoice
                    and line.invoice.state in ('posted', 'paid')):
                cls.raise_user_error('modify', {
                        'line': line.rec_name,
                        'invoice': line.invoice.rec_name
                        })

    @classmethod
    def delete(cls, lines):
        cls.check_modify(lines)
        super(InvoiceLine, cls).delete(lines)

    @classmethod
    def write(cls, lines, vals):
        cls.check_modify(lines)
        super(InvoiceLine, cls).write(lines, vals)

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
    def validate(cls, lines):
        super(InvoiceLine, cls).validate(lines)
        for line in lines:
            line.check_account_company()
            line.check_same_account()

    def check_account_company(self):
        if self.type == 'line':
            if self.invoice:
                if self.account.company != self.invoice.company:
                    self.raise_user_error('account_different_company', {
                            'line': self.rec_name,
                            'invoice': self.invoice.rec_name,
                            'invoice_line_company':
                                self.invoice.company.rec_name,
                            'account': self.account.rec_name,
                            'account_company': self.account.company.rec_name,
                            })
            elif self.company:
                if self.account.company != self.company:
                    self.raise_user_error('account_different_company', {
                            'line': self.rec_name,
                            'invoice': '/',
                            'invoice_line_company': self.company.rec_name,
                            'account': self.account.rec_name,
                            'account_company': self.account.company.rec_name,
                            })

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
        Tax = pool.get('account.tax')
        Currency = pool.get('currency.currency')

        context = self.invoice.get_tax_context()
        res = []
        if self.type != 'line':
            return res
        with Transaction().set_context(**context):
            taxes = Tax.compute(self.taxes, self.unit_price, self.quantity)
        for tax in taxes:
            if self.invoice.type in ('out_invoice', 'in_invoice'):
                base_code_id = (tax['tax'].invoice_base_code.id
                    if tax['tax'].invoice_base_code else None)
                amount = tax['base'] * tax['tax'].invoice_base_sign
            else:
                base_code_id = (tax['tax'].credit_note_base_code.id
                    if tax['tax'].credit_note_base_code else None)
                amount = tax['base'] * tax['tax'].credit_note_base_sign
            if base_code_id:
                with Transaction().set_context(
                        date=self.invoice.currency_date):
                    amount = Currency.compute(self.invoice.currency,
                        amount, self.invoice.company.currency)
                res.append({
                        'code': base_code_id,
                        'amount': amount,
                        'tax': tax['tax'].id if tax['tax'] else None,
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
            res['amount_second_currency'] = Decimal('0.0')
            res['second_currency'] = None
        if self.invoice.type in ('in_invoice', 'out_credit_note'):
            if amount >= Decimal('0.0'):
                res['debit'] = amount
                res['credit'] = Decimal('0.0')
            else:
                res['debit'] = Decimal('0.0')
                res['credit'] = - amount
                res['amount_second_currency'] = - res['amount_second_currency']
        else:
            if amount >= Decimal('0.0'):
                res['debit'] = Decimal('0.0')
                res['credit'] = amount
                res['amount_second_currency'] = - res['amount_second_currency']
            else:
                res['debit'] = - amount
                res['credit'] = Decimal('0.0')
        res['account'] = self.account.id
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

        for field in ('sequence', 'type', 'quantity', 'unit_price',
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
    sequence = fields.Integer('Sequence',
        order_field='(%(table)s.sequence IS NULL) %(order)s, '
        '%(table)s.sequence %(order)s')
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
        on_change_with=['tax', 'base', 'amount', 'manual'],
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
        states={
            'readonly': ~Eval('manual', False),
            },
        on_change=['tax', '_parent_invoice.party',
            '_parent_invoice.type'],
        depends=['manual'])

    @classmethod
    def __setup__(cls):
        super(InvoiceTax, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))
        cls._error_messages.update({
                'modify': ('You can not modify tax "%(tax)s" from invoice '
                    '"%(invoice)s" because it is posted or paid.'),
                'create': ('You can not add line "%(line)s" to invoice '
                    '"%(invoice)s" because it is posted, paid or canceled.'),
                'invalid_account_company': ('You can not create invoice '
                    '"%(invoice)s" on company "%(invoice_company)s" using '
                    'account "%(account)s" from company '
                    '"%(account_company)s".'),
                'invalid_base_code_company': ('You can not create invoice '
                    '"%(invoice)s" on company "%(invoice_company)s" using base '
                    'tax code "%(base_code)s" from company '
                    '"%(base_code_company)s".'),
                'invalid_tax_code_company': ('You can not create invoice '
                    '"%(invoice)s" on company "%(invoice_company)s" using tax '
                    'code "%(tax_code)s" from company "%(tax_code_company)s".'),
                })

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

        super(InvoiceTax, cls).__register__(module_name)

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')

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

    def on_change_tax(self):
        Tax = Pool().get('account.tax')
        changes = {}
        if self.tax:
            if self.invoice:
                context = self.invoice.get_tax_context()
            else:
                context = {}
            with Transaction().set_context(**context):
                tax = Tax(self.tax.id)
            changes['description'] = tax.description
            if self.invoice and self.invoice.type:
                invoice_type = self.invoice.type
            else:
                invoice_type = 'out_invoice'
            if invoice_type in ('out_invoice', 'in_invoice'):
                changes['base_code'] = (tax.invoice_base_code.id
                    if tax.invoice_base_code else None)
                changes['base_sign'] = tax.invoice_base_sign
                changes['tax_code'] = (tax.invoice_tax_code.id
                    if tax.invoice_tax_code else None)
                changes['tax_sign'] = tax.invoice_tax_sign
                changes['account'] = tax.invoice_account.id
            else:
                changes['base_code'] = (tax.credit_note_base_code.id
                    if tax.credit_note_base_code else None)
                changes['base_sign'] = tax.credit_note_base_sign
                changes['tax_code'] = (tax.credit_note_tax_code.id
                    if tax.credit_note_tax_code else None)
                changes['tax_sign'] = tax.credit_note_tax_sign
                changes['account'] = tax.credit_note_account.id
        return changes

    def on_change_with_amount(self):
        Tax = Pool().get('account.tax')
        if self.tax and self.manual:
            tax = self.tax
            base = self.base or Decimal(0)
            for values in Tax.compute([tax], base, 1):
                if (values['tax'] == tax
                        and values['base'] == base):
                    return values['amount']
        return self.amount

    @classmethod
    def check_modify(cls, taxes):
        '''
        Check if the taxes can be modified
        '''
        for tax in taxes:
            if tax.invoice.state in ('posted', 'paid'):
                cls.raise_user_error('modify')

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
    def write(cls, taxes, vals):
        cls.check_modify(taxes)
        super(InvoiceTax, cls).write(taxes, vals)

    @classmethod
    def create(cls, vlist):
        Invoice = Pool().get('account.invoice')
        invoice_ids = []
        for vals in vlist:
            if vals.get('invoice'):
                invoice_ids.append(vals['invoice'])
        for invoice in Invoice.browse(invoice_ids):
            if invoice.state in ('posted', 'paid', 'cancel'):
                cls.raise_user_error('create')
        return super(InvoiceTax, cls).create(vlist)

    @classmethod
    def validate(cls, taxes):
        super(InvoiceTax, cls).validate(taxes)
        for tax in taxes:
            tax.check_company()

    def check_company(self):
        company = self.invoice.company
        if self.account.company != company:
            self.raise_user_error('invalid_account_company', {
                    'invoice': self.invoice.rec_name,
                    'invoice_company': self.invoice.company.rec_name,
                    'account': self.account.rec_name,
                    'account_company': self.account.company.rec_name,
                    })
        if self.base_code:
            if self.base_code.company != company:
                self.raise_user_error('invalid_base_code_company', {
                        'invoice': self.invoice.rec_name,
                        'invoice_company': self.invoice.company.rec_name,
                        'base_code': self.base_code.rec_name,
                        'base_code_company': self.base_code.company.rec_name,
                        })
        if self.tax_code:
            if self.tax_code.company != company:
                self.raise_user_error('invalid_tax_code_company', {
                        'invoice': self.invoice.rec_name,
                        'invoice_company': self.invoice.company.rec_name,
                        'tax_code': self.tax_code.rec_name,
                        'tax_code_company': self.tax_code.company.rec_name,
                        })

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
            res['amount_second_currency'] = Decimal('0.0')
            res['second_currency'] = None
        if self.invoice.type in ('in_invoice', 'out_credit_note'):
            if amount >= Decimal('0.0'):
                res['debit'] = amount
                res['credit'] = Decimal('0.0')
            else:
                res['debit'] = Decimal('0.0')
                res['credit'] = - amount
                res['amount_second_currency'] = - res['amount_second_currency']
        else:
            if amount >= Decimal('0.0'):
                res['debit'] = Decimal('0.0')
                res['credit'] = amount
                res['amount_second_currency'] = - res['amount_second_currency']
            else:
                res['debit'] = - amount
                res['credit'] = Decimal('0.0')
        res['account'] = self.account.id
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

        for field in ('description', 'sequence', 'base', 'amount',
                'manual', 'base_sign', 'tax_sign'):
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
    print_ = StateAction('account_invoice.report_invoice')

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

        res = super(InvoiceReport, cls).execute(ids, data)
        if len(ids) > 1:
            res = (res[0], res[1], True, res[3])
        else:
            invoice = Invoice(ids[0])
            if invoice.number:
                res = (res[0], res[1], res[2], res[3] + ' - ' + invoice.number)
        return res

    @classmethod
    def _get_records(cls, ids, model, data):
        with Transaction().set_context(language=False):
            return super(InvoiceReport, cls)._get_records(ids[:1], model, data)

    @classmethod
    def parse(cls, report, records, data, localcontext):
        pool = Pool()
        User = pool.get('res.user')
        Invoice = pool.get('account.invoice')

        invoice = records[0]

        if invoice.invoice_report_cache:
            return (invoice.invoice_report_format,
                invoice.invoice_report_cache)

        user = User(Transaction().user)
        localcontext['company'] = user.company
        res = super(InvoiceReport, cls).parse(report, records, data,
                localcontext)
        # If the invoice is posted or paid and the report not saved in
        # invoice_report_cache there was an error somewhere. So we save it now
        # in invoice_report_cache
        if (invoice.state in ('posted', 'paid')
                and invoice.type in ('out_invoice', 'out_credit_note')):
            Invoice.write([Invoice(invoice.id)], {
                'invoice_report_format': res[0],
                'invoice_report_cache': res[1],
                })
        return res


class PayInvoiceStart(ModelView):
    'Pay Invoice'
    __name__ = 'account.invoice.pay.start'
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'], required=True)
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    currency_digits = fields.Integer('Currency Digits', readonly=True,
            on_change_with=['currency'])
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
        states={
            'invisible': Eval('type') != 'writeoff',
            'required': Eval('type') == 'writeoff',
            }, depends=['type'])
    account_writeoff = fields.Many2One('account.account', 'Write-Off Account',
        domain=[
            ('kind', '!=', 'view'),
            ('company', '=', Eval('context', {}).get('company', 0)),
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
            ('reconciliation', '=', False),
            ],
        states={
            'invisible': Eval('type') != 'writeoff',
            }, on_change=['lines', 'amount', 'currency', 'currency_writeoff',
            'invoice'],
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

    def on_change_lines(self):
        Currency = Pool().get('currency.currency')

        res = {}
        with Transaction().set_context(date=self.invoice.currency_date):
            amount = Currency.compute(self.currency, self.amount,
                self.currency_writeoff)

        res['amount_writeoff'] = Decimal('0.0')
        for line in self.lines:
            res['amount_writeoff'] += line.debit - line.credit
        if self.invoice.type in ('in_invoice', 'out_credit_note'):
            res['amount_writeoff'] = - res['amount_writeoff'] - amount
        else:
            res['amount_writeoff'] = res['amount_writeoff'] - amount
        return res


class PayInvoice(Wizard):
    'Pay Invoice'
    __name__ = 'account.invoice.pay'
    start = StateView('account.invoice.pay.start',
        'account_invoice.pay_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Ok', 'choice', 'tryton-ok', default=True),
            ])
    choice = StateTransition()
    ask = StateView('account.invoice.pay.ask',
        'account_invoice.pay_ask_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Ok', 'pay', 'tryton-ok', default=True),
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
        _, remainder = invoice.get_reconcile_lines_for_amount(amount)
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
            default['lines'] = [x.id for x in invoice.lines_to_pay]
        else:
            default['lines'], _ = \
                invoice.get_reconcile_lines_for_amount(amount)
        for line_id in default['lines'][:]:
            if line_id not in default['lines_to_pay']:
                default['lines'].remove(line_id)

        default['amount_writeoff'] = Decimal('0.0')
        for line in Line.browse(default['lines']):
            default['amount_writeoff'] += line.debit - line.credit
        for line in invoice.payment_lines:
            default['amount_writeoff'] += line.debit - line.credit
        if invoice.type in ('in_invoice', 'out_credit_note'):
            default['amount_writeoff'] = - default['amount_writeoff'] - amount
        else:
            default['amount_writeoff'] = default['amount_writeoff'] - amount

        default['currency_writeoff'] = invoice.company.currency.id
        default['currency_digits_writeoff'] = invoice.company.currency.digits
        default['invoice'] = invoice.id
        default['payment_lines'] = [x.id for x in invoice.payment_lines
                if not x.reconciliation]

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
            invoice.get_reconcile_lines_for_amount(amount)

        amount_second_currency = None
        second_currency = None
        if self.start.currency != invoice.company.currency:
            amount_second_currency = self.start.amount
            second_currency = self.start.currency

        if amount > invoice.amount_to_pay and \
                self.ask.type != 'writeoff':
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
                        date=self.start.date,
                        account=self.ask.account_writeoff)
        else:
            if line:
                reconcile_lines += [line]
            if reconcile_lines:
                MoveLine.reconcile(reconcile_lines)
        return 'end'


class CreditInvoiceStart(ModelView):
    'Credit Invoice Init'
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
                    'a supplier invoice/credit note.'),
                })

    def default_start(self, fields):
        Invoice = Pool().get('account.invoice')
        default = {
            'with_refund': True,
            }
        for invoice in Invoice.browse(Transaction().context['active_ids']):
            if (invoice.state != 'posted'
                    or invoice.payment_lines
                    or invoice.type in ('in_invoice', 'in_credit_note')):
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
                    self.raise_user_error('refund_supplier')

        credit_invoices = Invoice.credit(invoices, refund=refund)

        data = {'res_id': [i.id for i in credit_invoices]}
        if len(credit_invoices) == 1:
            action['views'].reverse()
        return action, data
