"Invoice"

from trytond.osv import fields, OSV, ExceptORM
import datetime
import mx.DateTime
from decimal import Decimal
from trytond.netsvc import LocalService

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
    _order = 'name, id'
    _description = __doc__
    name = fields.Char('Payment Term', size=None, required=True, translate=True)
    active = fields.Boolean('Active')
    description = fields.Text('Description', translate=True)
    lines = fields.One2Many('account.invoice.payment_term.line', 'payment',
            'Lines')

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
        currency_obj = self.pool.get('account.currency')
        res = []
        if date is None:
            date = datetime.datetime.today()
        remainder = amount
        for line in payment_term.lines:
            value = type_obj.get_value(cursor, user, line, remainder, currency,
                    context)
            value_date = delay_obj.get_date(cursor, user, line, date, context)
            if not value or not value_date:
                raise ExceptORM('Error', 'Invalid payment term line!')
            res.append((value_date, value))
            remainder -= value
        if not currency_obj.is_zero(cursor, user, currency, remainder):
            raise ExceptORM('Error', 'Payment term computation have a remainder!')
        return res

PaymentTerm()


class PaymentTermLineType(OSV):
    'Payment Term Line Type'
    _name = 'account.invoice.payment_term.line.type'
    _order = 'name, id'
    _description = __doc__
    name = fields.Char('Name', size=None, translate=True, required=True)
    code = fields.Char('Code', size=None, required=True)

    def __init__(self):
        super(PaymentTermLineType, self).__init__()
        self._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'Code must be unqiue!'),
        ]

    def get_value(self, cursor, user, line, amount, currency, context=None):
        currency_obj = self.pool.get('account.currency')
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
    _order = 'name, id'
    _description = __doc__
    name = fields.Char('Name', size=None, translate=True, required=True)
    code = fields.Char('Code', size=None, required=True)

    def __init__(self):
        super(PaymentTermLineDelay, self).__init__()
        self._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'Code must be unqiue!'),
        ]

    def get_date(self, cursor, user, line, date, context=None):
        if line.delay == 'net_days':
            return mx.DateTime.strptime(str(date), '%Y-%m-%d') + \
                    mx.DateTime.RelativeDateTime(days=line.days)
        elif line.delay == 'end_month':
            return mx.DateTime.strptime(str(date), '%Y-%m-%d') + \
                    mx.DateTime.RelativeDateTime(days=line.days) + \
                    mx.DateTime.RelativeDateTime(day=-1)
        return None

PaymentTermLineDelay()


class PaymentTermLine(OSV):
    'Payment Term Line'
    _name = 'account.invoice.payment_term.line'
    _order = 'sequence, id'
    _description = __doc__
    sequence = fields.Integer('Sequence', required=True,
            help='Use to order lines in ascending order')
    payment = fields.Many2One('account.invoice.payment_term', 'Payment Term',
            required=True)
    type = fields.Selection('get_type', 'Type', required=True)
    percent = fields.Numeric('Percent', digits=(16, 8),
            states={
                'invisible': "type != 'percent'",
                'required': "type == 'percent'",
            })
    #TODO digits depends of currency
    amount = fields.Numeric('Amount', digits=(16, 2),
            states={
                'invisible': "type != 'fixed'",
                'required': "type == 'fixed'",
            })
    currency = fields.Many2One('account.currency', 'Currency',
            states={
                'invisible': "type != 'fixed'",
                'required': "type == 'fixed'",
            })
    days = fields.Integer('Number of Days', required=True)
    delay = fields.Selection('get_delay', 'Condition', required=True)

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

PaymentTermLine()


