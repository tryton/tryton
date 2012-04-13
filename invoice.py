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
from trytond.pyson import If, Eval, Bool
from trytond.tools import reduce_ids
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.config import CONFIG

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
    _name = 'account.invoice'
    _description = __doc__
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
        ('proforma', 'Pro forma'),
        ('open', 'Opened'),
        ('paid', 'Paid'),
        ('cancel', 'Canceled'),
        ], 'State', readonly=True)
    invoice_date = fields.Date('Invoice Date',
        states={
            'readonly': Eval('state').in_(['open', 'paid', 'cancel']),
            'required': Eval('state').in_(['open', 'paid']),
            },
        depends=['state'])
    accounting_date = fields.Date('Accounting Date', states=_STATES,
        depends=_DEPENDS)
    party = fields.Many2One('party.party', 'Party',
        required=True, states=_STATES, depends=_DEPENDS,
        on_change=['party', 'payment_term', 'type', 'company'])
    party_lang = fields.Function(fields.Char('Party Language',
        on_change_with=['party']), 'get_party_language')
    invoice_address = fields.Many2One('party.address', 'Invoice Address',
        required=True, states=_STATES, depends=['state', 'party'],
        domain=[('party', '=', Eval('party'))])
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states={
            'readonly': ((Eval('state') != 'draft')
                | (Eval('lines') & Eval('currency'))),
            }, depends=['state', 'lines'])
    currency_digits = fields.Function(fields.Integer('Currency Digits',
        on_change_with=['currency']), 'get_currency_digits')
    currency_date = fields.Function(fields.Date('Currency Date',
        on_change_with=['invoice_date']), 'get_currency_date',)
    journal = fields.Many2One('account.journal', 'Journal', required=True,
        states=_STATES, depends=_DEPENDS, domain=[('centralised', '=', False)])
    move = fields.Many2One('account.move', 'Move', readonly=True)
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

    def __init__(self):
        super(Invoice, self).__init__()
        self._check_modify_exclude = ['state', 'payment_lines',
                'invoice_report_cache', 'invoice_report_format']
        self._constraints += [
            ('check_account', 'account_different_company'),
            ('check_account2', 'same_account_on_line'),
        ]
        self._order.insert(0, ('number', 'DESC'))
        self._order.insert(1, ('id', 'DESC'))
        self._error_messages.update({
            'reset_draft': 'You can not reset to draft ' \
                    'an invoice that has move!',
            'missing_tax_line': 'Taxes defined ' \
                    'but not on invoice lines!\n' \
                    'Re-compute the invoice.',
            'diff_tax_line': 'Base taxes ' \
                    'different from invoice lines!\n' \
                    'Re-compute the invoice.',
            'missing_tax_line2': 'Taxes defined ' \
                    'on invoice lines but not on invoice!\n' \
                    'Re-compute the invoice.',
            'no_invoice_sequence': 'There is no invoice sequence ' \
                    'on the period/fiscal year!',
            'modify_invoice': 'You can not modify an invoice that is ' \
                    'opened, paid!',
            'same_debit_account': 'The debit account on journal is ' \
                    'the same than the invoice account!',
            'missing_debit_account': 'The debit account on journal is ' \
                    'missing!',
            'same_credit_account': 'The credit account on journal is ' \
                    'the same than the invoice account!',
            'missing_credit_account': 'The credit account on journal is ' \
                    'missing!',
            'account_different_company': 'You can not create an invoice\n' \
                    'with account from a different invoice company!',
            'same_account_on_line': 'You can not use the same account\n' \
                    'as on invoice line!',
            'delete_cancel': 'Invoice "%s" must be cancelled before deletion!',
            })
        self._transitions |= set((
                ('draft', 'proforma'),
                ('proforma', 'open'),
                ('draft', 'open'),
                ('open', 'paid'),
                ('proforma', 'draft'),
                ('paid', 'open'),
                ('draft', 'cancel'),
                ('proforma', 'cancel'),
                ('cancel', 'draft'),
                ))
        self._buttons.update({
                'cancel': {
                    'invisible': ~Eval('state').in_(['draft', 'proforma']),
                    },
                'draft': {
                    'invisible': ~Eval('state').in_(['cancel', 'proforma']),
                    'icon': If(Eval('state') == 'cancel', 'tryton-clear',
                        'tryton-go-previous'),
                    },
                'proforma': {
                    'invisible': Eval('state') != 'draft',
                    },
                'open': {
                    'invisible': ~Eval('state').in_(['draft', 'proforma']),
                    },
                })

    def init(self, module_name):
        super(Invoice, self).init(module_name)
        cursor = Transaction().cursor
        table = TableHandler(cursor, self, module_name)

        # Migration from 1.2 invoice_date is no more required
        table.not_null_action('invoice_date', action='remove')

        # Migration from 2.0 invoice_report renamed into invoice_report_cache
        # to remove base64 encoding

        if (table.column_exist('invoice_report')
                and table.column_exist('invoice_report_cache')):
            limit = cursor.IN_MAX
            cursor.execute('SELECT COUNT(id) '
                'FROM "' + self._table + '"')
            invoice_count, = cursor.fetchone()
            for offset in range(0, invoice_count, limit):
                cursor.execute(cursor.limit_clause(
                    'SELECT id, invoice_report '
                    'FROM "' + self._table + '"'
                    'ORDER BY id',
                    limit, offset))
                for invoice_id, report in cursor.fetchall():
                    if report:
                        report = buffer(base64.decodestring(str(report)))
                        cursor.execute('UPDATE "' + self._table + '" '
                            'SET invoice_report_cache = %s '
                            'WHERE id = %s', (report, invoice_id))
            table.drop_column('invoice_report')

        # Add index on create_date
        table.index_action('create_date', action='add')

    def default_type(self):
        return Transaction().context.get('type', 'out_invoice')

    def default_state(self):
        return 'draft'

    def default_currency(self):
        company_obj = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = company_obj.browse(Transaction().context['company'])
            return company.currency.id

    def default_currency_digits(self):
        company_obj = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = company_obj.browse(Transaction().context['company'])
            return company.currency.digits
        return 2

    def default_company(self):
        return Transaction().context.get('company')

    def default_payment_term(self):
        payment_term_obj = Pool().get('account.invoice.payment_term')
        payment_term_ids = payment_term_obj.search(self.payment_term.domain)
        if len(payment_term_ids) == 1:
            return payment_term_ids[0]

    def __get_account_payment_term(self, type_, party_id, company_id):
        '''
        Return default account and payment term
        '''
        pool = Pool()
        party_obj = pool.get('party.party')
        company_obj = pool.get('company.company')
        account_obj = pool.get('account.account')
        payment_term_obj = pool.get('account.invoice.payment_term')

        result = {
            'account': None,
            }
        if party_id:
            party = party_obj.browse(party_id)
            if type_ in ('out_invoice', 'out_credit_note'):
                result['account'] = party.account_receivable.id
                if type_ == 'out_invoice' and party.customer_payment_term:
                    result['payment_term'] = party.customer_payment_term.id
            elif type_ in ('in_invoice', 'in_credit_note'):
                result['account'] = party.account_payable.id
                if type_ == 'in_invoice' and party.supplier_payment_term:
                    result['payment_term'] = party.supplier_payment_term.id
        if company_id and type_ in ('out_credit_note', 'in_credit_note'):
            company = company_obj.browse(company_id)
            if type_ == 'out_credit_note':
                result['payment_term'] = company.customer_payment_term.id
            else:
                result['payment_term'] = company.supplier_payment_term.id
        if result['account']:
            result['account.rec_name'] = account_obj.browse(
                    result['account']).rec_name
        if result.get('payment_term'):
            result['payment_term.rec_name'] = payment_term_obj.browse(
                    result['payment_term']).rec_name
        return result

    def on_change_type(self, vals):
        journal_obj = Pool().get('account.journal')
        res = {}
        journal_ids = journal_obj.search([
            ('type', '=', _TYPE2JOURNAL.get(vals.get('type', 'out_invoice'),
                'revenue')),
            ], limit=1)
        if journal_ids:
            journal = journal_obj.browse(journal_ids[0])
            res['journal'] = journal.id
            res['journal.rec_name'] = journal.rec_name
        res.update(self.__get_account_payment_term(vals.get('type'),
                vals.get('party'), vals.get('company')))
        return res

    def on_change_party(self, vals):
        pool = Pool()
        party_obj = pool.get('party.party')
        address_obj = pool.get('party.address')
        res = {
            'invoice_address': None,
        }
        res.update(self.__get_account_payment_term(vals.get('type'),
                vals.get('party'), vals.get('company')))

        if vals.get('party'):
            party = party_obj.browse(vals['party'])
            res['invoice_address'] = party_obj.address_get(party.id,
                    type='invoice')
        if res['invoice_address']:
            res['invoice_address.rec_name'] = address_obj.browse(
                    res['invoice_address']).rec_name
        return res

    def on_change_with_currency_digits(self, vals):
        currency_obj = Pool().get('currency.currency')
        if vals.get('currency'):
            currency = currency_obj.browse(vals['currency'])
            return currency.digits
        return 2

    def get_currency_digits(self, ids, name):
        res = {}
        for invoice in self.browse(ids):
            res[invoice.id] = invoice.currency.digits
        return res

    def on_change_with_currency_date(self, vals):
        date_obj = Pool().get('ir.date')
        today = date_obj.today()
        date = vals.get('invoice_date') or today
        return date

    def get_currency_date(self, ids, name):
        date_obj = Pool().get('ir.date')
        res = {}
        today = date_obj.today()
        for invoice in self.browse(ids):
            res[invoice.id] = invoice.invoice_date or today
        return res

    def on_change_with_party_lang(self, vals):
        party_obj = Pool().get('party.party')
        if vals.get('party'):
            party = party_obj.browse(vals['party'])
            if party.lang:
                return party.lang.code
        return CONFIG['language']

    def get_party_language(self, ids, name):
        '''
        Return the language code of the party of each invoice

        :param ids: the ids of the invoices
        :param name: the field name
        :return: a dictionary with invoice id as key and
            language code as value
        '''
        res = {}
        for invoice in self.browse(ids):
            if invoice.party.lang:
                res[invoice.id] = invoice.party.lang.code
            else:
                res[invoice.id] = CONFIG['language']
        return res

    def get_type_name(self, ids, name):
        res = {}
        type2name = {}
        for type, name in self.fields_get(fields_names=['type']
                )['type']['selection']:
            type2name[type] = name
        for invoice in self.browse(ids):
            res[invoice.id] = type2name[invoice.type]
        return res

    def on_change_lines(self, vals):
        return self._on_change_lines_taxes(vals)

    def on_change_taxes(self, vals):
        return self._on_change_lines_taxes(vals)

    def _on_change_lines_taxes(self, vals):
        currency_obj = Pool().get('currency.currency')
        tax_obj = Pool().get('account.tax')
        res = {
            'untaxed_amount': Decimal('0.0'),
            'tax_amount': Decimal('0.0'),
            'total_amount': Decimal('0.0'),
            'taxes': {},
        }
        currency = None
        if vals.get('currency'):
            currency = currency_obj.browse(vals['currency'])
        computed_taxes = {}
        if vals.get('lines'):
            context = self.get_tax_context(vals)
            for line in vals['lines']:
                if line.get('type', 'line') != 'line':
                    continue
                res['untaxed_amount'] += line.get('amount') or 0
                with Transaction().set_context(**context):
                    taxes = tax_obj.compute(line.get('taxes', []),
                            line.get('unit_price', Decimal('0.0')),
                            line.get('quantity', 0.0))
                for tax in taxes:
                    key, val = self._compute_tax(tax,
                            vals.get('type', 'out_invoice'))
                    if not key in computed_taxes:
                        computed_taxes[key] = val
                    else:
                        computed_taxes[key]['base'] += val['base']
                        computed_taxes[key]['amount'] += val['amount']
        if currency:
            for key in computed_taxes:
                for field in ('base', 'amount'):
                    computed_taxes[key][field] = currency_obj.round(currency,
                            computed_taxes[key][field])
        tax_keys = []
        for tax in vals.get('taxes', []):
            if tax.get('manual', False):
                res['tax_amount'] += tax.get('amount', Decimal('0.0'))
                continue
            key = (tax.get('base_code'), tax.get('base_sign'),
                    tax.get('tax_code'), tax.get('tax_sign'),
                    tax.get('account'), tax.get('tax'))
            if (key not in computed_taxes) or (key in tax_keys):
                res['taxes'].setdefault('remove', [])
                res['taxes']['remove'].append(tax.get('id'))
                continue
            tax_keys.append(key)
            if currency:
                if not currency_obj.is_zero(currency,
                        computed_taxes[key]['base'] - \
                                tax.get('base', Decimal('0.0'))):
                    res['tax_amount'] += computed_taxes[key]['amount']
                    res['taxes'].setdefault('update', [])
                    res['taxes']['update'].append({
                        'id': tax.get('id'),
                        'amount': computed_taxes[key]['amount'],
                        'base': computed_taxes[key]['base'],
                        })
                else:
                    res['tax_amount'] += tax.get('amount', Decimal('0.0'))
            else:
                if computed_taxes[key]['base'] - \
                        tax.get('base', Decimal('0.0')) != Decimal('0.0'):
                    res['tax_amount'] += computed_taxes[key]['amount']
                    res['taxes'].setdefault('update', [])
                    res['taxes']['update'].append({
                        'id': tax.get('id'),
                        'amount': computed_taxes[key]['amount'],
                        'base': computed_taxes[key]['base'],
                        })
                else:
                    res['tax_amount'] += tax.get('amount', Decimal('0.0'))
        for key in computed_taxes:
            if key not in tax_keys:
                res['tax_amount'] += computed_taxes[key]['amount']
                res['taxes'].setdefault('add', [])
                value = tax_obj.default_get(tax_obj._columns.keys())
                value.update(computed_taxes[key])
                res['taxes']['add'].append(value)
        if currency:
            res['untaxed_amount'] = currency_obj.round(currency,
                    res['untaxed_amount'])
            res['tax_amount'] = currency_obj.round(currency, res['tax_amount'])
        res['total_amount'] = res['untaxed_amount'] + res['tax_amount']
        if currency:
            res['total_amount'] = currency_obj.round(currency,
                    res['total_amount'])
        return res

    def get_untaxed_amount(self, ids, name):
        currency_obj = Pool().get('currency.currency')
        res = {}
        for invoice in self.browse(ids):
            res.setdefault(invoice.id, _ZERO)
            for line in invoice.lines:
                if line.type != 'line':
                    continue
                res[invoice.id] += line.amount
            res[invoice.id] = currency_obj.round(invoice.currency,
                    res[invoice.id])
        return res

    def get_tax_amount(self, ids, name):
        currency_obj = Pool().get('currency.currency')
        cursor = Transaction().cursor
        res = {}
        type_name = FIELDS[self.tax_amount._type].sql_type(self.tax_amount)[0]
        red_sql, red_ids = reduce_ids('invoice', ids)
        cursor.execute('SELECT invoice, ' \
                    'CAST(COALESCE(SUM(amount), 0) AS ' + type_name + ') ' \
                'FROM account_invoice_tax ' \
                'WHERE ' + red_sql + ' ' \
                'GROUP BY invoice', red_ids)
        for invoice_id, sum in cursor.fetchall():
            # SQLite uses float for SUM
            if not isinstance(sum, Decimal):
                sum = Decimal(str(sum))
            res[invoice_id] = sum

        for invoice in self.browse(ids):
            res.setdefault(invoice.id, Decimal('0.0'))
            res[invoice.id] = currency_obj.round(invoice.currency,
                    res[invoice.id])
        return res

    def get_total_amount(self, ids, name):
        currency_obj = Pool().get('currency.currency')
        res = {}
        for invoice in self.browse(ids):
            res[invoice.id] = currency_obj.round(invoice.currency,
                    invoice.untaxed_amount + invoice.tax_amount)
        return res

    def get_reconciled(self, ids, name):
        res = {}
        for invoice in self.browse(ids):
            res[invoice.id] = True
            if not invoice.lines_to_pay:
                res[invoice.id] = False
                continue
            for line in invoice.lines_to_pay:
                if not line.reconciliation:
                    res[invoice.id] = False
                    break
        return res

    def get_lines_to_pay(self, ids, name):
        res = {}
        for invoice in self.browse(ids):
            lines = []
            if invoice.move:
                for line in invoice.move.lines:
                    if line.account.id == invoice.account.id \
                            and line.maturity_date:
                        lines.append(line)
            lines.sort(key=operator.attrgetter('maturity_date'))
            res[invoice.id] = [x.id for x in lines]
        return res

    def get_amount_to_pay(self, ids, name):
        currency_obj = Pool().get('currency.currency')
        date_obj = Pool().get('ir.date')

        compute_ids = self.search([
            ('id', 'in', ids),
            ('state', '=', 'open'),
            ])

        res = dict((x, _ZERO) for x in ids)
        for invoice in self.browse(compute_ids):
            amount = _ZERO
            amount_currency = _ZERO
            for line in invoice.lines_to_pay:
                if line.reconciliation:
                    continue
                if name == 'amount_to_pay_today' \
                        and line.maturity_date > date_obj.today():
                    continue
                if line.second_currency.id == invoice.currency.id:
                    if line.debit - line.credit > _ZERO:
                        amount_currency += abs(line.amount_second_currency)
                    else:
                        amount_currency -= abs(line.amount_second_currency)
                else:
                    amount += line.debit - line.credit
            for line in invoice.payment_lines:
                if line.reconciliation:
                    continue
                if line.second_currency.id == invoice.currency.id:
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
                    amount_currency += currency_obj.compute(
                    invoice.company.currency.id, amount, invoice.currency.id)
            if amount_currency < _ZERO:
                amount_currency = _ZERO
            res[invoice.id] = amount_currency
        return res

    def search_total_amount(self, name, clause):
        pool = Pool()
        rule_obj = pool.get('ir.rule')
        line_obj = pool.get('account.invoice.line')
        tax_obj = pool.get('account.invoice.tax')
        type_name = FIELDS[self.total_amount._type].sql_type(
                self.total_amount)[0]
        cursor = Transaction().cursor

        invoice_query, invoice_val = rule_obj.domain_get('account.invoice')

        cursor.execute('SELECT invoice FROM ('
                    'SELECT invoice, '
                        'COALESCE(SUM(quantity * unit_price), 0) '
                            'AS total_amount '
                    'FROM "' + line_obj._table + '" '
                    'JOIN "' + self._table + '" ON '
                        '("' + self._table + '".id = '
                            '"' + line_obj._table + '".invoice) '
                    'WHERE ' + invoice_query + ' '
                    'GROUP BY invoice '
                'UNION '
                    'SELECT invoice, COALESCE(SUM(amount), 0) AS total_amount '
                    'FROM "' + tax_obj._table + '" '
                    'JOIN "' + self._table + '" ON '
                        '("' + self._table + '".id = '
                            '"' + tax_obj._table + '".invoice) '
                    'WHERE ' + invoice_query + ' '
                    'GROUP BY invoice  '
                ') AS u '
                'GROUP BY u.invoice '
                'HAVING (CAST(SUM(u.total_amount) AS ' + type_name + ') '
                    + clause[1] + ' %s)',
                invoice_val + invoice_val + [str(clause[2])])
        return [('id', 'in', [x[0] for x in cursor.fetchall()])]

    def search_untaxed_amount(self, name, clause):
        pool = Pool()
        rule_obj = pool.get('ir.rule')
        line_obj = pool.get('account.invoice.line')
        type_name = FIELDS[self.untaxed_amount._type].sql_type(
                self.untaxed_amount)[0]
        cursor = Transaction().cursor

        invoice_query, invoice_val = rule_obj.domain_get('account.invoice')

        cursor.execute('SELECT invoice FROM "' + line_obj._table + '" '
                'JOIN "' + self._table + '" ON '
                    '("' + self._table + '".id = '
                        '"' + line_obj._table + '".invoice) '
                'WHERE ' + invoice_query + ' '
                'GROUP BY invoice '
                'HAVING (CAST(COALESCE(SUM(quantity * unit_price), 0) '
                    'AS ' + type_name + ') ' + clause[1] + ' %s)',
                invoice_val + [str(clause[2])])
        return [('id', 'in', [x[0] for x in cursor.fetchall()])]

    def search_tax_amount(self, name, clause):
        pool = Pool()
        rule_obj = pool.get('ir.rule')
        tax_obj = pool.get('account.invoice.tax')
        type_name = FIELDS[self.tax_amount._type].sql_type(
                self.tax_amount)[0]
        cursor = Transaction().cursor

        invoice_query, invoice_val = rule_obj.domain_get('account.invoice')

        cursor.execute('SELECT invoice FROM "' + tax_obj._table + '" '
                'JOIN "' + self._table + '" ON '
                    '("' + self._table + '".id = '
                        '"' + tax_obj._table + '".invoice) '
                'WHERE ' + invoice_query + ' '
                'GROUP BY invoice '
                'HAVING (CAST(COALESCE(SUM(amount), 0) '
                    'AS ' + type_name + ') ' + clause[1] + ' %s)',
                invoice_val + [str(clause[2])])
        return [('id', 'in', [x[0] for x in cursor.fetchall()])]

    def get_tax_context(self, invoice):
        party_obj = Pool().get('party.party')
        res = {}
        if isinstance(invoice, dict):
            if invoice.get('party'):
                party = party_obj.browse(invoice['party'])
                if party.lang:
                    res['language'] = party.lang.code
        else:
            if invoice.party.lang:
                res['language'] = invoice.party.lang.code
        return res

    def _compute_tax(self, tax, invoice_type):
        val = {}
        val['manual'] = False
        val['description'] = tax['tax'].description
        val['base'] = tax['base']
        val['amount'] = tax['amount']
        val['tax'] = tax['tax'].id

        if invoice_type in ('out_invoice', 'in_invoice'):
            val['base_code'] = tax['tax'].invoice_base_code.id
            val['base_sign'] = tax['tax'].invoice_base_sign
            val['tax_code'] = tax['tax'].invoice_tax_code.id
            val['tax_sign'] = tax['tax'].invoice_tax_sign
            val['account'] = tax['tax'].invoice_account.id
        else:
            val['base_code'] = tax['tax'].credit_note_base_code.id
            val['base_sign'] = tax['tax'].credit_note_base_sign
            val['tax_code'] = tax['tax'].credit_note_tax_code.id
            val['tax_sign'] = tax['tax'].credit_note_tax_sign
            val['account'] = tax['tax'].credit_note_account.id
        key = (val['base_code'], val['base_sign'],
                val['tax_code'], val['tax_sign'],
                val['account'], val['tax'])
        return key, val

    def _compute_taxes(self, invoice):
        tax_obj = Pool().get('account.tax')
        currency_obj = Pool().get('currency.currency')

        context = self.get_tax_context(invoice)

        res = {}
        for line in invoice.lines:
            # Don't round on each line to handle rounding error
            if line.type != 'line':
                continue
            tax_ids = [x.id for x in line.taxes]
            with Transaction().set_context(**context):
                taxes = tax_obj.compute(tax_ids, line.unit_price,
                        line.quantity)
            for tax in taxes:
                key, val = self._compute_tax(tax, invoice.type)
                val['invoice'] = invoice.id
                if not key in res:
                    res[key] = val
                else:
                    res[key]['base'] += val['base']
                    res[key]['amount'] += val['amount']
        for key in res:
            for field in ('base', 'amount'):
                res[key][field] = currency_obj.round(invoice.currency,
                        res[key][field])
        return res

    def update_taxes(self, ids, exception=False):
        tax_obj = Pool().get('account.invoice.tax')
        currency_obj = Pool().get('currency.currency')
        for invoice in self.browse(ids):
            if invoice.state in ('open', 'paid', 'cancel'):
                continue
            computed_taxes = self._compute_taxes(invoice)
            if not invoice.taxes:
                for tax in computed_taxes.values():
                    tax_obj.create(tax)
            else:
                tax_keys = []
                for tax in invoice.taxes:
                    if tax.manual:
                        continue
                    key = (tax.base_code.id, tax.base_sign,
                            tax.tax_code.id, tax.tax_sign,
                            tax.account.id, tax.tax.id)
                    if (not key in computed_taxes) or (key in tax_keys):
                        if exception:
                            self.raise_user_error('missing_tax_line')
                        tax_obj.delete(tax.id)
                        continue
                    tax_keys.append(key)
                    if not currency_obj.is_zero(invoice.currency,
                            computed_taxes[key]['base'] - tax.base):
                        if exception:
                            self.raise_user_error('diff_tax_line')
                        tax_obj.write(tax.id, computed_taxes[key])
                for key in computed_taxes:
                    if not key in tax_keys:
                        if exception:
                            self.raise_user_error('missing_tax_line')
                        tax_obj.create(computed_taxes[key])
        return True

    def _get_move_line_invoice_line(self, invoice):
        '''
        Return list of move line values for each invoice lines
        '''
        line_obj = Pool().get('account.invoice.line')
        res = []
        for line in invoice.lines:
            val = line_obj.get_move_line(line)
            if val:
                res.extend(val)
        return res

    def _get_move_line_invoice_tax(self, invoice):
        '''
        Return list of move line values for each invoice taxes
        '''
        tax_obj = Pool().get('account.invoice.tax')
        res = []
        for tax in invoice.taxes:
            val = tax_obj.get_move_line(tax)
            if val:
                res.extend(val)
        return res

    def _get_move_line(self, invoice, date, amount):
        '''
        Return move line
        '''
        currency_obj = Pool().get('currency.currency')
        res = {}
        if invoice.currency.id != invoice.company.currency.id:
            with Transaction().set_context(date=invoice.currency_date):
                res['amount_second_currency'] = currency_obj.compute(
                    invoice.company.currency.id, amount, invoice.currency.id)
            res['amount_second_currency'] = abs(res['amount_second_currency'])
            res['second_currency'] = invoice.currency.id
        else:
            res['amount_second_currency'] = Decimal('0.0')
            res['second_currency'] = None
        if amount >= Decimal('0.0'):
            res['debit'] = Decimal('0.0')
            res['credit'] = amount
        else:
            res['debit'] = - amount
            res['credit'] = Decimal('0.0')
        res['account'] = invoice.account.id
        res['maturity_date'] = date
        res['reference'] = invoice.reference
        res['name'] = invoice.number
        res['party'] = invoice.party.id
        return res

    def create_move(self, invoice):
        '''
        Create account move for the invoice and return the created move id
        '''
        pool = Pool()
        payment_term_obj = pool.get('account.invoice.payment_term')
        currency_obj = pool.get('currency.currency')
        move_obj = pool.get('account.move')
        period_obj = pool.get('account.period')

        if invoice.move:
            return True
        self.update_taxes([invoice.id], exception=True)
        move_lines = self._get_move_line_invoice_line(invoice)
        move_lines += self._get_move_line_invoice_tax(invoice)

        total = Decimal('0.0')
        total_currency = Decimal('0.0')
        for line in move_lines:
            total += line['debit'] - line['credit']
            total_currency += line['amount_second_currency']

        term_lines = payment_term_obj.compute(total, invoice.company.currency,
                invoice.payment_term, invoice.invoice_date)
        remainder_total_currency = total_currency
        for date, amount in term_lines:
            val = self._get_move_line(invoice, date, amount)
            remainder_total_currency -= val['amount_second_currency']
            move_lines.append(val)
        if not currency_obj.is_zero(invoice.currency,
                remainder_total_currency):
            move_lines[-1]['amount_second_currency'] += \
                remainder_total_currency

        accounting_date = invoice.accounting_date or invoice.invoice_date
        period_id = period_obj.find(invoice.company.id, date=accounting_date)

        move_id = move_obj.create({
            'journal': invoice.journal.id,
            'period': period_id,
            'date': accounting_date,
            'lines': [('create', x) for x in move_lines],
            })
        self.write(invoice.id, {
            'move': move_id,
            })
        move_obj.post(move_id)
        return move_id

    def set_number(self, invoice):
        '''
        Set number to the invoice
        '''
        pool = Pool()
        period_obj = pool.get('account.period')
        sequence_obj = pool.get('ir.sequence.strict')
        date_obj = pool.get('ir.date')

        if invoice.number:
            return

        test_state = True
        if invoice.type in ('in_invoice', 'in_credit_note'):
            test_state = False

        period_id = period_obj.find(invoice.company.id,
                date=invoice.invoice_date, test_state=test_state)
        period = period_obj.browse(period_id)
        sequence_id = period[invoice.type + '_sequence'].id
        if not sequence_id:
            self.raise_user_error('no_invoice_sequence')
        with Transaction().set_context(
                date=invoice.invoice_date or date_obj.today()):
            number = sequence_obj.get_id(sequence_id)
            vals = {'number': number}
            if not invoice.invoice_date:
                vals['invoice_date'] = Transaction().context['date']
        self.write(invoice.id, vals)

    def check_modify(self, ids):
        '''
        Check if the invoices can be modified
        '''
        for invoice in self.browse(ids):
            if invoice.state in ('open', 'paid'):
                self.raise_user_error('modify_invoice')
        return

    def get_rec_name(self, ids, name):
        if not ids:
            return {}
        res = {}
        for invoice in self.browse(ids):
            res[invoice.id] = invoice.number or unicode(invoice.id) + \
                    (invoice.reference and (' ' + invoice.reference) or '') + \
                    ' ' + invoice.party.rec_name
        return res

    def search_rec_name(self, name, clause):
        ids = self.search(['OR',
            ('number',) + clause[1:],
            ('reference',) + clause[1:],
            ], order=[])
        if ids:
            return [('id', 'in', ids)]
        return [('party',) + clause[1:]]

    def delete(self, ids):
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.check_modify(ids)
        # Cancel before delete
        self.cancel(ids)
        for invoice in self.browse(ids):
            if invoice.state != 'cancel':
                self.raise_user_error('delete_cancel', invoice.rec_name)
        return super(Invoice, self).delete(ids)

    def write(self, ids, vals):
        if isinstance(ids, (int, long)):
            ids = [ids]
        keys = vals.keys()
        for key in self._check_modify_exclude:
            if key in keys:
                keys.remove(key)
        if len(keys):
            self.check_modify(ids)
        update_tax_ids = [x.id for x in self.browse(ids) if x.state == 'draft']
        res = super(Invoice, self).write(ids, vals)
        if update_tax_ids:
            self.update_taxes(update_tax_ids)
        return res

    def copy(self, ids, default=None):
        pool = Pool()
        line_obj = pool.get('account.invoice.line')
        tax_obj = pool.get('account.invoice.tax')

        int_id = False
        if isinstance(ids, (int, long)):
            int_id = True
            ids = [ids]

        if default is None:
            default = {}
        default = default.copy()
        default['state'] = 'draft'
        default['number'] = None
        default['move'] = None
        default['invoice_report_cache'] = None
        default['invoice_report_format'] = None
        default['payment_lines'] = None
        default['lines'] = None
        default['taxes'] = None
        default.setdefault('invoice_date', None)
        default.setdefault('accounting_date', None)
        default['lines_to_pay'] = None

        new_ids = []
        for invoice in self.browse(ids):
            new_id = super(Invoice, self).copy(invoice.id, default=default)
            line_obj.copy([x.id for x in invoice.lines], default={
                'invoice': new_id,
                })
            tax_obj.copy([x.id for x in invoice.taxes], default={
                'invoice': new_id,
                })
            new_ids.append(new_id)

        if int_id:
            return new_ids[0]
        return new_ids

    def check_account(self, ids):
        for invoice in self.browse(ids):
            if invoice.account.company.id != invoice.company.id:
                return False
        return True

    def check_account2(self, ids):
        for invoice in self.browse(ids):
            for line in invoice.lines:
                if line.type == 'line' \
                        and line.account.id == invoice.account.id:
                    return False
        return True

    def get_reconcile_lines_for_amount(self, invoice, amount,
            exclude_ids=None):
        '''
        Return list of line ids and the remainder to make reconciliation.
        '''
        currency_obj = Pool().get('currency.currency')

        if exclude_ids is None:
            exclude_ids = []
        payment_amount = Decimal('0.0')
        remainder = invoice.total_amount
        lines = []
        payment_lines = []

        for line in invoice.payment_lines:
            if line.reconciliation:
                continue
            payment_amount += line.debit - line.credit
            payment_lines.append(line.id)

        if invoice.type in ('out_invoice', 'in_credit_note'):
            amount = - abs(amount)
        else:
            amount = abs(amount)

        for line in invoice.lines_to_pay:

            if line.reconciliation:
                continue
            if line.id in exclude_ids:
                continue

            test_amount = amount + (line.debit - line.credit)
            if currency_obj.is_zero(invoice.currency, test_amount):
                return ([line.id], Decimal('0.0'))
            if abs(test_amount) < abs(remainder):
                lines = [line.id]
                remainder = test_amount

            test_amount = (amount + payment_amount)
            test_amount += (line.debit - line.credit)
            if currency_obj.is_zero(invoice.currency, test_amount):
                return ([line.id] + payment_lines, Decimal('0.0'))
            if abs(test_amount) < abs(remainder):
                lines = [line.id] + payment_lines
                remainder = test_amount

            exclude_ids2 = exclude_ids[:]
            exclude_ids2.append(line.id)
            res = self.get_reconcile_lines_for_amount(invoice,
                    (amount + (line.debit - line.credit)),
                    exclude_ids=exclude_ids2)
            if res[1] == Decimal('0.0'):
                res[0].append(line.id)
                return res
            if abs(res[1]) < abs(remainder):
                res[0].append(line.id)
                lines = res[0]
                remainder = res[1]

        return (lines, remainder)

    def pay_invoice(self, invoice_id, amount, journal_id, date, description,
            amount_second_currency=None, second_currency=None):
        '''
        Add a payment to an invoice

        :param invoice_id: the invoice id
        :param amount: the amount to pay
        :param journal_id: the journal id for the move
        :param date: the date of the move
        :param description: the description of the move
        :param amount_second_currency: the amount in the second currenry if one
        :param second_currency: the id of the second currency
        :return: the id of the payment line
        '''
        pool = Pool()
        journal_obj = pool.get('account.journal')
        move_obj = pool.get('account.move')
        period_obj = pool.get('account.period')

        lines = []
        invoice = self.browse(invoice_id)
        journal = journal_obj.browse(journal_id)

        if invoice.type in ('out_invoice', 'in_credit_note'):
            lines.append({
                'name': description,
                'account': invoice.account.id,
                'party': invoice.party.id,
                'debit': Decimal('0.0'),
                'credit': amount,
                'amount_second_currency': amount_second_currency,
                'second_currency': second_currency,
            })
            lines.append({
                'name': description,
                'account': journal.debit_account.id,
                'party': invoice.party.id,
                'debit': amount,
                'credit': Decimal('0.0'),
                'amount_second_currency': amount_second_currency,
                'second_currency': second_currency,
            })
            if invoice.account.id == journal.debit_account.id:
                self.raise_user_error('same_debit_account')
            if not journal.debit_account:
                self.raise_user_error('missing_debit_account')
        else:
            lines.append({
                'name': description,
                'account': invoice.account.id,
                'party': invoice.party.id,
                'debit': amount,
                'credit': Decimal('0.0'),
                'amount_second_currency': amount_second_currency,
                'second_currency': second_currency,
            })
            lines.append({
                'name': description,
                'account': journal.credit_account.id,
                'party': invoice.party.id,
                'debit': Decimal('0.0'),
                'credit': amount,
                'amount_second_currency': amount_second_currency,
                'second_currency': second_currency,
            })
            if invoice.account.id == journal.credit_account.id:
                self.raise_user_error('same_credit_account')
            if not journal.credit_account:
                self.raise_user_error('missing_credit_account')

        period_id = period_obj.find(invoice.company.id, date=date)

        move_id = move_obj.create({
            'journal': journal.id,
            'period': period_id,
            'date': date,
            'lines': [('create', x) for x in lines],
            })
        move_obj.post(move_id)

        move = move_obj.browse(move_id)

        for line in move.lines:
            if line.account.id == invoice.account.id:
                self.write(invoice.id, {
                    'payment_lines': [('add', line.id)],
                    })
                return line.id
        raise Exception('Missing account')

    def print_invoice(self, invoice):
        '''
        Generate invoice report and store it in invoice_report field.
        '''
        if invoice.invoice_report_cache:
            return
        invoice_report = Pool().get('account.invoice', type='report')
        invoice_report.execute([invoice.id], {})

    def _credit(self, invoice):
        '''
        Return values to credit invoice.
        '''
        invoice_line_obj = Pool().get('account.invoice.line')
        invoice_tax_obj = Pool().get('account.invoice.tax')

        res = {}
        if invoice.type == 'out_invoice':
            res['type'] = 'out_credit_note'
        elif invoice.type == 'in_invoice':
            res['type'] = 'in_credit_note'
        elif invoice.type == 'out_credit_note':
            res['type'] = 'out_invoice'
        elif invoice.type == 'in_credit_note':
            res['type'] = 'in_invoice'

        for field in ('description', 'comment'):
            res[field] = invoice[field]

        res['reference'] = invoice.number or invoice.reference

        for field in ('company', 'party', 'invoice_address', 'currency',
                'journal', 'account', 'payment_term'):
            res[field] = invoice[field].id

        res['lines'] = []
        for line in invoice.lines:
            value = invoice_line_obj._credit(line)
            res['lines'].append(('create', value))

        res['taxes'] = []
        for tax in invoice.taxes:
            if not tax.manual:
                continue
            value = invoice_tax_obj._credit(tax)
            res['taxes'].append(('create', value))
        return res

    def credit(self, ids, refund=False):
        '''
        Credit invoices and return ids of new invoices.

        :param ids: a list of invoice id
        :param refund: a boolean to specify the refund
        :return: the list of new invoice id
        '''
        move_line_obj = Pool().get('account.move.line')

        new_ids = []
        for invoice in self.browse(ids):
            vals = self._credit(invoice)
            new_id = self.create(vals)
            new_ids.append(new_id)
            if refund:
                self.open([new_id])
                new_invoice = self.browse(new_id)
                if new_invoice.state == 'open':
                    line_ids = [x.id for x in invoice.lines_to_pay
                            if not x.reconciliation] + \
                                    [x.id for x in new_invoice.lines_to_pay
                                            if not x.reconciliation]
                    move_line_obj.reconcile(line_ids)
        return new_ids

    @ModelView.button
    @Workflow.transition('draft')
    def draft(self, ids):
        pass

    @ModelView.button
    @Workflow.transition('proforma')
    def proforma(self, ids):
        pass

    @ModelView.button
    @Workflow.transition('open')
    def open(self, ids):
        for invoice in self.browse(ids):
            self.set_number(invoice)
            self.create_move(invoice)
            self.print_invoice(invoice)

    def process(self, ids):
        paid = []
        open_ = []
        for invoice in self.browse(ids):
            if invoice.state not in ('open', 'paid'):
                continue
            if invoice.reconciled:
                paid.append(invoice.id)
            else:
                open_.append(invoice.id)
        self.paid(paid)
        self.open(open_)

    @Workflow.transition('paid')
    def paid(self, ids):
        pass

    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(self, ids):
        pass

