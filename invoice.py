#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"Invoice"

from trytond.osv import fields, OSV
import datetime
import mx.DateTime
from decimal import Decimal
from trytond.netsvc import LocalService
from trytond.report import Report
from trytond.wizard import Wizard, WizardOSV
from trytond.pooler import get_pool_report
import base64

_STATES = {
    'readonly': "state != 'draft'",
}

_TYPE2JOURNAL = {
    'out_invoice': 'revenue',
    'in_invoice': 'expense',
    'out_refund': 'revenue',
    'in_refund': 'expense',
}


class PaymentTerm(OSV):
    'Payment Term'
    _name = 'account.invoice.payment_term'
    _description = __doc__
    name = fields.Char('Payment Term', size=None, required=True, translate=True)
    active = fields.Boolean('Active')
    description = fields.Text('Description', translate=True)
    lines = fields.One2Many('account.invoice.payment_term.line', 'payment',
            'Lines')

    def __init__(self):
        super(PaymentTerm, self).__init__()
        self._order.insert(0, ('name', 'ASC'))
        self._error_messages.update({
            'invalid_line': 'Invalid payment term line!',
            'missing_remainder': 'Payment term missing a remainder line!',
            })

    def default_active(self, cursor, user, context=None):
        return True

    def compute(self, cursor, user, amount, currency, payment_term, date=None,
            context=None):
        '''
        Return list with (date, amount) for each payment term lines
        '''
        #TODO implement business_days
        # http://pypi.python.org/pypi/BusinessHours/
        type_obj = self.pool.get('account.invoice.payment_term.line.type')
        delay_obj = self.pool.get(
                'account.invoice.payment_term.line.delay')
        currency_obj = self.pool.get('currency.currency')
        res = []
        if date is None:
            date = datetime.date.today()
        remainder = amount
        for line in payment_term.lines:
            value = type_obj.get_value(cursor, user, line, remainder, currency,
                    context)
            value_date = delay_obj.get_date(cursor, user, line, date, context)
            if not value or not value_date:
                if (not remainder) and line.amount:
                    self.raise_user_error(cursor, 'invalid_line',
                            context=context)
                else:
                    continue
            res.append((value_date, value))
            remainder -= value
        if not currency_obj.is_zero(cursor, user, currency, remainder):
            self.raise_user_error(cursor, 'missing_remainder',
                    context=context)
        return res

PaymentTerm()


class PaymentTermLineType(OSV):
    'Payment Term Line Type'
    _name = 'account.invoice.payment_term.line.type'
    _description = __doc__
    name = fields.Char('Name', size=None, translate=True, required=True)
    code = fields.Char('Code', size=None, required=True)

    def __init__(self):
        super(PaymentTermLineType, self).__init__()
        self._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'Code must be unique!'),
        ]
        self._order.insert(0, ('name', 'ASC'))

    def get_value(self, cursor, user, line, amount, currency, context=None):
        currency_obj = self.pool.get('currency.currency')
        if line.type == 'fixed':
            return currency_obj.compute(cursor, user, line.currency,
                    line.amount, currency, context=context)
        elif line.type == 'percent':
            return currency.round(cursor, user, currency, amount * line.percent)
        elif line.type == 'remainder':
            return currency.round(cursor, user, currency, amount)
        return None

PaymentTermLineType()


class PaymentTermLineDelay(OSV):
    'Payment Term Line Delay'
    _name = 'account.invoice.payment_term.line.delay'
    _description = __doc__
    name = fields.Char('Name', size=None, translate=True, required=True)
    code = fields.Char('Code', size=None, required=True)

    def __init__(self):
        super(PaymentTermLineDelay, self).__init__()
        self._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'Code must be unique!'),
        ]
        self._order.insert(0, ('name', 'ASC'))

    def get_date(self, cursor, user, line, date, context=None):
        value = None
        if line.delay == 'net_days':
            value = mx.DateTime.strptime(str(date), '%Y-%m-%d') + \
                    mx.DateTime.RelativeDateTime(days=line.days)
        elif line.delay == 'end_month':
            value = mx.DateTime.strptime(str(date), '%Y-%m-%d') + \
                    mx.DateTime.RelativeDateTime(days=line.days) + \
                    mx.DateTime.RelativeDateTime(day=-1)
        if value:
            return datetime.date(value.year, value.month, value.day)
        return None

PaymentTermLineDelay()