class Invoice(OSV):
    'Invoice'
    _name = 'account.invoice'
    _order = 'number, id'
    _rec_name = 'description'
    _description = __doc__
    company = fields.Many2One('company.company', 'Company', required=True,
            states=_STATES)
    type = fields.Selection([
        ('out_invoice', 'Customer Invoice'),
        ('in_invoice', 'Supplier Invoice'),
        ('out_refund', 'Customer Refund'),
        ('in_refund', 'Supplier Refund'),
        ], 'Type', select=1, on_change=['type'], required=True, states=_STATES)
    number = fields.Char('Number', size=None, readonly=True, select=1)
    reference = fields.Char('Reference', size=None)
    description = fields.Char('Description', size=None, required=True,
            states=_STATES)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('proforma', 'Pro forma'),
        ('open', 'Open'),
        ('paid', 'Paid'),
        ('cancel', 'Canceled'),
        ], 'State', readonly=True)
    invoice_date = fields.Date('Invoice Date', required=True,
        states=_STATES)
    partner = fields.Many2One('partner.partner', 'Partner', change_default=True,
        required=True, states=_STATES, on_change=['partner', 'invoice_date',
            'payment_term', 'type'])
    contact_address = fields.Many2One('partner.address', 'Contact Address',
        required=True, states=_STATES)
    invoice_address = fields.Many2One('partner.address', 'Invoice Address',
        required=True, states=_STATES)
    currency = fields.Many2One('account.currency', 'Currency', required=True,
        states=_STATES)
    journal = fields.Many2One('account.journal', 'Journal', required=True,
        states=_STATES, domain=[('centralisation', '=', False)])
    move = fields.Many2One('account.move', 'Move', readonly=True)
    account = fields.Many2One('account.account', 'Account', required=True,
        states=_STATES, domain="[('company', '=', company)]")
    payment_term = fields.Many2One('account.invoice.payment_term',
        'Payment Term', required=True, states=_STATES)
    lines = fields.One2Many('account.invoice.line', 'invoice', 'Lines',
        states=_STATES)
    taxes = fields.One2Many('account.invoice.tax', 'invoice', 'Tax Lines',
        states=_STATES)
    comment = fields.Text('Comment')
    #TODO digits must depend of currency
    untaxed_amount = fields.Function('get_untaxed_amount', type='numeric',
            digits=(16, 2), string='Untaxed')
    tax_amount = fields.Function('get_tax_amount', type='numeric',
            digits=(16, 2), string='Tax')
    total_amount = fields.Function('get_total_amount', type='numeric',
            digits=(16, 2), string='Total')
    reconciled = fields.Function('get_reconciled', type='boolean',
            string='Reconciled')
    payment_lines = fields.Function('get_payment_lines', type='one2many',
            relation='account.move.line', string='Payment Lines')

    def __init__(self):
        super(Invoice, self).__init__()
        self._rpc_allowed += [
            'button_draft',
            'button_compute',
            'button_reset_taxes',
        ]
        self._constraints += [
            ('check_account', 'You can not create an invoice \n' \
                    'with account from a different invoice company!',
                    ['account']),
            ('check_account2', 'You can not use the same account \n' \
                    'than on invoice line account!', ['account']),
        ]

    def default_type(self, cursor, user, context=None):
        if context is None:
            context = {}
        return context.get('type', 'out_invoice')

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def default_invoice_date(self, cursor, user, context=None):
        return datetime.datetime.today()

    def default_currency(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        currency_obj = self.pool.get('account.currency')
        if context is None:
            context = {}
        company = None
        if context.get('company'):
            company = company_obj.browse(cursor, user, context['company'],
                    context=context)
            return currency_obj.name_get(cursor, user, company.currency.id,
                    context=context)[0]
        return False

    def default_company(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        if context is None:
            context = {}
        if context.get('company'):
            return company_obj.name_get(cursor, user, context['company'],
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

    def on_change_partner(self, cursor, user, ids, vals, context=None):
        partner_obj = self.pool.get('partner.partner')
        address_obj = self.pool.get('partner.address')
        account_obj = self.pool.get('account.account')
        payment_term_obj = self.pool.get('account.invoice.payment_term')
        res = {
            'invoice_address': False,
            'contact_address': False,
            'payment_term': False,
            'account': False,
        }
        if vals.get('partner'):
            partner = partner_obj.browse(cursor, user, vals['partner'],
                    context=context)
            res['contact_address'] = partner_obj.address_get(cursor, user,
                    partner.id, type=None, context=context)
            res['invoice_address'] = partner_obj.address_get(cursor, user,
                    partner.id, type='invoice', context=context)
            if vals.get('type') in ('out_invoice', 'out_refund'):
                res['account'] = partner.account_receivable.id
            else:
                res['account'] = partner.account_payable.id
            if partner.payment_term:
                res['payment_term'] = partner.payment_term.id

        if res['contact_address']:
            res['contact_address'] = address_obj.name_get(cursor, user,
                    res['contact_address'], context=context)[0]
        if res['invoice_address']:
            res['invoice_address'] = address_obj.name_get(cursor, user,
                    res['invoice_address'], context=context)[0]
        if res['account']:
            res['account'] = account_obj.name_get(cursor, user,
                    res['account'], context=context)[0]
        if res['payment_term']:
            res['payment_term'] = payment_term_obj.name_get(cursor, user,
                    res['payment_term'], context=context)[0]
        return res

    def get_untaxed_amount(self, cursor, user, ids, name, arg, context=None):
        currency_obj = self.pool.get('account.currency')
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
        currency_obj = self.pool.get('account.currency')
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
        currency_obj = self.pool.get('account.currency')
        res = {}
        for invoice in self.browse(cursor, user, ids, context=context):
            res[invoice.id] = currency_obj.round(cursor, user, invoice.currency,
                    invoice.untaxed_amount + invoice.tax_amount)
        return res

    def get_reconciled(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for invoice in self.browse(cursor, user, ids, context):
            res[invoice.id] = True
            for line in invoice.payment_lines:
                if not line.reconciliation:
                    res[invoice.id] = False
                    break
        return res

    def get_payment_lines(self, cursor, user, ids, name, args, context=None):
        res = {}
        for invoice in self.browse(cursor, user, ids, context=context):
            res[invoice.id] = []
            if invoice.move:
                for line in invoice.move.lines:
                    if line.account.id == invoice.account.id:
                        res[invoice.id].append(line.id)
        return res

    def button_draft(self, cursor, user, ids, context=None):
        workflow_service = LocalService('workflow')
        for invoice in self.browse(cursor, user, ids, context=context):
            if invoice.move:
                raise ExceptORM('Error', 'You can not reset to draft ' \
                        'an invoice that have move!')
            workflow_service.trg_create(user, 'account.invoice',
                    invoice.id, cursor)
        self.write(cursor, user, ids, {'state': 'draft'})
        return True

    def get_tax_context(self, cursor, user, invoice, context=None):
        res = {}
        if invoice.partner.lang:
            res['language'] = invoice.partner.lang.code
        return res

    def _compute_taxes(self, cursor, user, invoice, context=None):
        tax_obj = self.pool.get('account.tax')
        currency_obj = self.pool.get('account.currency')
        if context is None:
            context = {}

        ctx = context.copy()
        ctx.update(self.get_tax_context(cursor, user, invoice,
            context=context))

        res = {}
        for line in invoice.lines:
            if line.type != 'line':
                continue
            tax_ids = [x.id for x in line.taxes]
            for tax in tax_obj.compute(cursor, user, tax_ids, line.unit_price,
                    line.quantity, context=ctx):
                val = {}
                val['manual'] = False
                val['invoice'] = invoice.id
                val['description'] = tax['tax'].name
                val['base'] = tax['base']
                val['amount'] = tax['amount']

                if invoice.type in ('out_invoice', 'in_invoice'):
                    val['base_code'] = tax['tax'].invoice_base_code.id
                    val['base_sign'] = tax['tax'].invoice_base_sign
                    val['tax_code'] = tax['tax'].invoice_tax_code.id
                    val['tax_sign'] = tax['tax'].invoice_tax_sign
                    val['account'] = tax['tax'].invoice_account.id or \
                            line.account.id
                else:
                    val['base_code'] = tax['tax'].refund_base_code.id
                    val['base_sign'] = tax['tax'].refund_base_sign
                    val['tax_code'] = tax['tax'].refund_tax_code.id
                    val['tax_sign'] = tax['tax'].refund_tax_sign
                    val['account'] = tax['tax'].refund_account.id or \
                            line.account.id
                key = (val['base_code'], val['base_sign'],
                        val['tax_code'], val['tax_sign'],
                        val['account'], val['description'])
                if not key in res:
                    res[key] = val
                else:
                    res[key]['base'] += val['base']
                    res[key]['amount'] += val['amount']
        return res

    def button_compute(self, cursor, user, ids, context=None, exception=False):
        tax_obj = self.pool.get('account.invoice.tax')
        currency_obj = self.pool.get('account.currency')
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
                            raise ExceptORM('Warning', 'Taxes defined ' \
                                    'but not in invoice lines!\n' \
                                    'Re-compute the invoice.')
                        tax_obj.unlink(cursor, user, tax.id,
                                context=context)
                        continue
                    if not currency_obj.is_zero(cursor, user,
                            invoice.currency,
                            computed_taxes[key]['base'] - tax.base):
                        if exception:
                            raise ExceptORM('Warning', 'Base taxes ' \
                                    'different from invoice lines!\n' \
                                    'Re-compute the invoice.')
                        tax_obj.write(cursor, user, tax.id,
                                computed_taxes[key], context=context)
                for key in computed_taxes:
                    if not key in tax_keys:
                        if exception:
                            raise ExceptORM('Warning', 'Taxes defined ' \
                                    'on invoice lines but not on invoice!\n' \
                                    'Re-compute the invoice.')
                        tax_obj.create(cursor, user, computed_taxes[key],
                                context=context)
        return True

    def button_reset_taxes(self, cursor, user, ids, context=None):
        tax_obj = self.pool.get('account.invoice.tax')
        for invoice in self.browse(cursor, user, ids, context=context):
            if invoice.taxes:
                tax_obj.unlink(cursor, user, [x.id for x in invoice.taxes],
                        context=context)
            computed_taxes = self._compute_taxes(cursor, user, invoice,
                    context=context)
            for tax in computed_taxes.values():
                tax_obj.create(cursor, user, tax, context=context)
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
        res = {}
        if invoice.currency.id != invoice.company.currency.id:
            res['amount_second_currency'] = currency_obj.compute(cursor, user,
                    invoice.company.currency, amount,
                    invoice.currency, context=context)
            res['second_currency'] = invoice.currency.id
        else:
            res['amount_second_currency'] = Decimal('0.0')
            res['second_currency'] = False
        if amount >= Decimal('0.0'):
            res['debit'] = Decimal('0.0')
            res['credit'] = amount
            res['amount_second_currency'] = - res['amount_second_currency']
        else:
            res['debit'] = - amount
            res['credit'] = Decimal('0.0')
        res['account'] = invoice.account.id
        res['maturity_date'] = date
        res['reference'] = invoice.reference
        res['description'] = invoice.description
        return res

    def create_move(self, cursor, user, invoice_id, context=None):
        tax_obj = self.pool.get('account.invoice.tax')
        payment_term_obj = self.pool.get('account.invoice.payment_term')
        currency_obj = self.pool.get('account.currency')
        move_obj = self.pool.get('account.move')
        period_obj = self.pool.get('account.period')

        invoice = self.browse(cursor, user, invoice_id, context=context)
        if invoice.move:
            return True
        self.button_compute(cursor, user, [invoice.id], context=context,
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

        period_id = period_obj.find(cursor, user, date=invoice.invoice_date,
                context=context)

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
        return True

    def set_number(self, cursor, user, invoice_id, context=None):
        period_obj = self.pool.get('account.period')
        sequence_obj = self.pool.get('ir.sequence')

        invoice = self.browse(cursor, user, invoice_id, context=context)

        if invoice.number:
            return True

        period_id = period_obj.find(cursor, user, date=invoice.invoice_date,
                context=context)
        period = period_obj.browse(cursor, user, period_id, context=context)
        sequence_id = period[invoice.type + '_sequence'].id
        number = sequence_obj.get_id(cursor, user, sequence_id)
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
                raise ExceptORM('UserError',
                        'You can not modify invoice that is ' \
                                'open, paid or canceled!')
        return

    def unlink(self, cursor, user, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.check_modify(cursor, user, ids, context=context)
        return super(Invoice, self).unlink(cursor, user, ids,
                context=context)

    def write(self, cursor, user, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        keys = vals.keys()
        for key in ('state',):
            if key in keys:
                keys.remove(key)
        if len(keys):
            self.check_modify(cursor, user, ids, context=context)
        return super(Invoice, self).write(cursor, user, ids, vals,
                context=context)

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

Invoice()


class InvoiceLine(OSV):
    'Invoice Line'
    _name = 'account.invoice.line'
    _order = 'sequence, id'
    _rec_name = 'description'
    _description = __doc__

    invoice = fields.Many2One('account.invoice', 'Invoice', ondelete='CASCADE',
            select=1)
    sequence = fields.Integer('Sequence')
    type = fields.Selection([
        ('line', 'Line'),
        ('subtotal', 'Subtotal'),
        ('title', 'Title'),
        ], 'Type', select=1, required=True)
    quantity = fields.Float('Quantity',
            states={
                'invisible': "type != 'line'",
                'required': "type == 'line'",
            })
    unit = fields.Many2One('product.uom', 'Unit',
            states={
                'required': "product",
                'invisible': "type != 'line'",
            }, domain="[('category', '=', (product, 'product'))]")
    product = fields.Many2One('product.product', 'Product',
            states={
                'invisible': "type != 'line'",
            }, on_change=['product', 'unit', 'quantity', 'description',
                'parent.type', 'parent.partner', 'parent.currency'])
    account = fields.Many2One('account.account', 'Account',
            domain="[('type.code', '!=', 'view'), " \
                    "('company', '=', parent.company), " \
                    "('id', '!=', parent.account)]",
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
            states={
                'invisible': "type not in ('line', 'subtotal')",
            })
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
            ('check_account', 'You can not create invoice line \n' \
                    'with account from a different invoice company!',
                    ['account']),
            ('check_account2', 'You can not use the same account \n' \
                    'than the invoice account!', ['account']),
        ]

    def default_type(self, cursor, user, context=None):
        return 'line'

    def default_quantity(self, cursor, user, context=None):
        return 0.0

    def default_unit_price(self, cursor, user, context=None):
        return Decimal('0.0')

    def get_amount(self, cursor, user, ids, name, arg, context=None):
        currency_obj = self.pool.get('account.currency')
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
        partner_obj = self.pool.get('partner.partner')
        account_obj = self.pool.get('account.account')
        uom_obj = self.pool.get('product.uom')
        company_obj = self.pool.get('company.company')
        currency_obj = self.pool.get('account.currency')
        if context is None:
            context = {}
        if not vals.get('product'):
            return {}
        res = {}

        ctx = context.copy()
        partner = None
        if vals.get('parent.partner'):
            partner = partner_obj.browse(cursor, user, vals['parent.partner'],
                    context=context)
            if partner.lang:
                ctx['language'] = partner.lang.code

        product = product_obj.browse(cursor, user, vals['product'],
                context=context)

        company = None
        if context.get('company'):
            company = company_obj.browse(cursor, user, context['company'],
                    context=context)
        currency = None
        if vals.get('parent.currency'):
            #TODO check if today date is correct
            currency = currency_obj.browse(cursor, user,
                    vals['parent.currency'], context=context)

        if vals.get('parent.type') in ('in_invoice', 'in_refund'):
            if company and currency:
                res['unit_price'] = currency_obj.compute(cursor, user,
                        company.currency, product.cost_price, currency,
                        round=False, context=context)
            else:
                res['unit_price'] = product.cost_price
            res['account'] = account_obj.name_get(cursor, user,
                    product.account_expense_used.id, context=context)[0]
            res['taxes'] = []
            for tax in product.supplier_taxes:
                if partner:
                    if partner.get(tax.group.code):
                        res['taxes'].append(partner.get(tax.group.code).id)
                        continue
                res['taxes'].append(tax.id)
        else:
            if company and currency:
                res['unit_price'] = currency_obj.compute(cursor, user,
                        company.currency, product.list_price, currency,
                        round=False, context=context)
            else:
                res['unit_price'] = product.list_price
            res['account'] = account_obj.name_get(cursor, user,
                    product.account_revenue_used.id, context=context)[0]
            res['taxes'] = []
            for tax in product.customer_taxes:
                if partner:
                    if tax.group.code in partner_obj._columns:
                        res['taxes'].append(partner[tax.group.code].id)
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
        return res

    def check_modify(self, cursor, user, ids, context=None):
        '''
        Check if the lines can be modified
        '''
        for line in self.browse(cursor, user, ids, context=context):
            if line.invoice.state in ('open', 'paid', 'cancel'):
                raise ExceptORM('UserError',
                        'You can not modify line from an invoice ' \
                                'that is open, paid or canceled!')
        return

    def unlink(self, cursor, user, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.check_modify(cursor, user, ids, context=context)
        return super(InvoiceLine, self).unlink(cursor, user, ids,
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
                raise ExceptORM('UserError',
                        'You can not add a line to an invoice ' \
                                'that is open, paid or canceled!')
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
        currency_obj = self.pool.get('account.currency')
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
        currency_obj = self.pool.get('account.currency')
        res = {}
        if line.type != 'line':
            return res
        res['description'] = line.description
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
        computed_taxes = self._compute_taxes(cursor, user, line,
                context=context)
        for tax in computed_taxes:
            res.setdefault('tax_lines', [])
            res.tax_lines.append(('create', tax))
        return res

InvoiceLine()


class InvoiceTax(OSV):
    'Invoice Tax'
    _name = 'account.invoice.tax'
    _order = 'sequence, id'
    _rec_name = 'description'
    _description = __doc__

    invoice = fields.Many2One('account.invoice', 'Invoice', ondelete='CASCADE',
            select=1)
    description = fields.Char('Description', size=None, required=True)
    sequence = fields.Integer('Sequence')
    account = fields.Many2One('account.account', 'Account', required=True,
            domain="[('type.code', '!=', 'view'), " \
                "('company', '=', parent.company)]")
    base = fields.Numeric('Base', digits=(16, 2),
            states={
                'invisible': "manual",
            })
    amount = fields.Numeric('Amount', digits=(16, 2))
    manual = fields.Boolean('Manual')
    base_code = fields.Many2One('account.tax.code', 'Base Code',
            domain="[('company', '=', parent.company)]",
            states={
                'invisible': "manual",
            })
    base_sign = fields.Numeric('Base Sign', digits=(2, 0),
            states={
                'invisible': "manual",
            })
    tax_code = fields.Many2One('account.tax.code', 'Tax Code',
            domain="[('company', '=', parent.company)]")
    tax_sign = fields.Numeric('Tax Sign', digits=(2, 0))

    def __init__(self):
        super(InvoiceTax, self).__init__()
        self._constraints += [
            ('check_company', 'You can not create invoice tax \n' \
                    'with account or code from a different invoice company!',
                    ['account', 'base_code', 'tax_code']),
        ]

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
                raise ExceptORM('UserError',
                        'You can not modify tax from an invoice ' \
                                'that is open, paid or canceled!')
        return

    def unlink(self, cursor, user, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.check_modify(cursor, user, ids, context=context)
        return super(InvoiceTax, self).unlink(cursor, user, ids,
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
                raise ExceptORM('UserError',
                        'You can not add a line to an invoice ' \
                                'that is open, paid or canceled!')
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
        currency_obj = self.pool.get('account.currency')
        res = {}
        res['description'] = tax.description
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
        if tax.tax_code:
            res['tax_lines'] = [('create', {
                'code': tax.tax_code.id,
                'amount': tax.amount * tax.tax_sign,
            })]
        return res

InvoiceTax()


class Address(OSV):
    _name = 'partner.address'
    invoice = fields.Boolean('Invoice')

Address()


class Partner(OSV):
    _name = 'partner.partner'
    payment_term = fields.Property(type='many2one',
            relation='account.invoice.payment_term',
            string='Invoice Payment Term', group_name='Accounting Properties',
            view_load=True)

Partner()


class Category(OSV):
    _name = 'product.category'
    account_expense = fields.Property(type='many2one',
            relation='account.account', string='Account Expence',
            group_name='Accounting Properties', view_load=True,
            domain="[('type.code', '=', 'expense'), ('company', '=', company)]",
            states={
                'invisible': "not company",
            })
    account_revenue = fields.Property(type='many2one',
            relation='account.account', string='Account Revenue',
            group_name='Accounting Properties', view_load=True,
            domain="[('type.code', '=', 'revenue'), ('company', '=', company)]",
            states={
                'invisible': "not company",
            })

Category()


class Template(OSV):
    _name = 'product.template'
    account_expense = fields.Property(type='many2one',
            string='Account Expence', group_name='Accounting Properties',
            view_load=True, relation='account.account',
            domain="[('type.code', '=', 'expense'), ('company', '=', company)]",
            states={
                'invisible': "not company",
            }, help='This account will be used instead of the one defined ' \
                    'on the category.')
    account_revenue = fields.Property(type='many2one',
            string='Account Revenue', group_name='Accounting Properties',
            view_load=True, relation='account.account',
            domain="[('type.code', '=', 'revenue'), ('company', '=', company)]",
            states={
                'invisible': "not company",
            }, help='This account will be used instead of the one defined ' \
                    'on the category.')
    account_expense_used = fields.Function('get_account', type='many2one',
            relation='account.account', string='Account Expence Used')
    account_revenue_used = fields.Function('get_account', type='many2one',
            relation='account.account', string='Account Revenue Used')
    customer_taxes = fields.Many2Many('account.tax',
            'product_customer_taxes_rel', 'product', 'tax',
            'Customer Taxes', domain=[('parent', '=', False)])
    supplier_taxes = fields.Many2Many('account.tax',
            'product_supplier_taxes_rel', 'product', 'tax',
            'Supplier Taxes', domain=[('parent', '=', False)])

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
                    raise ExceptORM('Error', 'There is no account ' \
                            'expense/revenue define on the product ' \
                            '%s (%d)' % (product.name, product.id))
        return res

Template()


class Uom(OSV):
    _name = 'product.uom'

    def search(self, cursor, user, args, offset=0, limit=None, order=None,
            context=None, count=False, query_string=False):
        product_obj = self.pool.get('product.product')
        args = args[:]
        i = 0
        while i < len(args):
            if args[i][0] == 'category':
                if isinstance(args[i][2], (list, tuple)) \
                        and len(args[i][2]) == 2:
                    if args[i][2][1] == 'product':
                        if not args[i][2][0]:
                            args[i] = ('id', '!=', '0')
                        else:
                            product = product_obj.browse(cursor, user,
                                    args[i][2][0], context=context)
                            category_id = product.default_uom.category.id
                            args[i] = (args[i][0], args[i][1], category_id)
            i += 1
        return super(Uom, self).search(cursor, user, args, offset=offset,
                limit=limit, order=order, context=context, count=count,
                query_string=query_string)

Uom()


class FiscalYear(OSV):
    _name = 'account.fiscalyear'
    out_invoice_sequence = fields.Many2One('ir.sequence',
            'Customer Invoice Sequence', required=True,
            domain="[('code', '=', 'account.invoice.out_invoice')]")
    in_invoice_sequence = fields.Many2One('ir.sequence',
            'Supplier Invoice Sequence', required=True,
            domain="[('code', '=', 'account.invoice.in_invoice')]")
    out_refund_sequence = fields.Many2One('ir.sequence',
            'Customer Refund Sequence', required=True,
            domain="[('code', '=', 'account.invoice.out_refund')]")
    in_refund_sequence = fields.Many2One('ir.sequence',
            'Supplier Refund Sequence', required=True,
            domain="[('code', '=', 'account.invoice.in_refund')]")

    def __init__(self):
        super(FiscalYear, self).__init__()
        self._constraints += [
            ('check_invoice_sequences',
                'Error! You must have different invoice sequence ' \
                        'per fiscal year!', ['out_invoice_sequence',
                            'in_invoice_sequence', 'out_refund_sequence',
                            'in_refund_sequence']),
        ]

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
                            ('date', '>=', fiscalyear.start_date),
                            ('date', '<=', fiscalyear.end_date),
                            ('number', '!=', False),
                            ('type', '=', sequence[:-9]),
                            ], context=context):
                            raise ExceptORM('UserError', 'You can not change ' \
                                    'the invoice sequence if there is already ' \
                                    'an invoice opened in the fiscalyear')
        return super(FiscalYear, self).write(cursor, user, ids, vals,
                context=context)

FiscalYear()


class Period(OSV):
    _name = 'account.period'
    out_invoice_sequence = fields.Many2One('ir.sequence',
            'Customer Invoice Sequence', required=True,
            domain="[('code', '=', 'account.invoice.out_invoice')]")
    in_invoice_sequence = fields.Many2One('ir.sequence',
            'Supplier Invoice Sequence', required=True,
            domain="[('code', '=', 'account.invoice.in_invoice')]")
    out_refund_sequence = fields.Many2One('ir.sequence',
            'Customer Refund Sequence', required=True,
            domain="[('code', '=', 'account.invoice.out_refund')]")
    in_refund_sequence = fields.Many2One('ir.sequence',
            'Supplier Refund Sequence', required=True,
            domain="[('code', '=', 'account.invoice.in_refund')]")

    def __init__(self):
        super(Period, self).__init__()
        self._constraints += [
            ('check_invoice_sequences',
                'Error! You must have different invoice sequences ' \
                        'per fiscal year!', ['out_invoice_sequence',
                            'in_invoice_sequence', 'out_refund_sequence',
                            'in_refund_sequence']),
        ]

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
                            raise ExceptORM('UserError', 'You can not change ' \
                                    'the invoice sequence if there is already ' \
                                    'an invoice opened in the period')
        return super(Period, self).write(cursor, user, ids, vals,
                context=context)

Period()