Invoice()


class InvoicePaymentLine(ModelSQL):
    'Invoice - Payment Line'
    _name = 'account.invoice-account.move.line'
    _description = __doc__
    invoice = fields.Many2One('account.invoice', 'Invoice', ondelete='CASCADE',
            select=True, required=True)
    line = fields.Many2One('account.move.line', 'Payment Line',
            ondelete='CASCADE', select=True, required=True)

InvoicePaymentLine()


class InvoiceLine(ModelSQL, ModelView):
    'Invoice Line'
    _name = 'account.invoice.line'
    _rec_name = 'description'
    _description = __doc__

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
        on_change_with=['party']), 'get_party_language')
    currency = fields.Many2One('currency.currency', 'Currency',
        states={
            'required': ~Eval('invoice'),
            },
        depends=['invoice'])
    currency_digits = fields.Function(fields.Integer('Currency Digits',
        on_change_with=['currency']), 'get_currency_digits')
    company = fields.Many2One('company.company', 'Company',
        states={
            'required': ~Eval('invoice'),
            }, domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', 0)),
            ],
        depends=['invoice'], select=True)

    sequence = fields.Integer('Sequence', required=True,
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
        on_change_with=['unit']), 'get_unit_digits')
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
        'get_product_uom_category')
    account = fields.Many2One('account.account', 'Account',
        domain=[
            ('company', '=', Eval('_parent_invoice', {}).get('company',
                    Eval('context', {}).get('company', 0))),
            If(Eval('_parent_invoice', {}).get('type').in_(['out_invoice',
                        'out_credit_note']),
                ('kind', '=', 'revenue'),
                ('kind', '=', 'expense')),
            ],
        on_change=['account', 'product'],
        states={
            'invisible': Eval('type') != 'line',
            'required': Eval('type') == 'line',
            },
        depends=['type'])
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
        'line', 'tax', 'Taxes', domain=[('parent', '=', None)],
        states={
            'invisible': Eval('type') != 'line',
            },
        depends=['type'])
    invoice_taxes = fields.Function(fields.One2Many('account.invoice.tax',
        None, 'Invoice Taxes'), 'get_invoice_taxes')

    def __init__(self):
        super(InvoiceLine, self).__init__()
        self._sql_constraints += [
            ('type_account',
                'CHECK((type = \'line\' AND account IS NOT NULL) ' \
                        'OR (type != \'line\'))',
                'Line with "line" type must have an account!'),
            ('type_invoice',
                'CHECK((type != \'line\' AND invoice IS NOT NULL) ' \
                        'OR (type = \'line\'))',
                'Line without "line" type must have an invoice!'),
        ]
        self._constraints += [
            ('check_account', 'account_different_company'),
            ('check_account2', 'same_account_on_invoice'),
        ]
        self._order.insert(0, ('sequence', 'ASC'))
        self._error_messages.update({
            'modify': 'You can not modify line from an invoice ' \
                    'that is opened, paid!',
            'create': 'You can not add a line to an invoice ' \
                    'that is open, paid or canceled!',
            'account_different_company': 'You can not create invoice line\n' \
                    'with account with a different invoice company!',
            'same_account_on_invoice': 'You can not use the same account\n' \
                    'as on the invoice!',
            })

    def init(self, module_name):
        super(InvoiceLine, self).init(module_name)
        cursor = Transaction().cursor
        table = TableHandler(cursor, self, module_name)

        # Migration from 1.0 invoice is no more required
        table.not_null_action('invoice', action='remove')

    def default_invoice_type(self):
        return Transaction().context.get('invoice_type', 'out_invoice')

    def default_currency(self):
        company_obj = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = company_obj.browse(Transaction().context['company'])
            return company.currency.id

    def default_currency_digits(self):
        company_obj = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = company_obj.browse(Transaction().context['company'])
            return company.currency.digits
        return 2

    def default_unit_digits(self):
        return 2

    def default_company(self):
        return Transaction().context.get('company')

    def default_type(self):
        return 'line'

    def on_change_with_party_lang(self, vals):
        party_obj = Pool().get('party.party')
        if vals.get('party'):
            party = party_obj.browse(vals['party'])
            if party.lang:
                return party.lang.code
        return CONFIG['language']

    def get_party_language(self, ids, name):
        '''
        Return the language code of the party of each line

        :param ids: the ids of the account.invoice.line
        :param name: the field name
        :return: a dictionary with account.invoice.line id as key and
            language code as value
        '''
        res = {}
        for line in self.browse(ids):
            if line.party and line.party.lang:
                res[line.id] = line.party.lang.code
            else:
                res[line.id] = CONFIG['language']
        return res

    def on_change_with_amount(self, vals):
        currency_obj = Pool().get('currency.currency')
        if vals.get('type') == 'line':
            currency = (vals.get('_parent_invoice.currency')
                or vals.get('currency'))
            if isinstance(currency, (int, long)) and currency:
                currency = currency_obj.browse(currency)
            amount = Decimal(str(vals.get('quantity') or '0.0')) * \
                    (vals.get('unit_price') or Decimal('0.0'))
            if currency:
                return currency_obj.round(currency, amount)
            return amount
        return Decimal('0.0')

    def on_change_with_unit_digits(self, vals):
        uom_obj = Pool().get('product.uom')
        if vals.get('unit'):
            uom = uom_obj.browse(vals['unit'])
            return uom.digits
        return 2

    def get_unit_digits(self, ids, name):
        res = {}
        for line in self.browse(ids):
            if line.unit:
                res[line.id] = line.unit.digits
            else:
                res[line.id] = 2
        return res

    def on_change_with_currency_digits(self, vals):
        currency_obj = Pool().get('currency.currency')
        if vals.get('currency'):
            currency = currency_obj.browse(vals['currency'])
            return currency.digits
        return 2

    def get_currency_digits(self, ids, name):
        res = {}
        for line in self.browse(ids):
            res[line.id] = line.currency and line.currency.digits or 2
        return res

    def get_amount(self, ids, name):
        currency_obj = Pool().get('currency.currency')
        res = {}
        for line in self.browse(ids):
            if line.type == 'line':
                currency = line.invoice and line.invoice.currency \
                        or line.currency
                res[line.id] = currency_obj.round(currency,
                        Decimal(str(line.quantity)) * line.unit_price)
            elif line.type == 'subtotal':
                res[line.id] = _ZERO
                for line2 in line.invoice.lines:
                    if line2.type == 'line':
                        res[line.id] += currency_obj.round(
                            line2.invoice.currency,
                            Decimal(str(line2.quantity)) * line2.unit_price)
                    elif line2.type == 'subtotal':
                        if line.id == line2.id:
                            break
                        res[line.id] = _ZERO
            else:
                res[line.id] = _ZERO
        return res

    def get_invoice_taxes(self, ids, name):
        tax_obj = Pool().get('account.tax')
        invoice_obj = Pool().get('account.invoice')

        res = {}
        for line in self.browse(ids):
            if not line.invoice:
                res[line.id] = None
                continue
            context = invoice_obj.get_tax_context(line.invoice)
            tax_ids = [x.id for x in line.taxes]
            taxes_keys = []
            with Transaction().set_context(**context):
                taxes = tax_obj.compute(tax_ids, line.unit_price,
                        line.quantity)
            for tax in taxes:
                key, _ = invoice_obj._compute_tax(tax, line.invoice.type)
                taxes_keys.append(key)
            res[line.id] = []
            for tax in line.invoice.taxes:
                if tax.manual:
                    continue
                key = (tax.base_code.id, tax.base_sign,
                        tax.tax_code.id, tax.tax_sign,
                        tax.account.id, tax.tax.id)
                if key in taxes_keys:
                    res[line.id].append(tax.id)
        return res

    def _get_tax_rule_pattern(self, party, vals):
        '''
        Get tax rule pattern

        :param party: the BrowseRecord of the party
        :param vals: a dictionary with value from on_change
        :return: a dictionary to use as pattern for tax rule
        '''
        res = {}
        return res

    def on_change_product(self, vals):
        pool = Pool()
        product_obj = pool.get('product.product')
        party_obj = pool.get('party.party')
        company_obj = pool.get('company.company')
        currency_obj = pool.get('currency.currency')
        tax_rule_obj = pool.get('account.tax.rule')
        invoice_obj = pool.get('account.invoice')
        date_obj = pool.get('ir.date')

        if not vals.get('product'):
            return {}
        res = {}

        context = {}
        party = None
        if vals.get('_parent_invoice.party') or vals.get('party'):
            party = party_obj.browse(vals.get('_parent_invoice.party')
                    or vals.get('party'))
            if party.lang:
                context['language'] = party.lang.code

        product = product_obj.browse(vals['product'])

        company = None
        if Transaction().context.get('company'):
            company = company_obj.browse(Transaction().context['company'])
        currency = None
        currency_date = date_obj.today()
        if '_parent_invoice.currency_date' in vals:
            if vals['_parent_invoice.currency_date']:
                currency_date = vals['_parent_invoice.currency_date']
        elif vals.get('invoice'):
            invoice = invoice_obj.browse(vals['invoice'])
            currency_date = invoice.currency_date
        if vals.get('_parent_invoice.currency') or vals.get('currency'):
            #TODO check if today date is correct
            currency = currency_obj.browse(
                    vals.get('_parent_invoice.currency') or
                    vals.get('currency'))

        if (vals.get('_parent_invoice.type') or vals.get('invoice_type')) \
                in ('in_invoice', 'in_credit_note'):
            if company and currency:
                with Transaction().set_context(date=currency_date):
                    res['unit_price'] = currency_obj.compute(
                            company.currency.id, product.cost_price,
                            currency.id, round=False)
            else:
                res['unit_price'] = product.cost_price
            try:
                res['account'] = product.account_expense_used.id
                res['account.rec_name'] = product.account_expense_used.rec_name
            except Exception:
                pass
            res['taxes'] = []
            pattern = self._get_tax_rule_pattern(party, vals)
            for tax in product.supplier_taxes_used:
                if party and party.supplier_tax_rule:
                    tax_ids = tax_rule_obj.apply(party.supplier_tax_rule, tax,
                            pattern)
                    if tax_ids:
                        res['taxes'].extend(tax_ids)
                    continue
                res['taxes'].append(tax.id)
            if party and party.supplier_tax_rule:
                tax_ids = tax_rule_obj.apply(party.supplier_tax_rule, None,
                        pattern)
                if tax_ids:
                    res['taxes'].extend(tax_ids)
        else:
            if company and currency:
                with Transaction().set_context(date=currency_date):
                    res['unit_price'] = currency_obj.compute(
                            company.currency.id, product.list_price,
                            currency.id, round=False)
            else:
                res['unit_price'] = product.list_price
            try:
                res['account'] = product.account_revenue_used.id
                res['account.rec_name'] = product.account_revenue_used.rec_name
            except Exception:
                pass
            res['taxes'] = []
            pattern = self._get_tax_rule_pattern(party, vals)
            for tax in product.customer_taxes_used:
                if party and party.customer_tax_rule:
                    tax_ids = tax_rule_obj.apply(party.customer_tax_rule, tax,
                            pattern)
                    if tax_ids:
                        res['taxes'].extend(tax_ids)
                    continue
                res['taxes'].append(tax.id)
            if party and party.customer_tax_rule:
                tax_ids = tax_rule_obj.apply(party.customer_tax_rule, None,
                        pattern)
                if tax_ids:
                    res['taxes'].extend(tax_ids)

        if not vals.get('description'):
            with Transaction().set_context(**context):
                res['description'] = product_obj.browse(product.id).rec_name

        category = product.default_uom.category
        if not vals.get('unit') \
                or vals.get('unit') not in [x.id for x in category.uoms]:
            res['unit'] = product.default_uom.id
            res['unit.rec_name'] = product.default_uom.rec_name
            res['unit_digits'] = product.default_uom.digits

        vals = vals.copy()
        vals['unit_price'] = res['unit_price']
        vals['type'] = 'line'
        res['amount'] = self.on_change_with_amount(vals)
        return res

    def on_change_with_product_uom_category(self, values):
        pool = Pool()
        product_obj = pool.get('product.product')
        if values.get('product'):
            product = product_obj.browse(values['product'])
            return product.default_uom_category.id

    def get_product_uom_category(self, ids, name):
        categories = {}
        for line in self.browse(ids):
            if line.product:
                categories[line.id] = line.product.default_uom_category.id
            else:
                categories[line.id] = None
        return categories

    def on_change_account(self, values):
        account_obj = Pool().get('account.account')
        if values.get('product'):
            return {}
        taxes = []
        result = {
            'taxes': taxes,
        }
        if values.get('account'):
            account = account_obj.browse(values['account'])
            taxes.extend(tax.id for tax in account.taxes)
        return result

    def check_modify(self, ids):
        '''
        Check if the lines can be modified
        '''
        for line in self.browse(ids):
            if line.invoice and \
                    line.invoice.state in ('open', 'paid'):
                self.raise_user_error('modify')
        return

    def delete(self, ids):
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.check_modify(ids)
        return super(InvoiceLine, self).delete(ids)

    def write(self, ids, vals):
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.check_modify(ids)
        return super(InvoiceLine, self).write(ids, vals)

    def create(self, vals):
        invoice_obj = Pool().get('account.invoice')
        if vals.get('invoice'):
            invoice = invoice_obj.browse(vals['invoice'])
            if invoice.state in ('open', 'paid', 'cancel'):
                self.raise_user_error('create')
        return super(InvoiceLine, self).create(vals)

    def check_account(self, ids):
        for line in self.browse(ids):
            if line.type == 'line':
                if line.invoice:
                    if line.account.company.id != line.invoice.company.id:
                        return False
                elif line.company:
                    if line.account.company.id != line.company.id:
                        return False
        return True

    def check_account2(self, ids):
        for line in self.browse(ids):
            if line.type == 'line':
                if line.invoice \
                        and line.account.id == line.invoice.account.id:
                    return False
        return True

    def _compute_taxes(self, line):
        pool = Pool()
        tax_obj = pool.get('account.tax')
        currency_obj = pool.get('currency.currency')
        invoice_obj = pool.get('account.invoice')

        context = invoice_obj.get_tax_context(line.invoice)
        res = []
        if line.type != 'line':
            return res
        tax_ids = [x.id for x in line.taxes]
        with Transaction().set_context(**context):
            taxes = tax_obj.compute(tax_ids, line.unit_price, line.quantity)
        for tax in taxes:
            if line.invoice.type in ('out_invoice', 'in_invoice'):
                base_code_id = tax['tax'].invoice_base_code.id
                amount = tax['base'] * tax['tax'].invoice_base_sign
            else:
                base_code_id = tax['tax'].credit_note_base_code.id
                amount = tax['base'] * tax['tax'].credit_note_base_sign
            if base_code_id:
                with Transaction().set_context(
                        date=line.invoice.currency_date):
                    amount = currency_obj.compute(line.invoice.currency.id,
                            amount, line.invoice.company.currency.id)
                res.append({
                    'code': base_code_id,
                    'amount': amount,
                    'tax': tax['tax'].id
                })
        return res

    def get_move_line(self, line):
        '''
        Return a list of move lines values for invoice line
        '''
        currency_obj = Pool().get('currency.currency')
        res = {}
        if line.type != 'line':
            return []
        res['name'] = line.description
        if line.invoice.currency.id != line.invoice.company.currency.id:
            with Transaction().set_context(date=line.invoice.currency_date):
                amount = currency_obj.compute(line.invoice.currency.id,
                        line.amount, line.invoice.company.currency.id)
            res['amount_second_currency'] = line.amount
            res['second_currency'] = line.invoice.currency.id
        else:
            amount = line.amount
            res['amount_second_currency'] = Decimal('0.0')
            res['second_currency'] = None
        if line.invoice.type in ('in_invoice', 'out_credit_note'):
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
        res['account'] = line.account.id
        res['party'] = line.invoice.party.id
        computed_taxes = self._compute_taxes(line)
        for tax in computed_taxes:
            res.setdefault('tax_lines', [])
            res['tax_lines'].append(('create', tax))
        return [res]

    def _credit(self, line):
        '''
        Return values to credit line.
        '''
        res = {}

        for field in ('sequence', 'type', 'quantity', 'unit_price',
                'description'):
            res[field] = line[field]

        for field in ('unit', 'product', 'account'):
            res[field] = line[field].id

        res['taxes'] = []
        for tax in line.taxes:
            res['taxes'].append(('add', tax.id))
        return res