class PaymentTermLine(OSV):
    'Payment Term Line'
    _name = 'account.invoice.payment_term.line'
    _description = __doc__
    sequence = fields.Integer('Sequence',
            help='Use to order lines in ascending order')
    payment = fields.Many2One('account.invoice.payment_term', 'Payment Term',
            required=True, ondelete="CASCADE")
    type = fields.Selection('get_type', 'Type', required=True,
            on_change=['type'])
    percent = fields.Numeric('Percent', digits=(16, 8),
            states={
                'invisible': "type != 'percent'",
                'required': "type == 'percent'",
            })
    amount = fields.Numeric('Amount', digits="(16, currency_digits)",
            states={
                'invisible': "type != 'fixed'",
                'required': "type == 'fixed'",
            })
    currency = fields.Many2One('currency.currency', 'Currency',
            states={
                'invisible': "type != 'fixed'",
                'required': "type == 'fixed'",
            })
    currency_digits = fields.Function('get_currency_digits', type='integer',
            string='Currency Digits', on_change_with=['currency'])
    days = fields.Integer('Number of Days')
    delay = fields.Selection('get_delay', 'Condition', required=True)

    def __init__(self):
        super(PaymentTermLine, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))

    def default_type(self, cursor, user, context=None):
        return 'remainder'

    def default_delay(self, cursor, user, context=None):
        return 'net_days'

    def get_type(self, cursor, user, context=None):
        type_obj = self.pool.get('account.invoice.payment_term.line.type')
        type_ids = type_obj.search(cursor, user, [], context=context)
        types = type_obj.browse(cursor, user, type_ids, context=context)
        return [(x.code, x.name) for x in types]

    def get_delay(self, cursor, user, context=None):
        delay_obj = self.pool.get('account.invoice.payment_term.line.delay')
        delay_ids = delay_obj.search(cursor, user, [], context=context)
        delays = delay_obj.browse(cursor, user, delay_ids,
                context=context)
        return [(x.code, x.name) for x in delays]

    def on_change_type(self, cursor, user, ids, vals, context=None):
        if not 'type' in vals:
            return {}
        res = {}
        if vals['type'] != 'fixed':
            res['amount'] = Decimal('0.0')
            res['currency'] =  False
        if vals['type'] != 'percent':
            res['percent'] =  Decimal('0.0')
        return res

    def on_change_with_currency_digits(self, cursor, user, ids, vals,
            context=None):
        currency_obj = self.pool.get('currency.currency')
        if vals.get('currency'):
            currency = currency_obj.browse(cursor, user, vals['currency'],
                    context=context)
            return currency.digits
        return 2

    def get_currency_digits(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for line in self.browse(cursor, user, ids, context=context):
            if line.currency:
                res[line.id] = line.currency.digits
            else:
                res[line.id] = 2
        return res

PaymentTermLine()


class Invoice(OSV):
    'Invoice'
    _name = 'account.invoice'
    _description = __doc__
    company = fields.Many2One('company.company', 'Company', required=True,
            states=_STATES)
    type = fields.Selection([
        ('out_invoice', 'Invoice'),
        ('in_invoice', 'Supplier Invoice'),
        ('out_refund', 'Refund'),
        ('in_refund', 'Supplier Refund'),
        ], 'Type', select=1, on_change=['type'], required=True, states={
            'readonly': "state != 'draft' or context.get('type', False)",
        })
    type_name = fields.Function('get_type_name', type='char', string='Type')
    number = fields.Char('Number', size=None, readonly=True, select=1)
    reference = fields.Char('Reference', size=None)
    description = fields.Char('Description', size=None, states=_STATES)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('proforma', 'Pro forma'),
        ('open', 'Open'),
        ('paid', 'Paid'),
        ('cancel', 'Canceled'),
        ], 'State', readonly=True)
    invoice_date = fields.Date('Invoice Date', required=True,
        states=_STATES)
    party = fields.Many2One('relationship.party', 'Party', change_default=True,
        required=True, states=_STATES, on_change=['party', 'payment_term',
            'type', 'company'])
    contact_address = fields.Many2One('relationship.address', 'Contact Address',
        required=True, states=_STATES, domain="[('party', '=', party)]")
    invoice_address = fields.Many2One('relationship.address', 'Invoice Address',
        required=True, states=_STATES, domain="[('party', '=', party)]")
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states={
            'readonly': "state != 'draft' or (bool(lines) and bool(currency))",
        })
    currency_digits = fields.Function('get_currency_digits', type='integer',
            string='Currency Digits', on_change_with=['currency'])
    journal = fields.Many2One('account.journal', 'Journal', required=True,
        states=_STATES, domain=[('centralised', '=', False)])
    move = fields.Many2One('account.move', 'Move', readonly=True)
    account = fields.Many2One('account.account', 'Account', required=True,
        states=_STATES,
        domain="[('company', '=', company), ('kind', '!=', 'view')]")
    payment_term = fields.Many2One('account.invoice.payment_term',
        'Payment Term', required=True, states=_STATES)
    lines = fields.One2Many('account.invoice.line', 'invoice', 'Lines',
        states=_STATES, on_change=['lines', 'taxes', 'currency', 'party', 'type'])
    taxes = fields.One2Many('account.invoice.tax', 'invoice', 'Tax Lines',
        states=_STATES, on_change=['lines', 'taxes', 'currency', 'party', 'type'])
    comment = fields.Text('Comment')
    untaxed_amount = fields.Function('get_untaxed_amount', type='numeric',
            digits="(16, currency_digits)", string='Untaxed')
    tax_amount = fields.Function('get_tax_amount', type='numeric',
            digits="(16, currency_digits)", string='Tax')
    total_amount = fields.Function('get_total_amount', type='numeric',
            digits="(16, currency_digits)", string='Total')
    reconciled = fields.Function('get_reconciled', type='boolean',
            string='Reconciled')
    lines_to_pay = fields.Function('get_lines_to_pay', type='one2many',
            relation='account.move.line', string='Lines to Pay')
    payment_lines = fields.Many2Many('account.move.line',
            'invoice_payment_lines_rel', 'invoice', 'line', readonly=True,
            string='Payment Lines')
    amount_to_pay_today = fields.Function('get_amount_to_pay',
            type='numeric', digits="(16, currency_digits)",
            string='Amount to Pay Today')
    amount_to_pay = fields.Function('get_amount_to_pay',
            type='numeric', digits="(16, currency_digits)",
            string='Amount to Pay')
    invoice_report = fields.Binary('Invoice Report', readonly=True)
    invoice_report_format = fields.Char('Invoice Report Format', readonly=True)

    def __init__(self):
        super(Invoice, self).__init__()
        self._rpc_allowed += [
            'button_draft',
        ]
        self._constraints += [
            ('check_account', 'account_different_company'),
            ('check_account2', 'same_account_on_line'),
        ]
        self._order.insert(0, ('number', 'ASC'))
        self._error_messages.update({
            'reset_draft': 'You can not reset to draft ' \
                    'an invoice that have move!',
            'missing_tax_line': 'Taxes defined ' \
                    'but not in invoice lines!\n' \
                    'Re-compute the invoice.',
            'diff_tax_line': 'Base taxes ' \
                    'different from invoice lines!\n' \
                    'Re-compute the invoice.',
            'missing_tax_line2': 'Taxes defined ' \
                    'on invoice lines but not on invoice!\n' \
                    'Re-compute the invoice.',
            'no_invoice_sequence': 'There is no invoice sequence ' \
                    'on the period/fiscal year!',
            'modify_invoice': 'You can not modify invoice that is ' \
                    'open, paid or canceled!',
            'same_debit_account': 'Debit account on journal is ' \
                    'the same than the invoice account!',
            'missing_debit_account': 'The debit account on journal is ' \
                    'missing!',
            'same_credit_account': 'Credit account on journal is ' \
                    'the same than the invoice account!',
            'missing_credit_account': 'The credit account on journal is ' \
                    'missing!',
            'account_different_company': 'You can not create an invoice\n' \
                    'with account from a different invoice company!',
            'same_account_on_line': 'You can not use the same account\n' \
                    'than on invoice line account!',
            })

    def default_type(self, cursor, user, context=None):
        if context is None:
            context = {}
        return context.get('type', 'out_invoice')

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def default_invoice_date(self, cursor, user, context=None):
        return datetime.date.today()

    def default_currency(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        currency_obj = self.pool.get('currency.currency')
        if context is None:
            context = {}
        company = None
        if context.get('company'):
            company = company_obj.browse(cursor, user, context['company'],
                    context=context)
            return currency_obj.name_get(cursor, user, company.currency.id,
                    context=context)[0]
        return False

    def default_currency_digits(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        if context is None:
            context = {}
        company = None
        if context.get('company'):
            company = company_obj.browse(cursor, user, context['company'],
                    context=context)
            return company.currency.digits
        return 2

    def default_company(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        if context is None:
            context = {}
        if context.get('company'):
            return company_obj.name_get(cursor, user, context['company'],
                    context=context)[0]
        return False

    def default_payment_term(self, cursor, user, context=None):
        payment_term_obj = self.pool.get('account.invoice.payment_term')
        payment_term_ids = payment_term_obj.search(cursor, user,
                self.payment_term._domain, context=context)
        if len(payment_term_ids) == 1:
            return payment_term_obj.name_get(cursor, user, payment_term_ids,
                    context=context)[0]
        return False

    def on_change_type(self, cursor, user, ids, vals, context=None):
        journal_obj = self.pool.get('account.journal')
        res = {}
        journal_ids = journal_obj.search(cursor, user, [
            ('type', '=', _TYPE2JOURNAL.get(vals.get('type', 'out_invoice'),
                'revenue')),
            ], limit=1, context=context)
        if journal_ids:
            res['journal'] = journal_obj.name_get(cursor, user, journal_ids[0],
                    context=context)[0]
        return res

    def on_change_party(self, cursor, user, ids, vals, context=None):
        party_obj = self.pool.get('relationship.party')
        address_obj = self.pool.get('relationship.address')
        account_obj = self.pool.get('account.account')
        payment_term_obj = self.pool.get('account.invoice.payment_term')
        company_obj = self.pool.get('company.company')
        res = {
            'invoice_address': False,
            'contact_address': False,
            'account': False,
        }
        if vals.get('party'):
            party = party_obj.browse(cursor, user, vals['party'],
                    context=context)
            res['contact_address'] = party_obj.address_get(cursor, user,
                    party.id, type=None, context=context)
            res['invoice_address'] = party_obj.address_get(cursor, user,
                    party.id, type='invoice', context=context)
            if vals.get('type') in ('out_invoice', 'out_refund'):
                res['account'] = party.account_receivable.id
                if vals['type'] == 'out_invoice' and party.payment_term:
                    res['payment_term'] = party.payment_term.id
            elif vals.get('type') in ('in_invoice', 'in_refund'):
                res['account'] = party.account_payable.id
                if vals['type'] == 'in_invoice' and party.supplier_payment_term:
                    res['payment_term'] = party.supplier_payment_term.id

        if vals.get('company'):
            company = company_obj.browse(cursor, user, vals['company'],
                    context=context)
            if vals.get('type') == 'out_refund':
                res['payment_term'] = company.payment_term.id
            elif vals.get('type') == 'in_refund':
                res['payment_term'] = company.supplier_payment_term.id

        if res['contact_address']:
            res['contact_address'] = address_obj.name_get(cursor, user,
                    res['contact_address'], context=context)[0]
        if res['invoice_address']:
            res['invoice_address'] = address_obj.name_get(cursor, user,
                    res['invoice_address'], context=context)[0]
        if res['account']:
            res['account'] = account_obj.name_get(cursor, user,
                    res['account'], context=context)[0]
        if res.get('payment_term'):
            res['payment_term'] = payment_term_obj.name_get(cursor, user,
                    res['payment_term'], context=context)[0]
        return res

    def on_change_with_currency_digits(self, cursor, user, ids, vals,
            context=None):
        currency_obj = self.pool.get('currency.currency')
        if vals.get('currency'):
            currency = currency_obj.browse(cursor, user, vals['currency'],
                    context=context)
            return currency.digits
        return 2

    def get_currency_digits(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for invoice in self.browse(cursor, user, ids, context=context):
            res[invoice.id] = invoice.currency.digits
        return res

    def get_type_name(self, cursor, user, ids, name, arg, context=None):
        res = {}
        type2name = {}
        for type, name in self.fields_get(cursor, user, fields_names=['type'],
                context=context)['type']['selection']:
            type2name[type] = name
        for invoice in self.browse(cursor, user, ids, context=context):
            res[invoice.id] = type2name[invoice.type]
        return res

    def on_change_lines(self, cursor, user, ids, vals, context=None):
        return self._on_change_lines_taxes(cursor, user, ids, vals, context=context)

    def on_change_taxes(self, cursor, user, ids, vals, context=None):
        return self._on_change_lines_taxes(cursor, user, ids, vals, context=context)

    def _on_change_lines_taxes(self, cursor, user, ids, vals, context=None):
        currency_obj = self.pool.get('currency.currency')
        tax_obj = self.pool.get('account.tax')
        if context is None:
            context = {}
        res = {
            'untaxed_amount': Decimal('0.0'),
            'tax_amount': Decimal('0.0'),
            'total_amount': Decimal('0.0'),
            'taxes': {},
        }
        currency = None
        if vals.get('currency'):
            currency = currency_obj.browse(cursor, user, vals['currency'],
                    context=context)
        computed_taxes = {}
        if vals.get('lines'):
            ctx = context.copy()
            ctx.update(self.get_tax_context(cursor, user, vals,
                context=context))
            for line in vals['lines']:
                if line.get('type', 'line') != 'line':
                    continue
                res['untaxed_amount'] += line.get('amount', Decimal('0.0'))

                for tax in tax_obj.compute(cursor, user, line.get('taxes', []),
                        line.get('unit_price', Decimal('0.0')),
                        line.get('quantity', 0.0), context=context):
                    key, val = self._compute_tax(cursor, user, tax,
                            vals.get('type', 'out_invoice'), context=context)
                    if not key in computed_taxes:
                        computed_taxes[key] = val
                    else:
                        computed_taxes[key]['base'] += val['base']
                        computed_taxes[key]['amount'] += val['amount']
        tax_keys = []
        for tax in vals.get('taxes', []):
            if tax.get('manual', False):
                res['tax_amount'] += tax.get('amount', Decimal('0.0'))
                continue
            key = (tax.get('base_code'), tax.get('base_sign'),
                    tax.get('tax_code'), tax.get('tax_sign'),
                    tax.get('account'), tax.get('description'))
            tax_keys.append(key)
            if key not in computed_taxes:
                res['taxes'].setdefault('remove', [])
                res['taxes']['remove'].append(tax.get('id'))
                continue
            if currency:
                if not currency_obj.is_zero(cursor, user, currency,
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
                        tax.get('base', Decimal('0.0')) == Decimal('0.0'):
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
                res['taxes']['add'].append(computed_taxes[key])
        if currency:
            res['untaxed_amount'] = currency_obj.round(cursor, user, currency,
                    res['untaxed_amount'])
            res['tax_amount'] = currency_obj.round(cursor, user, currency,
                    res['tax_amount'])
        res['total_amount'] = res['untaxed_amount'] + res['tax_amount']
        if currency:
            res['total_amount'] = currency_obj.round(cursor, user, currency,
                    res['total_amount'])
        return res

    def get_untaxed_amount(self, cursor, user, ids, name, arg, context=None):
        currency_obj = self.pool.get('currency.currency')
        res = {}
        for invoice in self.browse(cursor, user, ids, context=context):
            res.setdefault(invoice.id, Decimal('0.0'))
            for line in invoice.lines:
                if line.type != 'line':
                    continue
                res[invoice.id] += line.amount
            res[invoice.id] = currency_obj.round(cursor, user, invoice.currency,
                    res[invoice.id])
        return res

    def get_tax_amount(self, cursor, user, ids, name, arg, context=None):
        currency_obj = self.pool.get('currency.currency')
        res = {}
        cursor.execute('SELECT invoice, ' \
                    'COALESCE(SUM(amount), 0)::DECIMAL ' \
                'FROM account_invoice_tax ' \
                'WHERE invoice IN (' + ','.join(['%s' for x in ids]) + ') ' \
                'GROUP BY invoice', ids)
        for invoice_id, sum in cursor.fetchall():
            res[invoice_id] = sum

        for invoice in self.browse(cursor, user, ids, context=context):
            res.setdefault(invoice.id, Decimal('0.0'))
            res[invoice.id] = currency_obj.round(cursor, user, invoice.currency,
                    res[invoice.id])
        return res

    def get_total_amount(self, cursor, user, ids, name, arg, context=None):
        currency_obj = self.pool.get('currency.currency')
        res = {}
        for invoice in self.browse(cursor, user, ids, context=context):
            res[invoice.id] = currency_obj.round(cursor, user, invoice.currency,
                    invoice.untaxed_amount + invoice.tax_amount)
        return res

    def get_reconciled(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for invoice in self.browse(cursor, user, ids, context=context):
            res[invoice.id] = True
            if not invoice.lines_to_pay:
                res[invoice.id] = False
                continue
            for line in invoice.lines_to_pay:
                if not line.reconciliation:
                    res[invoice.id] = False
                    break
        return res

    def get_lines_to_pay(self, cursor, user, ids, name, args, context=None):
        res = {}
        for invoice in self.browse(cursor, user, ids, context=context):
            lines = []
            if invoice.move:
                for line in invoice.move.lines:
                    if line.account.id == invoice.account.id \
                            and line.maturity_date:
                        lines.append(line)
            lines.sort(lambda x, y: cmp(x.maturity_date, y.maturity_date))
            res[invoice.id] = [x.id for x in lines]
        return res

    def get_amount_to_pay(self, cursor, user, ids, name, arg,
            context=None):
        currency_obj = self.pool.get('currency.currency')
        res = {}
        for invoice in self.browse(cursor, user, ids, context=context):
            amount = Decimal('0.0')
            amount_currency = Decimal('0.0')
            for line in invoice.lines_to_pay:
                if line.reconciliation:
                    continue
                if name == 'amount_to_pay_today' \
                        and line.maturity_date > datetime.date.today():
                    continue
                if line.second_currency.id == invoice.currency.id:
                    if line.debit - line.credit > Decimal('0.0'):
                        amount_currency += line.amount_second_currency
                    else:
                        amount_currency -= line.amount_second_currency
                else:
                    amount += line.debit - line.credit
            for line in invoice.payment_lines:
                if line.reconciliation:
                    continue
                if line.second_currency.id == invoice.currency.id:
                    if line.debit - line.credit > Decimal('0.0'):
                        amount_currency += line.amount_second_currency
                    else:
                        amount_currency -= line.amount_second_currency
                else:
                    amount += line.debit - line.credit
            if invoice.type in ('in_invoice', 'out_refund'):
                amount = - amount
                amount_currency = - amount_currency
            if amount != Decimal('0.0'):
                amount_currency += currency_obj.compute(cursor, user,
                        invoice.company.currency, amount, invoice.currency,
                        context=context)
            if amount_currency < Decimal('0.0'):
                amount_currency = Decimal('0.0')
            res[invoice.id] = amount_currency
        return res

    def button_draft(self, cursor, user, ids, context=None):
        workflow_service = LocalService('workflow')
        for invoice in self.browse(cursor, user, ids, context=context):
            if invoice.move:
                self.raise_user_error(cursor, 'reset_draft',
                        context=context)
            workflow_service.trg_create(user, 'account.invoice',
                    invoice.id, cursor)
        self.write(cursor, user, ids, {'state': 'draft'})
        return True

    def get_tax_context(self, cursor, user, invoice, context=None):
        party_obj = self.pool.get('relationship.party')
        res = {}
        if isinstance(invoice, dict):
            if invoice.get('party'):
                party = party_obj.browse(cursor, user, invoice['party'],
                        context=context)
                if party.lang:
                    res['language'] = party.lang.code
        else:
            if invoice.party.lang:
                res['language'] = invoice.party.lang.code
        return res

    def _compute_tax(self, cursor, user, tax, invoice_type, context=None):
        val = {}
        val['manual'] = False
        val['description'] = tax['tax'].description
        val['base'] = tax['base']
        val['amount'] = tax['amount']

        if invoice_type in ('out_invoice', 'in_invoice'):
            val['base_code'] = tax['tax'].invoice_base_code.id
            val['base_sign'] = tax['tax'].invoice_base_sign
            val['tax_code'] = tax['tax'].invoice_tax_code.id
            val['tax_sign'] = tax['tax'].invoice_tax_sign
            val['account'] = tax['tax'].invoice_account.id
        else:
            val['base_code'] = tax['tax'].refund_base_code.id
            val['base_sign'] = tax['tax'].refund_base_sign
            val['tax_code'] = tax['tax'].refund_tax_code.id
            val['tax_sign'] = tax['tax'].refund_tax_sign
            val['account'] = tax['tax'].refund_account.id
        key = (val['base_code'], val['base_sign'],
                val['tax_code'], val['tax_sign'],
                val['account'], val['description'])
        return key, val

    def _compute_taxes(self, cursor, user, invoice, context=None):
        tax_obj = self.pool.get('account.tax')
        currency_obj = self.pool.get('currency.currency')
        if context is None:
            context = {}

        ctx = context.copy()
        ctx.update(self.get_tax_context(cursor, user, invoice,
            context=context))

        res = {}
        for line in invoice.lines:
            # Don't round on each line to handle rounding error
            if line.type != 'line':
                continue
            tax_ids = [x.id for x in line.taxes]
            for tax in tax_obj.compute(cursor, user, tax_ids, line.unit_price,
                    line.quantity, context=ctx):
                key, val = self._compute_tax(cursor, user, tax, invoice.type,
                        context=context)
                val['invoice'] = invoice.id
                if not key in res:
                    res[key] = val
                else:
                    res[key]['base'] += val['base']
                    res[key]['amount'] += val['amount']
        return res

    def update_taxes(self, cursor, user, ids, context=None, exception=False):
        tax_obj = self.pool.get('account.invoice.tax')
        currency_obj = self.pool.get('currency.currency')
        for invoice in self.browse(cursor, user, ids, context=context):
            computed_taxes = self._compute_taxes(cursor, user, invoice,
                    context=context)
            if not invoice.taxes:
                for tax in computed_taxes.values():
                    tax_obj.create(cursor, user, tax, context=context)
            else:
                tax_keys = []
                for tax in invoice.taxes:
                    if tax.manual:
                        continue
                    key = (tax.base_code.id, tax.base_sign,
                            tax.tax_code.id, tax.tax_sign,
                            tax.account.id, tax.description)
                    tax_keys.append(key)
                    if not key in computed_taxes:
                        if exception:
                            self.raise_user_error(cursor, 'missing_tax_line',
                                    context=context)
                        tax_obj.delete(cursor, user, tax.id,
                                context=context)
                        continue
                    if not currency_obj.is_zero(cursor, user,
                            invoice.currency,
                            computed_taxes[key]['base'] - tax.base):
                        if exception:
                            self.raise_user_error(cursor, 'diff_tax_line',
                                    context=context)
                        tax_obj.write(cursor, user, tax.id,
                                computed_taxes[key], context=context)
                for key in computed_taxes:
                    if not key in tax_keys:
                        if exception:
                            self.raise_user_error(cursor, 'missing_tax_line',
                                    context=context)
                        tax_obj.create(cursor, user, computed_taxes[key],
                                context=context)
        return True

    def _get_move_line_invoice_line(self, cursor, user, invoice, context=None):
        '''
        Return list of move line values for each invoice lines
        '''
        line_obj = self.pool.get('account.invoice.line')
        res = []
        for line in invoice.lines:
            val = line_obj.get_move_line(cursor, user, line,
                    context=context)
            if val:
                res.append(val)
        return res

    def _get_move_line_invoice_tax(self, cursor, user, invoice, context=None):
        '''
        Return list of move line values for each invoice taxes
        '''
        tax_obj = self.pool.get('account.invoice.tax')
        res = []
        for tax in invoice.taxes:
            val = tax_obj.get_move_line(cursor, user, tax,
                    context=context)
            res.append(val)
        return res

    def _get_move_line(self, cursor, user, invoice, date, amount, context=None):
        '''
        Return move line
        '''
        currency_obj = self.pool.get('currency.currency')
        res = {}
        if invoice.currency.id != invoice.company.currency.id:
            res['amount_second_currency'] = currency_obj.compute(cursor, user,
                    invoice.company.currency, amount,
                    invoice.currency, context=context)
            res['amount_second_currency'] = abs(res['amount_second_currency'])
            res['second_currency'] = invoice.currency.id
        else:
            res['amount_second_currency'] = Decimal('0.0')
            res['second_currency'] = False
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

    def create_move(self, cursor, user, invoice_id, context=None):
        tax_obj = self.pool.get('account.invoice.tax')
        payment_term_obj = self.pool.get('account.invoice.payment_term')
        currency_obj = self.pool.get('currency.currency')
        move_obj = self.pool.get('account.move')
        period_obj = self.pool.get('account.period')

        invoice = self.browse(cursor, user, invoice_id, context=context)
        if invoice.move:
            return True
        self.update_taxes(cursor, user, [invoice.id], context=context,
                exception=True)
        move_lines = self._get_move_line_invoice_line(cursor, user, invoice,
                context=context)
        move_lines += self._get_move_line_invoice_tax(cursor, user, invoice,
                context=context)

        total = Decimal('0.0')
        total_currency = Decimal('0.0')
        for line in move_lines:
            total += line['debit'] - line['credit']
            total_currency += line['amount_second_currency']

        term_lines = payment_term_obj.compute(cursor, user, total,
                invoice.company.currency, invoice.payment_term,
                invoice.invoice_date, context=context)
        remainder_total_currency = total_currency
        for date, amount in term_lines:
            val = self._get_move_line(cursor, user, invoice, date, amount,
                    context=None)
            remainder_total_currency -= val['amount_second_currency']
            move_lines.append(val)
        if not currency_obj.is_zero(cursor, user, invoice.currency,
                remainder_total_currency):
            move_lines[-1]['amount_second_currency'] += remainder_total_currency

        period_id = period_obj.find(cursor, user, invoice.company.id,
                date=invoice.invoice_date, context=context)

        move_id = move_obj.create(cursor, user, {
            'journal': invoice.journal.id,
            'period': period_id,
            'date': invoice.invoice_date,
            'lines': [('create', x) for x in move_lines],
            }, context=context)
        self.write(cursor, user, invoice.id, {
            'move': move_id,
            }, context=context)
        move_obj.post(cursor, user, move_id, context=context)
        return move_id

    def set_number(self, cursor, user, invoice_id, context=None):
        period_obj = self.pool.get('account.period')
        sequence_obj = self.pool.get('ir.sequence.strict')

        if context is None:
            context = {}

        invoice = self.browse(cursor, user, invoice_id, context=context)

        if invoice.number:
            return True

        period_id = period_obj.find(cursor, user, invoice.company.id,
                date=invoice.invoice_date, context=context)
        period = period_obj.browse(cursor, user, period_id, context=context)
        sequence_id = period[invoice.type + '_sequence'].id
        if not sequence_id:
            self.raise_user_error(cursor, 'no_invoice_sequence',
                    context=context)
        ctx = context.copy()
        ctx['date'] = invoice.invoice_date
        number = sequence_obj.get_id(cursor, user, sequence_id, context=ctx)
        self.write(cursor, user, invoice_id, {
            'number': number,
            }, context=context)
        return True

    def check_modify(self, cursor, user, ids, context=None):
        '''
        Check if the invoices can be modified
        '''
        for invoice in self.browse(cursor, user, ids, context=context):
            if invoice.state in ('open', 'paid'):
                self.raise_user_error(cursor, 'modify_invoice',
                        context=context)
        return

    def name_get(self, cursor, user, ids, context=None):
        if not ids:
            return []
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = []
        for invoice in self.browse(cursor, user, ids, context=context):
            res.append((invoice.id,
                invoice.number or str(invoice.id) + ' ' + invoice.party.name))
        return res

    def name_search(self, cursor, user, name='', args=None, operator='ilike',
            context=None, limit=None):
        if args is None:
            args = []
        if name:
            ids = self.search(cursor, user, [('number', operator, name)] + args,
                    limit=limit, context=context)
        if not ids:
            ids = self.search(cursor, user, [('party', operator, name)] + args,
                    limit=limit, context=context)
        res = self.name_get(cursor, user, ids, context=context)
        return res

    def delete(self, cursor, user, ids, context=None):
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.check_modify(cursor, user, ids, context=context)
        return super(Invoice, self).delete(cursor, user, ids,
                context=context)

    def write(self, cursor, user, ids, vals, context=None):
        workflow_service = LocalService('workflow')
        if isinstance(ids, (int, long)):
            ids = [ids]
        keys = vals.keys()
        for key in ('state', 'payment_lines',
                'invoice_report', 'invoice_report_format'):
            if key in keys:
                keys.remove(key)
        if len(keys):
            self.check_modify(cursor, user, ids, context=context)
        res = super(Invoice, self).write(cursor, user, ids, vals,
                context=context)
        self.update_taxes(cursor, user, ids, context=context)
        if 'state' in vals and vals['state'] in ('paid', 'cancel'):
            for invoice_id in ids:
                workflow_service.trg_trigger(user, self._name, invoice_id,
                        cursor)
        return res

    def copy(self, cursor, user, invoice_id, default=None, context=None):
        line_obj = self.pool.get('account.invoice.line')
        tax_obj = self.pool.get('account.invoice.tax')

        if default is None:
            default = {}
        default = default.copy()
        default['state'] = 'draft'
        default['number'] = False
        default['move'] = False
        default['invoice_report'] = False
        default['invoice_report_format'] = False
        default['payment_lines'] = False
        default['lines'] = False
        default['taxes'] = False
        default['date'] = datetime.date.today()
        default['lines_to_pay'] = False
        new_id = super(Invoice, self).copy(cursor, user, invoice_id,
                default=default, context=context)

        invoice = self.browse(cursor, user, invoice_id, context=context)
        for line in invoice.lines:
            line_obj.copy(cursor, user, line.id, default={
                'invoice': new_id,
                }, context=context)

        for tax in invoice.taxes:
            tax_obj.copy(cursor, user, tax.id, default={
                'invoice': new_id,
                }, context=context)
        return new_id

    def check_account(self, cursor, user, ids):
        for invoice in self.browse(cursor, user, ids):
            if invoice.account.company.id != invoice.company.id:
                return False
        return True

    def check_account2(self, cursor, user, ids):
        for invoice in self.browse(cursor, user, ids):
            for line in invoice.lines:
                if line.type == 'line' \
                        and line.account.id == invoice.account.id:
                    return False
        return True

    def get_reconcile_lines_for_amount(self, cursor, user, invoice, amount,
            exclude_ids=None, context=None):
        '''
        Return list of line ids and the remainder to make reconciliation.
        '''
        currency_obj = self.pool.get('currency.currency')

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

        if invoice.type in ('out_invoice', 'in_refund'):
            amount = - abs(amount)
        else:
            amount = abs(amount)

        for line in invoice.lines_to_pay:

            if line.reconciliation:
                continue
            if line.id in exclude_ids:
                continue

            test_amount = amount + (line.debit - line.credit)
            if currency_obj.is_zero(cursor, user, invoice.currency,
                    test_amount):
                return ([line.id], Decimal('0.0'))
            if abs(test_amount) < abs(remainder):
                lines = [line.id]
                remainder = test_amount

            test_amount = (amount + payment_amount) + (line.debit - line.credit)
            if currency_obj.is_zero(cursor, user, invoice.currency,
                    test_amount):
                return ([line.id] + payment_lines, Decimal('0.0'))
            if abs(test_amount) < abs(remainder):
                lines = [line.id] + payment_lines
                remainder = test_amount

            exclude_ids2 = exclude_ids[:]
            exclude_ids2.append(line.id)
            res = self.get_reconcile_lines_for_amount(cursor, user, invoice,
                    (amount + (line.debit - line.credit)),
                    exclude_ids=exclude_ids2, context=context)
            if res[1] == Decimal('0.0'):
                res[0].append(line.id)
                return res
            if abs(res[1]) < abs(remainder):
                res[0].append(line.id)
                lines = res[0]
                remainder = res[1]

        return (lines, remainder)

    def pay_invoice(self, cursor, user, invoice_id, amount, journal_id, date,
            description, amount_second_currency=False, second_currency=False,
            context=None):
        journal_obj = self.pool.get('account.journal')
        move_obj = self.pool.get('account.move')
        period_obj = self.pool.get('account.period')

        lines = []
        invoice = self.browse(cursor, user, invoice_id, context=context)
        journal = journal_obj.browse(cursor, user, journal_id, context=context)

        if invoice.type in ('out_invoice', 'in_refund'):
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
                self.raise_user_error(cursor, 'same_debit_account',
                        context=context)
            if not journal.debit_account:
                self.raise_user_error(cursor, 'missing_debit_account',
                        context=context)
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
            if invoice.account.id == journal.debit_account.id:
                self.raise_user_error(cursor, 'same_credit_account',
                        context=context)
            if not journal.credit_account:
                self.raise_user_error(cursor, 'missing_credit_account',
                        context=context)

        period_id = period_obj.find(cursor, user, invoice.company.id,
                date=date, context=context)

        move_id = move_obj.create(cursor, user, {
            'journal': journal.id,
            'period': period_id,
            'date': date,
            'lines': [('create', x) for x in lines],
            }, context=context)

        move = move_obj.browse(cursor, user, move_id, context=context)

        for line in move.lines:
            if line.account.id == invoice.account.id:
                self.write(cursor, user, invoice.id, {
                    'payment_lines': [('add', line.id)],
                    }, context=context)
                return line.id
        raise Exception('Missing account')

    def print_invoice(self, cursor, user, invoice_id, context=None):
        '''
        Generate invoice report and store it in invoice_report field.
        '''
        invoice_report = get_pool_report(cursor.dbname).get('account.invoice')
        val = invoice_report.execute(cursor, user, [invoice_id],
                {'id': invoice_id}, context=context)
        self.write(cursor, user, invoice_id, {
            'invoice_report_format': val[0],
            'invoice_report': val[1],
            }, context=context)
        return

    def _refund(self, cursor, user, invoice, context=None):
        '''
        Return values to refund invoice.
        '''
        invoice_line_obj = self.pool.get('account.invoice.line')
        invoice_tax_obj = self.pool.get('account.invoice.tax')

        res = {}
        if invoice.type == 'out_invoice':
            res['type'] = 'out_refund'
        elif invoice.type == 'in_invoice':
            res['type'] = 'in_refund'
        elif invoice.type == 'out_refund':
            res['type'] = 'out_invoice'
        elif invoice.type == 'in_refund':
            res['type'] = 'in_invoice'

        for field in ('reference', 'description', 'comment'):
            res[field] = invoice[field]

        for field in ('company', 'party', 'contact_address',
                'invoice_address', 'currency', 'journal', 'account',
                'payment_term'):
            res[field] = invoice[field].id

        res['lines'] = []
        for line in invoice.lines:
            value = invoice_line_obj._refund(cursor, user, line,
                    context=context)
            res['lines'].append(('create', value))

        res['taxes'] = []
        for tax in invoice.taxes:
            if not tax.manual:
                continue
            value = invoice_tax_obj._refund(cursor, user, tax,
                    context=context)
            res[taxes].append(('create', value))
        return res

    def refund(self, cursor, user, ids, context=None):
        '''
        Refund invoices and return ids of new invoices.
        '''
        new_ids = []
        for invoice in self.browse(cursor, user, ids, context=context):
            vals = self._refund(cursor, user, invoice, context=context)
            new_ids.append(self.create(cursor, user, vals, context=context))
        return new_ids

Invoice()


class InvoiceLine(OSV):
    'Invoice Line'
    _name = 'account.invoice.line'
    _rec_name = 'description'
    _description = __doc__

    invoice = fields.Many2One('account.invoice', 'Invoice', ondelete='CASCADE',
            select=1, required=True)
    sequence = fields.Integer('Sequence')
    type = fields.Selection([
        ('line', 'Line'),
        ('subtotal', 'Subtotal'),
        ('title', 'Title'),
        ('comment', 'Comment'),
        ], 'Type', select=1, required=True)
    quantity = fields.Float('Quantity',
            digits="(16, unit_digits)",
            states={
                'invisible': "type != 'line'",
                'required': "type == 'line'",
            })
    unit = fields.Many2One('product.uom', 'Unit',
            states={
                'required': "product",
                'invisible': "type != 'line'",
            }, domain="[('category', '=', " \
                    "(product, 'product.default_uom.category'))]")
    unit_digits = fields.Function('get_unit_digits', type='integer',
            string='Unit Digits', on_change_with=['unit'])
    product = fields.Many2One('product.product', 'Product',
            states={
                'invisible': "type != 'line'",
            }, on_change=['product', 'unit', 'quantity', 'description',
                '_parent_invoice.type', '_parent_invoice.party',
                '_parent_invoice.currency'])
    account = fields.Many2One('account.account', 'Account',
            domain="[('kind', '!=', 'view'), " \
                    "('company', '=', _parent_invoice.company), " \
                    "('id', '!=', _parent_invoice.account)]",
            states={
                'invisible': "type != 'line'",
                'required': "type == 'line'",
            })
    unit_price = fields.Numeric('Unit Price', digits=(16, 4),
            states={
                'invisible': "type != 'line'",
                'required': "type == 'line'",
            })
    amount = fields.Function('get_amount', type='numeric', string='Amount',
            digits="(16, _parent_invoice.currency_digits)",
            states={
                'invisible': "type not in ('line', 'subtotal')",
            }, on_change_with=['type', 'quantity', 'unit_price',
                '_parent_invoice.currency'])
    description = fields.Char('Description', size=None, required=True)
    taxes = fields.Many2Many('account.tax', 'account_invoice_line_account_tax',
            'line', 'tax', 'Taxes', domain=[('parent', '=', False)],
            states={
                'invisible': "type != 'line'",
            })

    def __init__(self):
        super(InvoiceLine, self).__init__()
        self._sql_constraints += [
            ('type_account',
                'CHECK((type = \'line\' AND account IS NOT NULL) ' \
                        'OR (type != \'line\'))',
                'Line type must have an account!'),
        ]
        self._constraints += [
            ('check_account', 'account_different_company'),
            ('check_account2', 'same_account_on_invoice'),
        ]
        self._order.insert(0, ('sequence', 'ASC'))
        self._error_messages.update({
            'modify': 'You can not modify line from an invoice ' \
                    'that is open, paid or canceled!',
            'create': 'You can not add a line to an invoice ' \
                    'that is open, paid or canceled!',
            'account_different_company': 'You can not create invoice line\n' \
                    'with account from a different invoice company!',
            'same_account_on_invoice': 'You can not use the same account\n' \
                    'than the invoice account!',
            })

    def default_type(self, cursor, user, context=None):
        return 'line'

    def default_quantity(self, cursor, user, context=None):
        return 0.0

    def default_unit_price(self, cursor, user, context=None):
        return Decimal('0.0')

    def on_change_with_amount(self, cursor, user, ids, vals, context=None):
        currency_obj = self.pool.get('currency.currency')
        if vals.get('type') == 'line':
            if isinstance(vals.get('_parent_invoice.currency'), (int, long)):
                currency = currency_obj.browse(cursor, user,
                        vals['_parent_invoice.currency'], context=context)
            else:
                currency = vals['_parent_invoice.currency']
            amount = Decimal(str(vals.get('quantity') or '0.0')) * \
                    (vals.get('unit_price') or Decimal('0.0'))
            if currency:
                return currency_obj.round(cursor, user, currency, amount)
            return amount
        return Decimal('0.0')

    def on_change_with_unit_digits(self, cursor, user, ids, vals,
            context=None):
        uom_obj = self.pool.get('product.uom')
        if vals.get('unit'):
            uom = uom_obj.browse(cursor, user, vals['unit'],
                    context=context)
            return uom.digits
        return 2

    def get_unit_digits(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for line in self.browse(cursor, user, ids, context=context):
            if line.unit:
                res[line.id] = line.unit.digits
            else:
                res[line.id] = 2
        return res

    def get_amount(self, cursor, user, ids, name, arg, context=None):
        currency_obj = self.pool.get('currency.currency')
        res = {}
        for line in self.browse(cursor, user, ids, context=context):
            if line.type == 'line':
                res[line.id] = currency_obj.round(cursor, user,
                        line.invoice.currency,
                        Decimal(str(line.quantity)) * line.unit_price)
            elif line.type == 'subtotal':
                res[line.id] = Decimal('0.0')
                for line2 in line.invoice.lines:
                    if line2.type == 'line':
                        res[line.id] += currency_obj.round(cursor, user,
                                line2.invoice.currency,
                                Decimal(str(line2.quantity)) * line2.unit_price)
                    elif line2.type == 'subtotal':
                        if line.id == line2.id:
                            break
                        res[line.id] = Decimal('0.0')
            else:
                res[line.id] = Decimal('0.0')
        return res

    def on_change_product(self, cursor, user, ids, vals, context=None):
        product_obj = self.pool.get('product.product')
        party_obj = self.pool.get('relationship.party')
        account_obj = self.pool.get('account.account')
        uom_obj = self.pool.get('product.uom')
        company_obj = self.pool.get('company.company')
        currency_obj = self.pool.get('currency.currency')
        if context is None:
            context = {}
        if not vals.get('product'):
            return {}
        res = {}

        ctx = context.copy()
        party = None
        if vals.get('_parent_invoice.party'):
            party = party_obj.browse(cursor, user, vals['_parent_invoice.party'],
                    context=context)
            if party.lang:
                ctx['language'] = party.lang.code

        product = product_obj.browse(cursor, user, vals['product'],
                context=context)

        company = None
        if context.get('company'):
            company = company_obj.browse(cursor, user, context['company'],
                    context=context)
        currency = None
        if vals.get('_parent_invoice.currency'):
            #TODO check if today date is correct
            currency = currency_obj.browse(cursor, user,
                    vals['_parent_invoice.currency'], context=context)

        if vals.get('_parent_invoice.type') in ('in_invoice', 'in_refund'):
            if company and currency:
                res['unit_price'] = currency_obj.compute(cursor, user,
                        company.currency, product.cost_price, currency,
                        round=False, context=context)
            else:
                res['unit_price'] = product.cost_price
            try:
                res['account'] = account_obj.name_get(cursor, user,
                        product.account_expense_used.id, context=context)[0]
            except:
                pass
            res['taxes'] = []
            for tax in product.supplier_taxes:
                if party:
                    if 'supplier_' + tax.group.code in party_obj._columns \
                            and party['supplier_' + tax.group.code]:
                        res['taxes'].append(
                                party['supplier_' + tax.group.code].id)
                        continue
                res['taxes'].append(tax.id)
        else:
            if company and currency:
                res['unit_price'] = currency_obj.compute(cursor, user,
                        company.currency, product.list_price, currency,
                        round=False, context=context)
            else:
                res['unit_price'] = product.list_price
            try:
                res['account'] = account_obj.name_get(cursor, user,
                        product.account_revenue_used.id, context=context)[0]
            except:
                pass
            res['taxes'] = []
            for tax in product.customer_taxes:
                if party:
                    if tax.group.code in party_obj._columns \
                            and party[tax.group.code]:
                        res['taxes'].append(party[tax.group.code].id)
                        continue
                res['taxes'].append(tax.id)

        if not vals.get('description'):
            res['description'] = product_obj.name_get(cursor, user, product.id,
                    context=ctx)[0][1]

        category = product.default_uom.category
        if not vals.get('unit') \
                or vals.get('unit') not in [x.id for x in category.uoms]:
            res['unit'] = uom_obj.name_get(cursor, user, product.default_uom.id,
                context=context)[0]
            res['unit_digits'] = product.default_uom.digits
        return res

    def check_modify(self, cursor, user, ids, context=None):
        '''
        Check if the lines can be modified
        '''
        for line in self.browse(cursor, user, ids, context=context):
            if line.invoice.state in ('open', 'paid', 'cancel'):
                self.raise_user_error(cursor, 'modify', context=context)
        return

    def delete(self, cursor, user, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.check_modify(cursor, user, ids, context=context)
        return super(InvoiceLine, self).delete(cursor, user, ids,
                context=context)

    def write(self, cursor, user, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.check_modify(cursor, user, ids, context=context)
        return super(InvoiceLine, self).write(cursor, user, ids, vals,
                context=context)

    def create(self, cursor, user, vals, context=None):
        invoice_obj = self.pool.get('account.invoice')
        if vals.get('invoice'):
            invoice = invoice_obj.browse(cursor, user, vals['invoice'],
                    context=context)
            if invoice.state in ('open', 'paid', 'cancel'):
                self.raise_user_error(cursor, 'create', context=context)
        return super(InvoiceLine, self).create(cursor, user, vals,
                context=context)

    def check_account(self, cursor, user, ids):
        for line in self.browse(cursor, user, ids):
            if line.type == 'line' \
                    and line.account.company.id != line.invoice.company.id:
                return False
        return True

    def check_account2(self, cursor, user, ids):
        for line in self.browse(cursor, user, ids):
            if line.type == 'line' \
                    and line.account.id == line.invoice.account.id:
                return False
        return True

    def _compute_taxes(self, cursor, user, line, context=None):
        tax_obj = self.pool.get('account.tax')
        currency_obj = self.pool.get('currency.currency')
        invoice_obj = self.pool.get('account.invoice')
        if context is None:
            context = {}

        ctx = context.copy()
        ctx.update(invoice_obj.get_tax_context(cursor, user, line.invoice,
            context=context))
        res = []
        if line.type != 'line':
            return res
        tax_ids = [x.id for x in line.taxes]
        for tax in tax_obj.compute(cursor, user, tax_ids, line.unit_price,
                line.quantity, context=ctx):
            if line.invoice.type in ('out_invoice', 'in_invoice'):
                base_code_id = tax['tax'].invoice_base_code.id
                amount = tax['base'] * tax['tax'].invoice_base_sign
            else:
                base_code_id = tax['tax'].refund_base_code.id
                amount = tax['base'] * tax['tax'].refund_base_sign
            if base_code_id:
                amount = currency_obj.compute(cursor, user,
                        line.invoice.currency, amount,
                        line.invoice.company.currency, context=context)
                res.append({
                    'code': base_code_id,
                    'amount': amount,
                })
        return res

    def get_move_line(self, cursor, user, line, context=None):
        '''
        Return move line value for invoice line
        '''
        currency_obj = self.pool.get('currency.currency')
        res = {}
        if line.type != 'line':
            return res
        res['name'] = line.description
        if line.invoice.currency.id != line.invoice.company.currency.id:
            amount = currency_obj.compute(cursor, user,
                    line.invoice.currency, line.amount,
                    line.invoice.company.currency, context=context)
            res['amount_second_currency'] = line.amount
            res['second_currency'] = line.invoice.currency.id
        else:
            amount = line.amount
            res['amount_second_currency'] = Decimal('0.0')
            res['second_currency'] = False
        if line.invoice.type in ('in_invoice', 'out_refund'):
            res['debit'] = amount
            res['credit'] = Decimal('0.0')
        else:
            res['debit'] = Decimal('0.0')
            res['credit'] = amount
            res['amount_second_currency'] = - res['amount_second_currency']
        res['account'] = line.account.id
        res['party'] = line.invoice.party.id
        computed_taxes = self._compute_taxes(cursor, user, line,
                context=context)
        for tax in computed_taxes:
            res.setdefault('tax_lines', [])
            res['tax_lines'].append(('create', tax))
        return res

    def _refund(self, cursor, user, line, context=None):
        '''
        Return values to refund line.
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


class InvoiceTax(OSV):
    'Invoice Tax'
    _name = 'account.invoice.tax'
    _rec_name = 'description'
    _description = __doc__

    invoice = fields.Many2One('account.invoice', 'Invoice', ondelete='CASCADE',
            select=1)
    description = fields.Char('Description', size=None, required=True)
    sequence = fields.Integer('Sequence')
    account = fields.Many2One('account.account', 'Account', required=True,
            domain="[('kind', '!=', 'view'), " \
                "('company', '=', _parent_invoice.company)]")
    base = fields.Numeric('Base', digits="(16, _parent_invoice.currency_digits)",
            states={
                'invisible': "manual",
            })
    amount = fields.Numeric('Amount', digits="(16, _parent_invoice.currency_digits)")
    manual = fields.Boolean('Manual')
    base_code = fields.Many2One('account.tax.code', 'Base Code',
            domain="[('company', '=', _parent_invoice.company)]",
            states={
                'invisible': "manual",
            })
    base_sign = fields.Numeric('Base Sign', digits=(2, 0),
            states={
                'invisible': "manual",
            })
    tax_code = fields.Many2One('account.tax.code', 'Tax Code',
            domain="[('company', '=', _parent_invoice.company)]")
    tax_sign = fields.Numeric('Tax Sign', digits=(2, 0))

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
                    'that is open, paid or canceled!',
            'create': 'You can not add a line to an invoice ' \
                    'that is open, paid or canceled!',
            })

    def default_base(self, cursor, user, context=None):
        return Decimal('0.0')

    def default_amount(self, cursor, user, context=None):
        return Decimal('0.0')

    def default_manual(self, cursor, user, context=None):
        return True

    def default_base_sign(self, cursor, user, context=None):
        return Decimal('1')

    def default_tax_sign(self, cursor, user, context=None):
        return Decimal('1')

    def check_modify(self, cursor, user, ids, context=None):
        '''
        Check if the taxes can be modified
        '''
        for tax in self.browse(cursor, user, ids, context=context):
            if tax.invoice.state in ('open', 'paid', 'cancel'):
                self.raise_user_error(cursor, 'modify',
                        context=context)
        return

    def delete(self, cursor, user, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.check_modify(cursor, user, ids, context=context)
        return super(InvoiceTax, self).delete(cursor, user, ids,
                context=context)

    def write(self, cursor, user, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.check_modify(cursor, user, ids, context=context)
        return super(InvoiceTax, self).write(cursor, user, ids, vals,
                context=context)

    def create(self, cursor, user, vals, context=None):
        invoice_obj = self.pool.get('account.invoice')
        if vals.get('invoice'):
            invoice = invoice_obj.browse(cursor, user, vals['invoice'],
                    context=context)
            if invoice.state in ('open', 'paid', 'cancel'):
                self.raise_user_error(cursor, 'create', context=context)
        return super(InvoiceTax, self).create(cursor, user, vals,
                context=context)

    def check_company(self, cursor, user, ids):
        for tax in self.browse(cursor, user, ids):
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

    def get_move_line(self, cursor, user, tax, context=None):
        '''
        Return move line value for invoice tax
        '''
        currency_obj = self.pool.get('currency.currency')
        res = {}
        res['name'] = tax.description
        if tax.invoice.currency.id != tax.invoice.company.currency.id:
            amount = currency_obj.compute(cursor, user,
                    tax.invoice.currency, tax.amount,
                    tax.invoice.company.currency, context=context)
            res['amount_second_currency'] = tax.amount * tax.tax_sign
            res['second_currency'] = tax.invoice.currency.id
        else:
            amount = tax.amount
            res['amount_second_currency'] = Decimal('0.0')
            res['second_currency'] = False
        amount *= tax.tax_sign
        if tax.invoice.type in ('in_invoice', 'out_refund'):
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
                'amount': amount,
            })]
        return res

    def _refund(self, cursor, user, tax, context=None):
        '''
        Return values to refund tax.
        '''
        res = {}

        for field in ('description', 'sequence', 'base', 'amount',
                'manual', 'base_sign', 'tax_sign'):
            res[field] = tax[field]

        for field in ('account', 'base_code', 'tax_code'):
            res[field] = tax[field].id
        return res

InvoiceTax()


class PrintInvoiceReportWarning(WizardOSV):
    _name = 'account.invoice.print_invoice_report.warning'

PrintInvoiceReportWarning()


class PrintInvoiceReport(Wizard):
    'Print Invoice Report'
    _name = 'account.invoice.print_invoice_report'
    states = {
        'init': {
            'result': {
                'type': 'choice',
                'next_state': '_choice',
            },
        },
        'warning': {
            'result': {
                'type': 'form',
                'object': 'account.invoice.print_invoice_report.warning',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('print', 'Print', 'tryton-ok', True),
                ],
            },
        },
        'print': {
            'actions': ['_print_init'],
            'result': {
                'type': 'print',
                'report': 'account.invoice',
                'state': 'print_next',
                'get_id_from_action': True,
            },
        },
        'print_next': {
            'actions': ['_next_id'],
            'result': {
                'type': 'choice',
                'next_state': '_print_next',
            },
        }
    }

    def _choice(self, cursor, user, data, context=None):
        if len(data['ids']) > 1:
            return 'warning'
        return 'print'

    def _print_init(self, cursor, user, data, context=None):
        res = {}
        if 'ids' in data['form']:
            res['ids'] = data['form']['ids']
        else:
            res['ids'] = data['ids']
        return res

    def _next_id(self, cursor, user, data, context=None):
        res = {}
        if data['form']['ids']:
            data['form']['ids'].pop(0)
        res['ids'] = data['form']['ids']
        return res

    def _print_next(self, cursor, user, data, context=None):
        if not data['form']['ids']:
            return 'end'
        return 'print'

PrintInvoiceReport()


class InvoiceReport(Report):
    _name = 'account.invoice'

    def execute(self, cursor, user, ids, datas, context=None):
        if context is None:
            context = {}
        res = super(InvoiceReport, self).execute(cursor, user, ids, datas,
                context=context)
        if len(ids) > 1 or datas['id'] != ids[0]:
            res = (res[0], res[1], True)
        return res

    def _get_objects(self, cursor, user_id, ids, model, datas, context):
        invoice_obj = self.pool.get('account.invoice')

        if context is None:
            context = {}

        context = context.copy()
        if 'language' in context:
            del context['language']
        return invoice_obj.browse(cursor, user_id, [ids[0]], context=context)

    def parse(self, cursor, user_id, report, objects, datas, context):
        user_obj = self.pool.get('res.user')
        invoice_obj = self.pool.get('account.invoice')

        invoice = objects[0]

        if invoice.invoice_report:
            return (invoice.invoice_report_format,
                    base64.decodestring(invoice.invoice_report))

        user = user_obj.browse(cursor, user_id, user_id, context)
        if context is None:
            context = {}
        context = context.copy()
        context['company'] = user.company
        res = super(InvoiceReport, self).parse(cursor, user_id, report, objects,
                datas, context)
        #If the invoice is open or paid and the report not saved in invoice_report
        #there was an error somewhere. So we save it now in invoice_report
        if invoice.state in ('open', 'paid'):
            invoice_obj.write(cursor, user_id, invoice.id, {
                'invoice_report_format': res[0],
                'invoice_report': base64.encodestring(res[1]),
                }, context=context)
        return res

InvoiceReport()


class Address(OSV):
    _name = 'relationship.address'
    invoice = fields.Boolean('Invoice')

Address()


class Party(OSV):
    _name = 'relationship.party'
    payment_term = fields.Property(type='many2one',
            relation='account.invoice.payment_term',
            string='Invoice Payment Term', group_name='Accounting Properties',
            view_load=True)
    supplier_payment_term = fields.Property(type='many2one',
            relation='account.invoice.payment_term',
            string='Supplier Payment Term', group_name='Accounting Properties',
            view_load=True)

Party()


class Category(OSV):
    _name = 'product.category'
    account_expense = fields.Property(type='many2one',
            relation='account.account', string='Account Expense',
            group_name='Accounting Properties', view_load=True,
            domain="[('kind', '=', 'expense'), ('company', '=', company)]",
            states={
                'invisible': "not company",
            })
    account_revenue = fields.Property(type='many2one',
            relation='account.account', string='Account Revenue',
            group_name='Accounting Properties', view_load=True,
            domain="[('kind', '=', 'revenue'), ('company', '=', company)]",
            states={
                'invisible': "not company",
            })

Category()


class Template(OSV):
    _name = 'product.template'
    account_expense = fields.Property(type='many2one',
            string='Account Expense', group_name='Accounting Properties',
            view_load=True, relation='account.account',
            domain="[('kind', '=', 'expense'), ('company', '=', company)]",
            states={
                'invisible': "not company",
            }, help='This account will be used instead of the one defined ' \
                    'on the category.')
    account_revenue = fields.Property(type='many2one',
            string='Account Revenue', group_name='Accounting Properties',
            view_load=True, relation='account.account',
            domain="[('kind', '=', 'revenue'), ('company', '=', company)]",
            states={
                'invisible': "not company",
            }, help='This account will be used instead of the one defined ' \
                    'on the category.')
    account_expense_used = fields.Function('get_account', type='many2one',
            relation='account.account', string='Account Expense Used')
    account_revenue_used = fields.Function('get_account', type='many2one',
            relation='account.account', string='Account Revenue Used')
    customer_taxes = fields.Many2Many('account.tax',
            'product_customer_taxes_rel', 'product', 'tax',
            'Customer Taxes', domain=[('parent', '=', False)])
    supplier_taxes = fields.Many2Many('account.tax',
            'product_supplier_taxes_rel', 'product', 'tax',
            'Supplier Taxes', domain=[('parent', '=', False)])

    def __init__(self):
        super(Template, self).__init__()
        self._error_messages.update({
            'missing_account': 'There is no account ' \
                    'expense/revenue define on the product ' \
                    '%s (%d)',
            })

    def get_account(self, cursor, user, ids, name, arg, context=None):
        account_obj = self.pool.get('account.account')
        res = {}
        name = name[:-5]
        for product in self.browse(cursor, user, ids, context=context):
            if product[name]:
                res[product.id] = account_obj.name_get(cursor, user,
                        product[name].id, context=context)[0]
            else:
                if product.category[name]:
                    res[product.id] = account_obj.name_get(cursor, user,
                            product.category[name].id, context=context)[0]
                else:
                    self.raise_user_error(cursor, 'missing_account',
                            (product.name, product.id), context=context)
        return res

Template()


class FiscalYear(OSV):
    _name = 'account.fiscalyear'
    out_invoice_sequence = fields.Many2One('ir.sequence.strict',
            'Customer Invoice Sequence', required=True,
            domain="[('code', '=', 'account.invoice')]")
    in_invoice_sequence = fields.Many2One('ir.sequence.strict',
            'Supplier Invoice Sequence', required=True,
            domain="[('code', '=', 'account.invoice')]")
    out_refund_sequence = fields.Many2One('ir.sequence.strict',
            'Customer Refund Sequence', required=True,
            domain="[('code', '=', 'account.invoice')]")
    in_refund_sequence = fields.Many2One('ir.sequence.strict',
            'Supplier Refund Sequence', required=True,
            domain="[('code', '=', 'account.invoice')]")

    def __init__(self):
        super(FiscalYear, self).__init__()
        self._constraints += [
            ('check_invoice_sequences',
                'Error! You must have different invoice sequence ' \
                        'per fiscal year!', ['out_invoice_sequence',
                            'in_invoice_sequence', 'out_refund_sequence',
                            'in_refund_sequence']),
        ]
        self._error_messages.update({
            'change_invoice_sequence': 'You can not change ' \
                    'the invoice sequence if there is already ' \
                    'an invoice opened in the fiscalyear',
            })

    def check_invoice_sequences(self, cursor, user, ids):
        for fiscalyear in self.browse(cursor, user, ids):
            for sequence in ('out_invoice_sequence', 'in_invoice_sequence',
                    'out_refund_sequence', 'in_refund_sequence'):
                if self.search(cursor, user, [
                    (sequence, '=', fiscalyear[sequence].id),
                    ('id', '!=', fiscalyear.id),
                    ]):
                    return False
        return True

    def write(self, cursor, user, ids, vals, context=None):
        invoice_obj = self.pool.get('account.invoice')
        for sequence in ('out_invoice_sequence', 'in_invoice_sequence',
                'out_refund_sequence', 'in_refund_sequence'):
            if vals.get(sequence):
                for fiscalyear in self.browse(cursor, user, ids,
                        context=context):
                    if fiscalyear[sequence] and \
                            fiscalyear[sequence].id != \
                            vals[sequence]:
                        if invoice_obj.search(cursor, user, [
                            ('invoice_date', '>=', fiscalyear.start_date),
                            ('invoice_date', '<=', fiscalyear.end_date),
                            ('number', '!=', False),
                            ('type', '=', sequence[:-9]),
                            ], context=context):
                            self.raise_user_error(cursor,
                                    'change_invoice_sequence', context=context)
        return super(FiscalYear, self).write(cursor, user, ids, vals,
                context=context)

FiscalYear()


class Period(OSV):
    _name = 'account.period'
    out_invoice_sequence = fields.Many2One('ir.sequence.strict',
            'Customer Invoice Sequence',
            domain="[('code', '=', 'account.invoice')]",
            states={
                'required': "type == 'standard'",
                'invisible': "type != 'standard'",
            })
    in_invoice_sequence = fields.Many2One('ir.sequence.strict',
            'Supplier Invoice Sequence',
            domain="[('code', '=', 'account.invoice')]",
            states={
                'required': "type == 'standard'",
                'invisible': "type != 'standard'",
            })
    out_refund_sequence = fields.Many2One('ir.sequence.strict',
            'Customer Refund Sequence',
            domain="[('code', '=', 'account.invoice')]",
            states={
                'required': "type == 'standard'",
                'invisible': "type != 'standard'",
            })
    in_refund_sequence = fields.Many2One('ir.sequence.strict',
            'Supplier Refund Sequence',
            domain="[('code', '=', 'account.invoice')]",
            states={
                'required': "type == 'standard'",
                'invisible': "type != 'standard'",
            })

    def __init__(self):
        super(Period, self).__init__()
        self._constraints += [
            ('check_invoice_sequences',
                'Error! You must have different invoice sequences ' \
                        'per fiscal year!', ['out_invoice_sequence',
                            'in_invoice_sequence', 'out_refund_sequence',
                            'in_refund_sequence']),
        ]
        self._error_messages.update({
            'change_invoice_sequence': 'You can not change ' \
                    'the invoice sequence if there is already ' \
                    'an invoice opened in the period',
            })

    def check_invoice_sequences(self, cursor, user, ids):
        for period in self.browse(cursor, user, ids):
            for sequence in ('out_invoice_sequence', 'in_invoice_sequence',
                    'out_refund_sequence', 'in_refund_sequence'):
                if self.search(cursor, user, [
                    (sequence, '=', period[sequence].id),
                    ('fiscalyear', '!=', period.fiscalyear.id),
                    ]):
                    return False
        return True

    def create(self, cursor, user, vals, context=None):
        fiscalyear_obj = self.pool.get('account.fiscalyear')
        vals = vals.copy()
        if vals.get('fiscalyear'):
            fiscalyear = fiscalyear_obj.browse(cursor, user, vals['fiscalyear'],
                    context=context)
            for sequence in ('out_invoice_sequence', 'in_invoice_sequence',
                    'out_refund_sequence', 'in_refund_sequence'):
                if not vals.get(sequence):
                    vals[sequence] = fiscalyear[sequence].id
        return super(Period, self).create(cursor, user, vals, context=context)

    def write(self, cursor, user, ids, vals, context=None):
        invoice_obj = self.pool.get('account.invoice')

        if isinstance(ids, (int, long)):
            ids = [ids]

        for sequence in ('out_invoice_sequence', 'in_invoice_sequence',
                'out_refund_sequence', 'in_refund_sequence'):
            if vals.get(sequence):
                for period in self.browse(cursor, user, ids, context=context):
                    if period[sequence] and \
                            period[sequence].id != \
                            vals[sequence]:
                        if invoice_obj.search(cursor, user, [
                            ('date', '>=', period.start_date),
                            ('date', '<=', period.end_date),
                            ('number', '!=', False),
                            ('type', '=', sequence[:-9]),
                            ], context=context):
                            self.raise_user_error(cursor,
                                    'change_invoice_sequence', context=context)
        return super(Period, self).write(cursor, user, ids, vals,
                context=context)

Period()


class PayInvoiceInit(WizardOSV):
    _name = 'account.invoice.pay_invoice.init'
    amount = fields.Numeric('Amount', digits=(16, 2), required=True)
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    description = fields.Char('Description', size=None, required=True)
    journal = fields.Many2One('account.journal', 'Journal', required=True,
            domain=[('type', '=', 'cash')])
    date = fields.Date('Date', required=True)

    def default_date(self, cursor, user, context=None):
        return datetime.date.today()

PayInvoiceInit()


class PayInvoiceAsk(WizardOSV):
    _name = 'account.invoice.pay_invoice.ask'
    type = fields.Selection([
        ('writeoff', 'Write-Off'),
        ('partial', 'Partial Payment'),
        ], 'Type', required=True)
    journal_writeoff = fields.Many2One('account.journal', 'Journal',
            states={
                'invisible': "type != 'writeoff'",
                'required': "type == 'writeoff'",
            })
    account_writeoff = fields.Many2One('account.account', 'Account',
            domain="[('kind', '!=', 'view'), ('company', '=', company)]",
            states={
                'invisible': "type != 'writeoff'",
                'required': "type == 'writeoff'",
            })
    amount = fields.Numeric('Amount', digits=(16, 2), readonly=True)
    currency = fields.Many2One('currency.currency', 'Currency', readonly=True)
    lines_to_pay = fields.Char(string='Lines to Pay', size=None)
    lines = fields.One2Many('account.move.line', 'ham', 'Lines',
            domain="[('id', 'in', eval(lines_to_pay)), " \
                    "('reconciliation', '=', False)]",
            states={
                'invisible': "type != 'writeoff'",
            })
    description = fields.Char('Description', size=None, readonly=True)
    journal = fields.Many2One('account.journal', 'Journal', readonly=True,
            domain=[('type', '=', 'cash')])
    date = fields.Date('Date', readonly=True)
    company = fields.Many2One('company.company', 'Company', readonly=True)
    account = fields.Many2One('account.account', 'Account', readonly=True)

    def default_type(self, cursor, user, context=None):
        return 'writeoff'

PayInvoiceAsk()


class PayInvoice(Wizard):
    'Pay Invoice'
    _name = 'account.invoice.pay_invoice'
    states = {
        'init': {
            'actions': ['_init'],
            'result': {
                'type': 'form',
                'object': 'account.invoice.pay_invoice.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('choice', 'Ok', 'tryton-ok', True),
                ],
            },
        },
        'choice': {
            'result': {
                'type': 'choice',
                'next_state': '_choice',
            },
        },
        'ask': {
            'actions': ['_ask'],
            'result': {
                'type': 'form',
                'object': 'account.invoice.pay_invoice.ask',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('pay', 'Ok', 'tryton-ok', True),
                ],
            },
        },
        'pay': {
            'result': {
                'type': 'action',
                'action': '_action_pay',
                'state': 'end',
            },
        },
    }

    def _init(self, cursor, user, data, context=None):
        invoice_obj = self.pool.get('account.invoice')
        res = {}
        invoice = invoice_obj.browse(cursor, user, data['id'], context=context)
        res['currency'] = invoice.currency.id
        res['amount'] = invoice.amount_to_pay_today
        res['description'] = invoice.number
        return res

    def _choice(self, cursor, user, data, context=None):
        invoice_obj = self.pool.get('account.invoice')
        currency_obj = self.pool.get('currency.currency')

        invoice = invoice_obj.browse(cursor, user, data['id'], context=context)

        ctx = context.copy()
        ctx['date'] = data['form']['date']
        amount = currency_obj.compute(cursor, user, data['form']['currency'],
                data['form']['amount'], invoice.company.currency,
                context=context)
        res = invoice_obj.get_reconcile_lines_for_amount(cursor, user, invoice,
                amount)
        if res[1] == Decimal('0.0'):
            return 'pay'
        return 'ask'

    def _ask(self, cursor, user, data, context=None):
        invoice_obj = self.pool.get('account.invoice')
        currency_obj = self.pool.get('currency.currency')

        res = {}
        invoice = invoice_obj.browse(cursor, user, data['id'], context=context)
        res['lines_to_pay'] = str(
                [x.id for x in invoice.lines_to_pay if not x.reconciliation] + \
                [x.id for x in invoice.payment_lines if not x.reconciliation])

        res['amount'] = data['form']['amount']
        res['currency'] = data['form']['currency']
        res['description'] = data['form']['description']
        res['journal'] = data['form']['journal']
        res['date'] = data['form']['date']
        res['company'] = invoice.company.id
        amount = currency_obj.compute(cursor, user, data['form']['currency'],
                data['form']['amount'], invoice.company.currency,
                context=context)
        res['lines'] = invoice_obj.get_reconcile_lines_for_amount(cursor, user, invoice,
                amount)[0]
        return res

    def _action_pay(self, cursor, user, data, context=None):
        invoice_obj = self.pool.get('account.invoice')
        currency_obj = self.pool.get('currency.currency')
        move_line_obj = self.pool.get('account.move.line')

        invoice = invoice_obj.browse(cursor, user, data['id'], context=context)

        ctx = context.copy()
        ctx['date'] = data['form']['date']
        amount = currency_obj.compute(cursor, user, data['form']['currency'],
                data['form']['amount'], invoice.company.currency,
                context=context)

        reconcile_lines = invoice_obj.get_reconcile_lines_for_amount(cursor,
                user, invoice, amount)

        amount_second_currency = False
        second_currency = False
        if data['form']['currency'] != invoice.company.currency.id:
            amount_second_currency = data['form']['amount']
            second_currency = data['form']['currency']

        line_id = invoice_obj.pay_invoice(cursor, user, data['id'], amount,
                data['form']['journal'], data['form']['date'],
                data['form']['description'], amount_second_currency,
                second_currency, context=context)

        if reconcile_lines[1] != Decimal('0.0'):
            if data['form'].get('type') == 'writeoff':
                line_ids = [line_id] + data['form']['lines'][0][1]
                move_line_obj.reconcile(cursor, user, line_ids,
                        journal_id=data['form']['journal_writeoff'],
                        date=data['form']['date'],
                        account_id=data['form']['account_writeoff'],
                        context=context)
        else:
            line_ids = reconcile_lines[0] + [line_id]
            move_line_obj.reconcile(cursor, user, line_ids, context=context)
        return {}

PayInvoice()


class RefundInvoiceInit(WizardOSV):
    _name = 'account.invoice.refund_invoice.init'

RefundInvoiceInit()


class RefundInvoice(Wizard):
    'Refund Invoice'
    _name = 'account.invoice.refund_invoice'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'account.invoice.refund_invoice.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('refund', 'Refund', 'tryton-ok', True),
                ],
            }
        },
        'refund': {
            'result': {
                'type': 'action',
                'action': '_action_refund',
                'state': 'end',
            },
        },
    }

    def _action_refund(self, cursor, user, data, context=None):
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')
        invoice_obj = self.pool.get('account.invoice')

        invoice_ids = invoice_obj.refund(cursor, user, data['ids'],
                context=context)

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_invoice_form'),
            ('module', '=', 'account_invoice'),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id, context=context)
        res['res_id'] = invoice_ids
        if len(invoice_ids) == 1:
            res['views'].reverse()
        return res

RefundInvoice()