InvoiceLine()


class InvoiceLineTax(ModelSQL):
    'Invoice Line - Tax'
    _name = 'account.invoice.line-account.tax'
    _table = 'account_invoice_line_account_tax'
    _description = __doc__
    line = fields.Many2One('account.invoice.line', 'Invoice Line',
            ondelete='CASCADE', select=True, required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
            required=True)

InvoiceLineTax()


class InvoiceTax(ModelSQL, ModelView):
    'Invoice Tax'
    _name = 'account.invoice.tax'
    _rec_name = 'description'
    _description = __doc__

    invoice = fields.Many2One('account.invoice', 'Invoice', ondelete='CASCADE',
            select=True)
    description = fields.Char('Description', size=None, required=True)
    sequence = fields.Integer('Sequence', required=True)
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
        digits=(16, Eval('_parent_invoice', {}).get('currency_digits', 2)))
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
    tax = fields.Many2One('account.tax', 'Tax')

    def __init__(self):
        super(InvoiceTax, self).__init__()
        self._constraints += [
            ('check_company', 'You can not create invoice tax \n' \
                    'with account or code from a different invoice company!',
                    ['account', 'base_code', 'tax_code']),
        ]
        self._order.insert(0, ('sequence', 'ASC'))
        self._error_messages.update({
            'modify': 'You can not modify tax from an invoice ' \
                    'that is opened, paid!',
            'create': 'You can not add a line to an invoice ' \
                    'that is open, paid or canceled!',
            })

    def default_base(self):
        return Decimal('0.0')

    def default_amount(self):
        return Decimal('0.0')

    def default_manual(self):
        return True

    def default_base_sign(self):
        return Decimal('1')

    def default_tax_sign(self):
        return Decimal('1')

    def check_modify(self, ids):
        '''
        Check if the taxes can be modified
        '''
        for tax in self.browse(ids):
            if tax.invoice.state in ('open', 'paid'):
                self.raise_user_error('modify')
        return

    def get_sequence_number(self, ids, name):
        res = {}
        for tax in self.browse(ids):
            res[tax.id] = 0
            i = 1
            for tax2 in tax.invoice.taxes:
                if tax2.id == tax.id:
                    res[tax.id] = i
                    break
                i += 1
        return res

    def delete(self, ids):
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.check_modify(ids)
        return super(InvoiceTax, self).delete(ids)

    def write(self, ids, vals):
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.check_modify(ids)
        return super(InvoiceTax, self).write(ids, vals)

    def create(self, vals):
        invoice_obj = Pool().get('account.invoice')
        if vals.get('invoice'):
            invoice = invoice_obj.browse(vals['invoice'])
            if invoice.state in ('open', 'paid', 'cancel'):
                self.raise_user_error('create')
        return super(InvoiceTax, self).create(vals)

    def check_company(self, ids):
        for tax in self.browse(ids):
            company = tax.invoice.company
            if tax.account.company.id != company.id:
                return False
            if tax.base_code:
                if tax.base_code.company.id != company.id:
                    return False
            if tax.tax_code:
                if tax.tax_code.company.id != company.id:
                    return False
        return True

    def get_move_line(self, tax):
        '''
        Return a list of move lines values for invoice tax
        '''
        currency_obj = Pool().get('currency.currency')
        res = {}
        if not tax.amount:
            return []
        res['name'] = tax.description
        if tax.invoice.currency.id != tax.invoice.company.currency.id:
            with Transaction().set_context(date=tax.invoice.currency_date):
                amount = currency_obj.compute(tax.invoice.currency.id,
                        tax.amount, tax.invoice.company.currency.id)
            res['amount_second_currency'] = tax.amount
            res['second_currency'] = tax.invoice.currency.id
        else:
            amount = tax.amount
            res['amount_second_currency'] = Decimal('0.0')
            res['second_currency'] = None
        if tax.invoice.type in ('in_invoice', 'out_credit_note'):
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
        res['account'] = tax.account.id
        res['party'] = tax.invoice.party.id
        if tax.tax_code:
            res['tax_lines'] = [('create', {
                'code': tax.tax_code.id,
                'amount': amount * tax.tax_sign,
                'tax': tax.tax and tax.tax.id or None
            })]
        return [res]

    def _credit(self, tax):
        '''
        Return values to credit tax.
        '''
        res = {}

        for field in ('description', 'sequence', 'base', 'amount',
                'manual', 'base_sign', 'tax_sign'):
            res[field] = tax[field]

        for field in ('account', 'base_code', 'tax_code', 'tax'):
            res[field] = tax[field].id
        return res

InvoiceTax()


class PrintInvoiceWarning(ModelView):
    'Print Invoice Report Warning'
    _name = 'account.invoice.print.warning'
    _description = __doc__

PrintInvoiceWarning()


class PrintInvoice(Wizard):
    'Print Invoice Report'
    _name = 'account.invoice.print'

    start = StateTransition()
    warning = StateView('account.invoice.print.warning',
        'account_invoice.print_warning_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateAction('account_invoice.report_invoice')

    def transition_start(self, session):
        if len(Transaction().context['active_ids']) > 1:
            return 'warning'
        return 'print_'

    def do_print_(self, session, action):
        data = {}
        data['id'] = Transaction().context['active_ids'].pop()
        data['ids'] = [data['id']]
        return action, data

    def transition_print_(self, session):
        if Transaction().context['active_ids']:
            return 'print_'
        return 'end'

PrintInvoice()


class InvoiceReport(Report):
    _name = 'account.invoice'

    def __init__(self):
        super(InvoiceReport, self).__init__()
        self._rpc['execute'] = True

    def execute(self, ids, data):
        invoice_obj = Pool().get('account.invoice')

        res = super(InvoiceReport, self).execute(ids, data)
        if len(ids) > 1:
            res = (res[0], res[1], True, res[3])
        else:
            invoice = invoice_obj.browse(ids[0])
            if invoice.number:
                res = (res[0], res[1], res[2], res[3] + ' - ' + invoice.number)
        return res

    def _get_objects(self, ids, model, data):
        invoice_obj = Pool().get('account.invoice')

        with Transaction().set_context(language=False):
            return invoice_obj.browse([ids[0]])

    def parse(self, report, objects, data, localcontext):
        user_obj = Pool().get('res.user')
        invoice_obj = Pool().get('account.invoice')

        invoice = objects[0]

        if invoice.invoice_report_cache:
            return (invoice.invoice_report_format,
                invoice.invoice_report_cache)

        user = user_obj.browse(Transaction().user)
        localcontext['company'] = user.company
        res = super(InvoiceReport, self).parse(report, objects, data,
                localcontext)
        # If the invoice is open or paid and the report not saved in
        # invoice_report_cache there was an error somewhere. So we save it now
        # in invoice_report_cache
        if invoice.state in ('open', 'paid'):
            invoice_obj.write(invoice.id, {
                'invoice_report_format': res[0],
                'invoice_report_cache': res[1],
                })
        return res

InvoiceReport()


class PayInvoiceStart(ModelView):
    'Pay Invoice'
    _name = 'account.invoice.pay.start'
    _description = __doc__
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'], required=True)
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    currency_digits = fields.Integer('Currency Digits', readonly=True,
            on_change_with=['currency'])
    description = fields.Char('Description', size=None, required=True)
    journal = fields.Many2One('account.journal', 'Journal', required=True,
            domain=[('type', '=', 'cash')])
    date = fields.Date('Date', required=True)

    def default_date(self):
        date_obj = Pool().get('ir.date')
        return date_obj.today()

    def default_currency_digits(self):
        return 2

    def on_change_with_currency_digits(self, vals):
        currency_obj = Pool().get('currency.currency')
        if vals.get('currency'):
            currency = currency_obj.browse(vals['currency'])
            return currency.digits
        return 2

PayInvoiceStart()


class PayInvoiceAsk(ModelView):
    'Pay Invoice'
    _name = 'account.invoice.pay.ask'
    _description = __doc__
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

    def default_type(self):
        return 'partial'

    def on_change_lines(self, vals):
        pool = Pool()
        currency_obj = pool.get('currency.currency')
        line_obj = pool.get('account.move.line')
        invoice_obj = pool.get('account.invoice')

        res = {}
        invoice = invoice_obj.browse(vals['invoice'])
        with Transaction().set_context(date=invoice.currency_date):
            amount = currency_obj.compute(vals['currency'], vals['amount'],
                    vals['currency_writeoff'])

        res['amount_writeoff'] = Decimal('0.0')
        for line in line_obj.browse(vals['lines']):
            res['amount_writeoff'] += line.debit - line.credit
        if invoice.type in ('in_invoice', 'out_credit_note'):
            res['amount_writeoff'] = - res['amount_writeoff'] - amount
        else:
            res['amount_writeoff'] = res['amount_writeoff'] - amount
        return res

PayInvoiceAsk()


class PayInvoice(Wizard):
    'Pay Invoice'
    _name = 'account.invoice.pay'

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

    def __init__(self):
        super(PayInvoice, self).__init__()
        self._error_messages.update({
            'amount_greater_amount_to_pay': 'You can not create a partial ' \
                    'payment with an amount greater then the amount to pay!',
            })

    def default_start(self, session, fields):
        invoice_obj = Pool().get('account.invoice')
        default = {}
        invoice = invoice_obj.browse(Transaction().context['active_id'])
        default['currency'] = invoice.currency.id
        default['currency_digits'] = invoice.currency.digits
        default['amount'] = (invoice.amount_to_pay_today
            or invoice.amount_to_pay)
        default['description'] = invoice.number
        return default

    def transition_choice(self, session):
        invoice_obj = Pool().get('account.invoice')
        currency_obj = Pool().get('currency.currency')

        invoice = invoice_obj.browse(Transaction().context['active_id'])

        with Transaction().set_context(date=session.start.date):
            amount = currency_obj.compute(session.start.currency.id,
                session.start.amount, invoice.company.currency.id)
        _, remainder = invoice_obj.get_reconcile_lines_for_amount(invoice,
            amount)
        if remainder == Decimal('0.0') and amount <= invoice.amount_to_pay:
            return 'pay'
        return 'ask'

    def default_ask(self, session, fields):
        pool = Pool()
        invoice_obj = pool.get('account.invoice')
        currency_obj = pool.get('currency.currency')
        line_obj = pool.get('account.move.line')

        default = {}
        invoice = invoice_obj.browse(Transaction().context['active_id'])
        default['lines_to_pay'] = [x.id for x in invoice.lines_to_pay
                if not x.reconciliation]

        default['amount'] = session.start.amount
        default['currency'] = session.start.currency.id
        default['currency_digits'] = session.start.currency_digits
        default['company'] = invoice.company.id

        with Transaction().set_context(date=session.start.date):
            amount = currency_obj.compute(session.start.currency.id,
                session.start.amount, invoice.company.currency.id)

        if currency_obj.is_zero(invoice.company.currency, amount):
            default['lines'] = [x.id for x in invoice.lines_to_pay]
        else:
            default['lines'], _ = \
                invoice_obj.get_reconcile_lines_for_amount(invoice, amount)
        for line_id in default['lines'][:]:
            if line_id not in default['lines_to_pay']:
                default['lines'].remove(line_id)

        default['amount_writeoff'] = Decimal('0.0')
        for line in line_obj.browse(default['lines']):
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

        if amount > invoice.amount_to_pay \
                or currency_obj.is_zero(invoice.company.currency, amount):
            default['type'] = 'writeoff'
        return default

    def transition_pay(self, session):
        pool = Pool()
        invoice_obj = pool.get('account.invoice')
        currency_obj = pool.get('currency.currency')
        move_line_obj = pool.get('account.move.line')

        invoice = invoice_obj.browse(Transaction().context['active_id'])

        with Transaction().set_context(date=session.start.date):
            amount = currency_obj.compute(session.start.currency.id,
                session.start.amount, invoice.company.currency.id)

        reconcile_lines, remainder = \
            invoice_obj.get_reconcile_lines_for_amount(invoice, amount)

        amount_second_currency = None
        second_currency = None
        if session.start.currency.id != invoice.company.currency.id:
            amount_second_currency = session.start.amount
            second_currency = session.start.currency

        if amount > invoice.amount_to_pay and \
                session.ask.type != 'writeoff':
            self.raise_user_error('amount_greater_amount_to_pay')

        line_id = None
        if not currency_obj.is_zero(invoice.company.currency, amount):
            line_id = invoice_obj.pay_invoice(invoice.id, amount,
                session.start.journal.id, session.start.date,
                session.start.description, amount_second_currency,
                second_currency)

        if remainder != Decimal('0.0'):
            if session.ask.type == 'writeoff':
                line_ids = [x.id for x in session.ask.lines] + \
                    [x.id for x in invoice.payment_lines
                        if not x.reconciliation]
                if line_ids:
                    move_line_obj.reconcile(line_ids,
                        journal_id=session.ask.journal_writeoff,
                        date=session.start.date,
                        account_id=session.ask.account_writeoff)
        else:
            if line_id:
                reconcile_lines += [line_id]
            if reconcile_lines:
                move_line_obj.reconcile(reconcile_lines)
        return 'end'

PayInvoice()


class CreditInvoiceStart(ModelView):
    'Credit Invoice Init'
    _name = 'account.invoice.credit.start'
    _description = __doc__
    with_refund = fields.Boolean('With Refund', help='If true, ' \
            'the current invoice(s) will be paid.')

CreditInvoiceStart()


class CreditInvoice(Wizard):
    'Credit Invoice'
    _name = 'account.invoice.credit'

    start = StateView('account.invoice.credit.start',
        'account_invoice.credit_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Credit', 'credit', 'tryton-ok', default=True),
            ])
    credit = StateAction('account_invoice.act_invoice_form')

    def __init__(self):
        super(CreditInvoice, self).__init__()
        self._error_messages.update({
            'refund_non_open': 'You can not credit with refund ' \
                    'an invoice that is not opened!',
            'refund_with_payement': 'You can not credit with refund ' \
                    'an invoice with payments!',
            })

    def default_start(self, session, fields):
        invoice_obj = Pool().get('account.invoice')
        default = {
            'with_refund': True,
        }
        for invoice in invoice_obj.browse(Transaction().context['active_ids']):
            if invoice.state != 'open' or invoice.payment_lines:
                default['with_refund'] = False
                break
        return default

    def do_credit(self, session, action):
        pool = Pool()
        invoice_obj = pool.get('account.invoice')

        refund = session.start.with_refund
        invoice_ids = Transaction().context['active_ids']

        if refund:
            for invoice in invoice_obj.browse(invoice_ids):
                if invoice.state != 'open':
                    self.raise_user_error('refund_non_open')
                if invoice.payment_lines:
                    self.raise_user_error('refund_with_payement')

        invoice_ids = invoice_obj.credit(invoice_ids, refund=refund)

        data = {'res_id': invoice_ids}
        if len(invoice_ids) == 1:
            action['views'].reverse()
        return action, data

CreditInvoice()
