#This file is part of Tryton.  The COPYRIGHT file at the top level
#of this repository contains the full copyright notices and license terms.
"Purchase"
from trytond.model import ModelWorkflow, ModelView, ModelSQL, fields
from trytond.modules.company import CompanyReport
from trytond.wizard import Wizard
from trytond.backend import TableHandler
from decimal import Decimal
import datetime
import copy

_STATES = {
    'readonly': "state != 'draft'",
}


class Purchase(ModelWorkflow, ModelSQL, ModelView):
    'Purchase'
    _name = 'purchase.purchase'
    _description = __doc__

    company = fields.Many2One('company.company', 'Company', required=True,
            states={
                'readonly': "state != 'draft' or bool(lines)",
            }, domain=["('id', 'company' in context and '=' or '!=', " \
                    "context.get('company', 0))"])
    reference = fields.Char('Reference', size=None, readonly=True, select=1)
    supplier_reference = fields.Char('Supplier Reference', select=1)
    description = fields.Char('Description', size=None, states=_STATES)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('quotation', 'Quotation'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancel', 'Canceled'),
    ], 'State', readonly=True, required=True)
    purchase_date = fields.Date('Purchase Date', required=True, states=_STATES)
    payment_term = fields.Many2One('account.invoice.payment_term',
        'Payment Term', required=True, states=_STATES)
    party = fields.Many2One('party.party', 'Party', change_default=True,
            required=True, states=_STATES, on_change=['party', 'payment_term'],
            select=1)
    party_lang = fields.Function('get_function_fields', type='char',
            string='Party Language', on_change_with=['party'])
    invoice_address = fields.Many2One('party.address', 'Invoice Address',
            domain=["('party', '=', party)"], states=_STATES)
    warehouse = fields.Many2One('stock.location', 'Warehouse',
            domain=[('type', '=', 'warehouse')], required=True, states=_STATES)
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states={
            'readonly': "state != 'draft' or (bool(lines) and bool(currency))",
        })
    currency_digits = fields.Function('get_function_fields', type='integer',
            string='Currency Digits', on_change_with=['currency'])
    lines = fields.One2Many('purchase.line', 'purchase', 'Lines',
            states=_STATES, on_change=['lines', 'currency', 'party'])
    comment = fields.Text('Comment')
    untaxed_amount = fields.Function('get_function_fields', type='numeric',
            digits="(16, currency_digits)", string='Untaxed')
    tax_amount = fields.Function('get_function_fields', type='numeric',
            digits="(16, currency_digits)", string='Tax')
    total_amount = fields.Function('get_function_fields', type='numeric',
            digits="(16, currency_digits)", string='Total')
    invoice_method = fields.Selection([
        ('manual', 'Manual'),
        ('order', 'Based On Order'),
        ('shipment', 'Based On Shipment'),
    ], 'Invoice Method', required=True, states=_STATES)
    invoice_state = fields.Selection([
        ('none', 'None'),
        ('waiting', 'Waiting'),
        ('paid', 'Paid'),
        ('exception', 'Exception'),
    ], 'Invoice State', readonly=True, required=True)
    invoices = fields.Many2Many('purchase.purchase-account.invoice',
            'purchase', 'invoice', 'Invoices', readonly=True)
    invoices_ignored = fields.Many2Many(
            'purchase.purchase-ignored-account.invoice',
            'purchase', 'invoice', 'Ignored Invoices', readonly=True)
    invoices_recreated = fields.Many2Many(
            'purchase.purchase-recreated-account.invoice',
            'purchase', 'invoice', 'Recreated Invoices', readonly=True)
    invoice_paid = fields.Function('get_function_fields', type='boolean',
            string='Invoices Paid')
    invoice_exception = fields.Function('get_function_fields', type='boolean',
            string='Invoices Exception')
    shipment_state = fields.Selection([
        ('none', 'None'),
        ('waiting', 'Waiting'),
        ('received', 'Received'),
        ('exception', 'Exception'),
    ], 'Shipment State', readonly=True, required=True)
    shipments = fields.Function('get_function_fields', type='many2many',
            relation='stock.shipment.in', string='Shipments')
    moves = fields.Function('get_function_fields', type='many2many',
            relation='stock.move', string='Moves')
    shipment_done = fields.Function('get_function_fields', type='boolean',
            string='Shipment Done')
    shipment_exception = fields.Function('get_function_fields', type='boolean',
            string='Shipments Exception')

    def __init__(self):
        super(Purchase, self).__init__()
        self._order.insert(0, ('purchase_date', 'DESC'))
        self._order.insert(1, ('id', 'DESC'))
        self._error_messages.update({
                'invoice_addresse_required': 'Invoice addresses must be '
                'defined for the quotation.',
                'missing_account_payable': 'It misses ' \
                        'an "Account Payable" on the party "%s"!',
            })

    def init(self, cursor, module_name):
        # Migration from 1.2: packing renamed into shipment
        cursor.execute("UPDATE ir_model_data "\
                "SET fs_id = REPLACE(fs_id, 'packing', 'shipment') "\
                "WHERE fs_id like '%%packing%%' AND module = %s",
                (module_name,))
        cursor.execute("UPDATE ir_model_field "\
                "SET relation = REPLACE(relation, 'packing', 'shipment'), "\
                    "name = REPLACE(name, 'packing', 'shipment') "
                "WHERE (relation like '%%packing%%' "\
                    "OR name like '%%packing%%') AND module = %s",
                (module_name,))
        table = TableHandler(cursor, self, module_name)
        table.column_rename('packing_state', 'shipment_state')

        super(Purchase, self).init(cursor, module_name)

        # Migration from 1.2: rename packing to shipment in
        # invoice_method values
        cursor.execute("UPDATE " + self._table + " "\
                "SET invoice_method = 'shipment' "\
                "WHERE invoice_method = 'packing'")

    def default_payment_term(self, cursor, user, context=None):
        payment_term_obj = self.pool.get('account.invoice.payment_term')
        payment_term_ids = payment_term_obj.search(cursor, user,
                self.payment_term.domain, context=context)
        if len(payment_term_ids) == 1:
            return payment_term_ids[0]
        return False

    def default_warehouse(self, cursor, user, context=None):
        location_obj = self.pool.get('stock.location')
        location_ids = location_obj.search(cursor, user,
                self.warehouse.domain, context=context)
        if len(location_ids) == 1:
            return location_ids[0]
        return False

    def default_company(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        if context is None:
            context = {}
        if context.get('company'):
            return context['company']
        return False

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def default_purchase_date(self, cursor, user, context=None):
        date_obj = self.pool.get('ir.date')
        return date_obj.today(cursor, user, context=context)

    def default_currency(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        currency_obj = self.pool.get('currency.currency')
        if context is None:
            context = {}
        company = None
        if context.get('company'):
            company = company_obj.browse(cursor, user, context['company'],
                    context=context)
            return company.currency.id
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

    def default_invoice_method(self, cursor, user, context=None):
        return 'order'

    def default_invoice_state(self, cursor, user, context=None):
        return 'none'

    def default_shipment_state(self, cursor, user, context=None):
        return 'none'

    def on_change_party(self, cursor, user, ids, vals, context=None):
        party_obj = self.pool.get('party.party')
        address_obj = self.pool.get('party.address')
        payment_term_obj = self.pool.get('account.invoice.payment_term')
        res = {
            'invoice_address': False,
            'payment_term': False,
        }
        if vals.get('party'):
            party = party_obj.browse(cursor, user, vals['party'],
                    context=context)
            res['invoice_address'] = party_obj.address_get(cursor, user,
                    party.id, type='invoice', context=context)
            if party.supplier_payment_term:
                res['payment_term'] = party.supplier_payment_term.id

        if res['invoice_address']:
            res['invoice_address.rec_name'] = address_obj.browse(cursor, user,
                    res['invoice_address'], context=context).rec_name
        if not res['payment_term']:
            res['payment_term'] = self.default_payment_term(cursor, user,
                    context=context)
        if res['payment_term']:
            res['payment_term.rec_name'] = payment_term_obj.browse(cursor, user,
                    res['payment_term'], context=context).rec_name
        return res

    def on_change_with_currency_digits(self, cursor, user, ids, vals,
            context=None):
        currency_obj = self.pool.get('currency.currency')
        if vals.get('currency'):
            currency = currency_obj.browse(cursor, user, vals['currency'],
                    context=context)
            return currency.digits
        return 2

    def get_currency_digits(self, cursor, user, purchases, context=None):
        '''
        Return the number of digits of the currency for each purchases

        :param cursor: the database cursor
        :param user: the user id
        :param purchases: a BrowseRecordList of purchases
        :param context: the context
        :return: a dictionary with purchase id as key and
            number of digits as value
        '''
        res = {}
        for purchase in purchases:
            res[purchase.id] = purchase.currency.digits
        return res

    def on_change_with_party_lang(self, cursor, user, ids, vals,
            context=None):
        party_obj = self.pool.get('party.party')
        if vals.get('party'):
            party = party_obj.browse(cursor, user, vals['party'],
                    context=context)
            if party.lang:
                return party.lang.code
        return 'en_US'

    def get_tax_context(self, cursor, user, purchase, context=None):
        party_obj = self.pool.get('party.party')
        res = {}
        if isinstance(purchase, dict):
            if purchase.get('party'):
                party = party_obj.browse(cursor, user, purchase['party'],
                        context=context)
                if party.lang:
                    res['language'] = party.lang.code
        else:
            if purchase.party.lang:
                res['language'] = purchase.party.lang.code
        return res

    def on_change_lines(self, cursor, user, ids, vals, context=None):
        currency_obj = self.pool.get('currency.currency')
        tax_obj = self.pool.get('account.tax')
        invoice_obj = self.pool.get('account.invoice')

        if context is None:
            context = {}
        res = {
            'untaxed_amount': Decimal('0.0'),
            'tax_amount': Decimal('0.0'),
            'total_amount': Decimal('0.0'),
        }
        currency = None
        if vals.get('currency'):
            currency = currency_obj.browse(cursor, user, vals['currency'],
                    context=context)
        if vals.get('lines'):
            ctx = context.copy()
            ctx.update(self.get_tax_context(cursor, user, vals,
                context=context))
            taxes = {}
            for line in vals['lines']:
                if line.get('type', 'line') != 'line':
                    continue
                res['untaxed_amount'] += line.get('amount', Decimal('0.0'))

                for tax in tax_obj.compute(cursor, user, line.get('taxes', []),
                        line.get('unit_price', Decimal('0.0')),
                        line.get('quantity', 0.0), context=ctx):
                    key, val = invoice_obj._compute_tax(cursor, user, tax,
                            'in_invoice', context=context)
                    if not key in taxes:
                        taxes[key] = val['amount']
                    else:
                        taxes[key] += val['amount']
            if currency:
                for key in taxes:
                    res['tax_amount'] += currency_obj.round(cursor, user,
                            currency, taxes[key])
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

    def get_function_fields(self, cursor, user, ids, names, args, context=None):
        '''
        Function to compute function fields for purchase ids.

        :param cursor: the database cursor
        :param user: the user id
        :param ids: the ids of the purchases
        :param names: the list of field name to compute
        :param args: optional argument
        :param context: the context
        :return: a dictionary with all field names as key and
            a dictionary as value with id as key
        '''
        res = {}
        purchases = self.browse(cursor, user, ids, context=context)
        if 'currency_digits' in names:
            res['currency_digits'] = self.get_currency_digits(cursor, user,
                    purchases, context=context)
        if 'party_lang' in names:
            res['party_lang'] = self.get_party_lang(cursor, user, purchases,
                    context=context)
        if 'untaxed_amount' in names:
            res['untaxed_amount'] = self.get_untaxed_amount(cursor, user,
                    purchases, context=context)
        if 'tax_amount' in names:
            res['tax_amount'] = self.get_tax_amount(cursor, user, purchases,
                    context=context)
        if 'total_amount' in names:
            res['total_amount'] = self.get_total_amount(cursor, user,
                    purchases, context=context)
        if 'invoice_paid' in names:
            res['invoice_paid'] = self.get_invoice_paid(cursor, user,
                    purchases, context=context)
        if 'invoice_exception' in names:
            res['invoice_exception'] = self.get_invoice_exception(cursor, user,
                    purchases, context=context)
        if 'shipments' in names:
            res['shipments'] = self.get_shipments(cursor, user, purchases,
                    context=context)
        if 'moves' in names:
            res['moves'] = self.get_moves(cursor, user, purchases,
                    context=context)
        if 'shipment_done' in names:
            res['shipment_done'] = self.get_shipment_done(cursor, user,
                    purchases, context=context)
        if 'shipment_exception' in names:
            res['shipment_exception'] = self.get_shipment_exception(cursor,
                    user, purchases, context=context)
        return res

    def get_party_lang(self, cursor, user, purchases, context=None):
        '''
        Return the language code of the party of each purchases

        :param cursor: the database cursor
        :param user: the user id
        :param purchases: a BrowseRecordList of purchases
        :param context: the context
        :return: a dictionary with purchase id as key and
            a language code as value
        '''
        res = {}
        for purchase in purchases:
            if purchase.party.lang:
                res[purchase.id] = purchase.party.lang.code
            else:
                res[purchase.id] = 'en_US'
        return res

    def get_untaxed_amount(self, cursor, user, purchases, context=None):
        '''
        Return the untaxed amount for each purchases

        :param cursor: the database cursor
        :param user: the user id
        :param purchases: a BrowseRecordList of purchases
        :param context: the context
        :return: a dictionary with purchase id as key and
            the untaxed amount as value
        '''
        currency_obj = self.pool.get('currency.currency')
        res = {}
        for purchase in purchases:
            res.setdefault(purchase.id, Decimal('0.0'))
            for line in purchase.lines:
                if line.type != 'line':
                    continue
                res[purchase.id] += line.amount
            res[purchase.id] = currency_obj.round(cursor, user, purchase.currency,
                    res[purchase.id])
        return res

    def get_tax_amount(self, cursor, user, purchases, context=None):
        '''
        Return the tax amount for each purchases

        :param cursor: the database cursor
        :param user: the user id
        :param purchases: a BrowseRecordList of purchases
        :param context: the context
        :return: a dictionary with purchase id as key and
            the tax amount as value
        '''
        currency_obj = self.pool.get('currency.currency')
        tax_obj = self.pool.get('account.tax')
        invoice_obj = self.pool.get('account.invoice')

        if context is None:
            context = {}
        res = {}
        for purchase in purchases:
            ctx = context.copy()
            ctx.update(self.get_tax_context(cursor, user,
                purchase, context=context))
            res.setdefault(purchase.id, Decimal('0.0'))
            taxes = {}
            for line in purchase.lines:
                if line.type != 'line':
                    continue
                # Don't round on each line to handle rounding error
                for tax in tax_obj.compute(
                    cursor, user, [t.id for t in line.taxes], line.unit_price,
                    line.quantity, context=ctx):
                    key, val = invoice_obj._compute_tax(cursor, user, tax,
                            'in_invoice', context=context)
                    if not key in taxes:
                        taxes[key] = val['amount']
                    else:
                        taxes[key] += val['amount']
            for key in taxes:
                res[purchase.id] += currency_obj.round(cursor, user,
                        purchase.currency, taxes[key])
            res[purchase.id] = currency_obj.round(cursor, user, purchase.currency,
                    res[purchase.id])
        return res

    def get_total_amount(self, cursor, user, purchases, context=None):
        '''
        Return the total amount of each purchases

        :param cursor: the database cursor
        :param user: the user id
        :param purchases: a BrowseRecordList of purchases
        :param context: the context
        :return: a dictionary with purchase id as key and
            total amount as value
        '''
        currency_obj = self.pool.get('currency.currency')
        res = {}
        untaxed_amounts = self.get_untaxed_amount(cursor, user, purchases,
                context=context)
        tax_amounts = self.get_tax_amount(cursor, user, purchases,
                context=context)
        for purchase in purchases:
            res[purchase.id] = currency_obj.round(cursor, user, purchase.currency,
                    untaxed_amounts[purchase.id] + tax_amounts[purchase.id])
        return res

    def get_invoice_paid(self, cursor, user, purchases, context=None):
        '''
        Return if all invoices have been paid for each purchases

        :param cursor: the database cursor
        :param user: the user id
        :param purchases: a BrowseRecordList of purchases
        :param context: the context
        :return: a dictionary with purchase id as key and
            a boolean as value
        '''
        res = {}
        for purchase in purchases:
            val = True
            ignored_ids = set(x.id for x in purchase.invoices_ignored + \
                                  purchase.invoices_recreated)
            for invoice in purchase.invoices:
                if invoice.state != 'paid' \
                        and invoice.id not in ignored_ids:
                    val = False
                    break
            res[purchase.id] = val
        return res

    def get_invoice_exception(self, cursor, user, purchases, context=None):
        '''
        Return if there is an invoice exception for each purchases

        :param cursor: the database cursor
        :param user: the user id
        :param purchases: a BrowseRecordList of purchases
        :param context: the context
        :return: a dictionary with purchase id as key and
            a boolean as value
        '''
        res = {}
        for purchase in purchases:
            val = False
            skip_ids = set(x.id for x in purchase.invoices_ignored)
            skip_ids.update(x.id for x in purchase.invoices_recreated)
            for invoice in purchase.invoices:
                if invoice.state == 'cancel' \
                        and invoice.id not in skip_ids:
                    val = True
                    break
            res[purchase.id] = val
        return res

    def get_shipments(self, cursor, user, purchases, context=None):
        '''
        Return the shipments for the purchases.

        :param cursor: the database cursor
        :param user: the user id
        :param purchases: a BrowseRecordList of purchases
        :param context: the context
        :return: a dictionary with purchase id as key and
            a list of shipment_in id as value
        '''
        res = {}
        for purchase in purchases:
            res[purchase.id] = []
            for line in purchase.lines:
                for move in line.moves:
                    if move.shipment_in:
                        if move.shipment_in.id not in res[purchase.id]:
                            res[purchase.id].append(move.shipment_in.id)
        return res

    def get_moves(self, cursor, user, purchases, context=None):
        '''
        Return the moves for the purchases.

        :param cursor: the database cursor
        :param user: the user id
        :param purchases: a BrowseRecordList of purchases
        :param context: the context
        :return: a dictionary with purchase id as key and
            a list of moves id as value
        '''
        res = {}
        for purchase in purchases:
            res[purchase.id] = []
            for line in purchase.lines:
                res[purchase.id].extend([x.id for x in line.moves])
        return res

    def get_shipment_done(self, cursor, user, purchases, context=None):
        '''
        Return if all the move have been done for the purchases

        :param cursor: the database cursor
        :param user: the user id
        :param purchases: a BrowseRecordList of purchases
        :param context: the context
        :return: a dictionary with purchase id as key and
            a boolean as value
        '''
        res = {}
        for purchase in purchases:
            val = True
            for line in purchase.lines:
                if not line.move_done:
                    val = False
                    break
            res[purchase.id] = val
        return res

    def get_shipment_exception(self, cursor, user, purchases, context=None):
        '''
        Return if there is a shipment in exception for the purchases

        :param cursor: the database cursor
        :param user: the user id
        :param purchases: a BrowseRecordList of purchases
        :param context: the context
        :return: a dictionary with purchase id as key and
            a boolean as value
        '''
        res = {}
        for purchase in purchases:
            val = False
            for line in purchase.lines:
                if line.move_exception:
                    val = True
                    break
            res[purchase.id] = val
        return res

    def get_rec_name(self, cursor, user, ids, name, arg, context=None):
        if not ids:
            return {}
        res = {}
        for purchase in self.browse(cursor, user, ids, context=context):
            res[purchase.id] = purchase.reference or str(purchase.id) \
                    + ' - ' + purchase.party.name
        return res

    def search_rec_name(self, cursor, user, name, args, context=None):
        args2 = []
        i = 0
        while i < len(args):
            names = args[i][2].split(' - ', 1)
            ids = self.search(cursor, user, ['OR',
                ('reference', args[i][1], names[0]),
                ('supplier_reference', args[i][1], names[0]),
                ], context=context)
            args2.append(('id', 'in', ids))
            if len(names) != 1 and names[1]:
                args2.append(('party', args[i][1], names[1]))
            i += 1
        return args2

    def copy(self, cursor, user, ids, default=None, context=None):
        if default is None:
            default = {}
        default = default.copy()
        default['state'] = 'draft'
        default['reference'] = False
        default['invoice_state'] = 'none'
        default['invoices'] = False
        default['invoices_ignored'] = False
        default['shipment_state'] = 'none'
        return super(Purchase, self).copy(cursor, user, ids, default=default,
                context=context)

    def check_for_quotation(self, cursor, user, purchase_id, context=None):
        purchase = self.browse(cursor, user, purchase_id, context=context)
        if not purchase.invoice_address:
            self.raise_user_error(cursor, 'invoice_addresse_required', context=context)
        return True

    def set_reference(self, cursor, user, purchase_id, context=None):
        sequence_obj = self.pool.get('ir.sequence')

        purchase = self.browse(cursor, user, purchase_id, context=context)

        if purchase.reference:
            return True

        reference = sequence_obj.get(cursor, user, 'purchase.purchase',
                context=context)
        self.write(cursor, user, purchase_id, {
            'reference': reference,
            }, context=context)
        return True

    def set_purchase_date(self, cursor, user, purchase_id, context=None):
        date_obj = self.pool.get('ir.date')

        self.write(cursor, user, purchase_id, {
            'purchase_date': date_obj.today(cursor, user, context=context),
            }, context=context)
        return True

    def _get_invoice_line_purchase_line(self, cursor, user, purchase,
            context=None):
        '''
        Return invoice line values for each purchase lines

        :param cursor: the database cursor
        :param user: the user id
        :param purchase: a BrowseRecord of the purchase
        :param context: the context
        :return: a dictionary with line id as key and a list
            of invoice line values as value
        '''
        line_obj = self.pool.get('purchase.line')
        res = {}
        for line in purchase.lines:
            val = line_obj.get_invoice_line(cursor, user, line,
                    context=context)
            if val:
                res[line.id] = val
        return res

    def _get_invoice_purchase(self, cursor, user, purchase, context=None):
        '''
        Return invoice values for purchase

        :param cursor: the database cursor
        :param user: the user id
        :param purchase: the BrowseRecord of the purchase
        :param context: the context

        :return: a dictionary with purchase fields as key and
            purchase values as value
        '''
        journal_obj = self.pool.get('account.journal')

        journal_id = journal_obj.search(cursor, user, [
            ('type', '=', 'expense'),
            ], limit=1, context=context)
        if journal_id:
            journal_id = journal_id[0]

        res = {
            'company': purchase.company.id,
            'type': 'in_invoice',
            'reference': purchase.reference,
            'journal': journal_id,
            'party': purchase.party.id,
            'invoice_address': purchase.invoice_address.id,
            'currency': purchase.currency.id,
            'account': purchase.party.account_payable.id,
            'payment_term': purchase.payment_term.id,
        }
        return res

    def create_invoice(self, cursor, user, purchase_id, context=None):
        '''
        Create invoice for the purchase id

        :param cursor: the database cursor
        :param user: the user id
        :param purchase_id: the id of the purchase
        :param context: the context
        :return: the id of the invoice or None
        '''
        invoice_obj = self.pool.get('account.invoice')
        invoice_line_obj = self.pool.get('account.invoice.line')
        purchase_line_obj = self.pool.get('purchase.line')

        if context is None:
            context = {}

        purchase = self.browse(cursor, user, purchase_id, context=context)

        if not purchase.party.account_payable:
            self.raise_user_error(cursor, 'missing_account_payable',
                    error_args=(purchase.party.rec_name,), context=context)

        invoice_lines = self._get_invoice_line_purchase_line(cursor, user,
                purchase, context=context)
        if not invoice_lines:
            return

        ctx = context.copy()
        ctx['user'] = user
        vals = self._get_invoice_purchase(cursor, user, purchase, context=context)
        invoice_id = invoice_obj.create(cursor, 0, vals, context=ctx)

        for line in purchase.lines:
            if line.id not in invoice_lines:
                continue
            for vals in invoice_lines[line.id]:
                vals['invoice'] = invoice_id
                invoice_line_id = invoice_line_obj.create(cursor, 0, vals,
                        context=ctx)
                purchase_line_obj.write(cursor, user, line.id, {
                    'invoice_lines': [('add', invoice_line_id)],
                    }, context=context)

        invoice_obj.update_taxes(cursor, 0, [invoice_id], context=ctx)

        self.write(cursor, user, purchase_id, {
            'invoices': [('add', invoice_id)],
        }, context=context)
        return invoice_id

    def create_move(self, cursor, user, purchase_id, context=None):
        '''
        Create move for each purchase lines
        '''
        line_obj = self.pool.get('purchase.line')

        purchase = self.browse(cursor, user, purchase_id, context=context)
        for line in purchase.lines:
            line_obj.create_move(cursor, user, line, context=context)

Purchase()


class PurchaseInvoice(ModelSQL):
    'Purchase - Invoice'
    _name = 'purchase.purchase-account.invoice'
    _table = 'purchase_invoices_rel'
    _description = __doc__
    purchase = fields.Many2One('purchase.purchase', 'Purchase',
            ondelete='CASCADE', select=1, required=True)
    invoice = fields.Many2One('account.invoice', 'Invoice',
            ondelete='RESTRICT', select=1, required=True)

PurchaseInvoice()


class PuchaseIgnoredInvoice(ModelSQL):
    'Purchase - Ignored Invoice'
    _name = 'purchase.purchase-ignored-account.invoice'
    _table = 'purchase_invoice_ignored_rel'
    _description = __doc__
    purchase = fields.Many2One('purchase.purchase', 'Purchase',
            ondelete='CASCADE', select=1, required=True)
    invoice = fields.Many2One('account.invoice', 'Invoice',
            ondelete='RESTRICT', select=1, required=True)

PuchaseIgnoredInvoice()


class PurchaseRecreadtedInvoice(ModelSQL):
    'Purchase - Recreated Invoice'
    _name = 'purchase.purchase-recreated-account.invoice'
    _table = 'purchase_invoice_recreated_rel'
    _description = __doc__
    purchase = fields.Many2One('purchase.purchase', 'Purchase',
            ondelete='CASCADE', select=1, required=True)
    invoice = fields.Many2One('account.invoice', 'Invoice',
            ondelete='RESTRICT', select=1, required=True)

PurchaseRecreadtedInvoice()


class PurchaseLine(ModelSQL, ModelView):
    'Purchase Line'
    _name = 'purchase.line'
    _rec_name = 'description'
    _description = __doc__

    purchase = fields.Many2One('purchase.purchase', 'Purchase', ondelete='CASCADE',
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
                'readonly': "not globals().get('_parent_purchase')",
            }, on_change=['product', 'quantity', 'unit',
                '_parent_purchase.currency', '_parent_purchase.party'])
    unit = fields.Many2One('product.uom', 'Unit',
            states={
                'required': "product",
                'invisible': "type != 'line'",
                'readonly': "not globals().get('_parent_purchase')",
            }, domain=["('category', '=', " \
                    "(product, 'product.default_uom.category'))"],
            context="{'category': (product, 'product.default_uom.category')}",
            on_change=['product', 'quantity', 'unit', '_parent_purchase.currency',
                '_parent_purchase.party'])
    unit_digits = fields.Function('get_unit_digits', type='integer',
            string='Unit Digits', on_change_with=['unit'])
    product = fields.Many2One('product.product', 'Product',
            domain=[('purchasable', '=', True)],
            states={
                'invisible': "type != 'line'",
                'readonly': "not globals().get('_parent_purchase')",
            }, on_change=['product', 'unit', 'quantity', 'description',
                '_parent_purchase.party', '_parent_purchase.currency'],
            context="{'locations': " \
                        "_parent_purchase.warehouse and " \
                        "[_parent_purchase.warehouse] or False, " \
                    "'stock_date_end': _parent_purchase.purchase_date, " \
                    "'purchasable': True, " \
                    "'stock_skip_warehouse': True}")
    unit_price = fields.Numeric('Unit Price', digits=(16, 4),
            states={
                'invisible': "type != 'line'",
                'required': "type == 'line'",
            })
    amount = fields.Function('get_amount', type='numeric', string='Amount',
            digits="(16, _parent_purchase.currency_digits)",
            states={
                'invisible': "type not in ('line', 'subtotal')",
                'readonly': "not globals().get('_parent_purchase')",
            }, on_change_with=['type', 'quantity', 'unit_price', 'unit',
                '_parent_purchase.currency'])
    description = fields.Text('Description', size=None, required=True)
    note = fields.Text('Note')
    taxes = fields.Many2Many('purchase.line-account.tax',
            'line', 'tax', 'Taxes', domain=[('parent', '=', False)],
            states={
                'invisible': "type != 'line'",
            })
    invoice_lines = fields.Many2Many('purchase.line-account.invoice.line',
            'purchase_line', 'invoice_line', 'Invoice Lines', readonly=True)
    moves = fields.One2Many('stock.move', 'purchase_line', 'Moves',
            readonly=True, select=1)
    moves_ignored = fields.Many2Many('purchase.line-ignored-stock.move',
            'purchase_line', 'move', 'Ignored Moves', readonly=True)
    moves_recreated = fields.Many2Many('purchase.line-recreated-stock.move',
            'purchase_line', 'move', 'Recreated Moves', readonly=True)
    move_done = fields.Function('get_move_done', type='boolean',
            string='Moves Done')
    move_exception = fields.Function('get_move_exception', type='boolean',
            string='Moves Exception')

    def __init__(self):
        super(PurchaseLine, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))
        self._error_messages.update({
            'supplier_location_required': 'The supplier location is required!',
            'missing_account_expense': 'It misses ' \
                    'an "Account Expense" on product "%s"!',
            'missing_account_expense_property': 'It misses ' \
                    'an "account expense" default property!',
            })

    def init(self, cursor, module_name):
        super(PurchaseLine, self).init(cursor, module_name)
        table = TableHandler(cursor, self, module_name)

        # Migration from 1.0 comment change into note
        if table.column_exist('comment'):
            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET note = comment')
            table.drop_column('comment', exception=True)

    def default_type(self, cursor, user, context=None):
        return 'line'

    def default_quantity(self, cursor, user, context=None):
        return 0.0

    def default_unit_price(self, cursor, user, context=None):
        return Decimal('0.0')

    def get_move_done(self, cursor, user, ids, name, args, context=None):
        uom_obj = self.pool.get('product.uom')
        res = {}
        for line in self.browse(cursor, user, ids, context=context):
            val = True
            if not line.product:
                res[line.id] = True
                continue
            if line.product.type == 'service':
                res[line.id] = True
                continue
            skip_ids = set(x.id for x in line.moves_recreated + \
                                line.moves_ignored)
            quantity = line.quantity
            for move in line.moves:
                if move.state != 'done' \
                        and move.id not in skip_ids:
                    val = False
                    break
                quantity -= uom_obj.compute_qty(cursor, user, move.uom,
                     move.quantity, line.unit, context=context)
            if val:
                if quantity > 0.0:
                    val = False
            res[line.id] = val
        return res

    def get_move_exception(self, cursor, user, ids, name, args, context=None):
        res = {}
        for line in self.browse(cursor, user, ids, context=context):
            val = False
            skip_ids = set(x.id for x in line.moves_ignored + \
                               line.moves_recreated)
            for move in line.moves:
                if move.state == 'cancel' \
                        and move.id not in skip_ids:
                    val = True
                    break
            res[line.id] = val
        return res

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

    def _get_tax_rule_pattern(self, cursor, user, party, vals, context=None):
        '''
        Get tax rule pattern

        :param cursor: the database cursor
        :param user: the user id
        :param party: the BrowseRecord of the party
        :param vals: a dictionary with value from on_change
        :param context: the context
        :return: a dictionary to use as pattern for tax rule
        '''
        res = {}
        return res

    def on_change_product(self, cursor, user, ids, vals, context=None):
        party_obj = self.pool.get('party.party')
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        tax_rule_obj = self.pool.get('account.tax.rule')

        if context is None:
            context = {}
        if not vals.get('product'):
            return {}
        res = {}

        ctx = context.copy()
        party = None
        if vals.get('_parent_purchase.party'):
            party = party_obj.browse(cursor, user, vals['_parent_purchase.party'],
                    context=context)
            if party.lang:
                ctx['language'] = party.lang.code

        product = product_obj.browse(cursor, user, vals['product'],
                context=context)

        ctx2 = context.copy()
        if vals.get('_parent_purchase.currency'):
            ctx2['currency'] = vals['_parent_purchase.currency']
        if vals.get('_parent_purchase.party'):
            ctx2['supplier'] = vals['_parent_purchase.party']
        if vals.get('unit'):
            ctx2['uom'] = vals['unit']
        else:
            ctx2['uom'] = product.purchase_uom.id
        res['unit_price'] = product_obj.get_purchase_price(cursor, user,
                [product.id], vals.get('quantity', 0), context=ctx2)[product.id]
        res['taxes'] = []
        pattern = self._get_tax_rule_pattern(cursor, user, party, vals,
                context=context)
        for tax in product.supplier_taxes_used:
            if party and party.supplier_tax_rule:
                tax_ids = tax_rule_obj.apply(cursor, user,
                        party.supplier_tax_rule, tax, pattern,
                        context=context)
                if tax_ids:
                    res['taxes'].extend(tax_ids)
                continue
            res['taxes'].append(tax.id)
        if party and party.supplier_tax_rule:
            tax_ids = tax_rule_obj.apply(cursor, user,
                    party.supplier_tax_rule, False, pattern,
                    context=context)
            if tax_ids:
                res['taxes'].extend(tax_ids)

        if not vals.get('description'):
            res['description'] = product_obj.browse(cursor, user, product.id,
                    context=ctx).rec_name

        category = product.purchase_uom.category
        if not vals.get('unit') \
                or vals.get('unit') not in [x.id for x in category.uoms]:
            res['unit'] = product.purchase_uom.id
            res['unit.rec_name'] = product.purchase_uom.rec_name
            res['unit_digits'] = product.purchase_uom.digits

        vals = vals.copy()
        vals['unit_price'] = res['unit_price']
        vals['type'] = 'line'
        res['amount'] = self.on_change_with_amount(cursor, user, ids,
                vals, context=context)
        return res

    def on_change_quantity(self, cursor, user, ids, vals, context=None):
        product_obj = self.pool.get('product.product')

        if context is None:
            context = {}
        if not vals.get('product'):
            return {}
        res = {}

        product = product_obj.browse(cursor, user, vals['product'],
                context=context)

        ctx2 = context.copy()
        if vals.get('_parent_purchase.currency'):
            ctx2['currency'] = vals['_parent_purchase.currency']
        if vals.get('_parent_purchase.party'):
            ctx2['supplier'] = vals['_parent_purchase.party']
        if vals.get('unit'):
            ctx2['uom'] = vals['unit']
        res['unit_price'] = product_obj.get_purchase_price(cursor, user,
                [vals['product']], vals.get('quantity', 0),
                context=ctx2)[vals['product']]
        return res

    def on_change_unit(self, cursor, user, ids, vals, context=None):
        return self.on_change_quantity(cursor, user, ids, vals, context=context)

    def on_change_with_amount(self, cursor, user, ids, vals, context=None):
        currency_obj = self.pool.get('currency.currency')
        if vals.get('type') == 'line':
            if isinstance(vals.get('_parent_purchase.currency'), (int, long)):
                currency = currency_obj.browse(cursor, user,
                        vals['_parent_purchase.currency'], context=context)
            else:
                currency = vals['_parent_purchase.currency']
            amount = Decimal(str(vals.get('quantity') or '0.0')) * \
                    (vals.get('unit_price') or Decimal('0.0'))
            if currency:
                return currency_obj.round(cursor, user, currency, amount)
            return amount
        return Decimal('0.0')

    def get_amount(self, cursor, user, ids, name, arg, context=None):
        currency_obj = self.pool.get('currency.currency')
        res = {}
        for line in self.browse(cursor, user, ids, context=context):
            if line.type == 'line':
                res[line.id] = currency_obj.round(cursor, user,
                        line.purchase.currency,
                        Decimal(str(line.quantity)) * line.unit_price)
            elif line.type == 'subtotal':
                res[line.id] = Decimal('0.0')
                for line2 in line.purchase.lines:
                    if line2.type == 'line':
                        res[line.id] += currency_obj.round(cursor, user,
                                line2.purchase.currency,
                                Decimal(str(line2.quantity)) * line2.unit_price)
                    elif line2.type == 'subtotal':
                        if line.id == line2.id:
                            break
                        res[line.id] = Decimal('0.0')
            else:
                res[line.id] = Decimal('0.0')
        return res

    def get_invoice_line(self, cursor, user, line, context=None):
        '''
        Return invoice line values for purchase line

        :param cursor: the database cursor
        :param user: the user id
        :param line: a BrowseRecord of the purchase line
        :param context: the context
        :return: a list of invoice line values
        '''
        uom_obj = self.pool.get('product.uom')
        property_obj = self.pool.get('ir.property')

        res = {}
        res['sequence'] = line.sequence
        res['type'] = line.type
        res['description'] = line.description
        res['note'] = line.note
        if line.type != 'line':
            return [res]
        if (line.purchase.invoice_method == 'order'
                or not line.product
                or line.product.type == 'service'):
            quantity = line.quantity
        else:
            quantity = 0.0
            for move in line.moves:
                if move.state == 'done':
                    quantity += uom_obj.compute_qty(cursor, user, move.uom,
                            move.quantity, line.unit, context=context)

        if line.purchase.invoices_ignored:
            ignored_ids = set(
                l.id for i in line.purchase.invoices_ignored for l in i.lines)
        else:
            ignored_ids = ()
        for invoice_line in line.invoice_lines:
            if invoice_line.type != 'line':
                continue
            if ((invoice_line.invoice and
                    invoice_line.invoice.state != 'cancel') or
                invoice_line.id in ignored_ids):
                quantity -= uom_obj.compute_qty(
                    cursor, user, invoice_line.unit, invoice_line.quantity,
                    line.unit, context=context)
        res['quantity'] = quantity


        if res['quantity'] <= 0.0:
            return None
        res['unit'] = line.unit.id
        res['product'] = line.product.id
        res['unit_price'] = line.unit_price
        res['taxes'] = [('set', [x.id for x in line.taxes])]
        if line.product:
            res['account'] = line.product.account_expense_used.id
            if not res['account']:
                self.raise_user_error(cursor, 'missing_account_expense',
                        error_args=(line.product.rec_name,), context=context)
        else:
            for model in ('product.template', 'product.category'):
                res['account'] = property_obj.get(cursor, user,
                        'account_expense', model, context=context)
                if res['account']:
                    break
            if not res['account']:
                self.raise_user_error(cursor,
                        'missing_account_expense_property', context=context)
        return [res]

    def copy(self, cursor, user, ids, default=None, context=None):
        if default is None:
            default = {}
        default = default.copy()
        default['moves'] = False
        default['moves_ignored'] = False
        default['moves_recreated'] = False
        default['invoice_lines'] = False
        return super(PurchaseLine, self).copy(cursor, user, ids,
                default=default, context=context)

    def create_move(self, cursor, user, line, context=None):
        '''
        Create move line
        '''
        move_obj = self.pool.get('stock.move')
        uom_obj = self.pool.get('product.uom')
        product_supplier_obj = self.pool.get('purchase.product_supplier')

        if context is None:
            context = {}

        vals = {}
        if line.type != 'line':
            return
        if not line.product:
            return
        if line.product.type == 'service':
            return
        skip_ids = set(x.id for x in line.moves_recreated)
        quantity = line.quantity
        for move in line.moves:
            if move.id not in skip_ids:
                quantity -= uom_obj.compute_qty(cursor, user, move.uom,
                        move.quantity, line.unit, context=context)
        if quantity <= 0.0:
            return
        if not line.purchase.party.supplier_location:
            self.raise_user_error(cursor, 'supplier_location_required',
                    context=context)
        vals['quantity'] = quantity
        vals['uom'] = line.unit.id
        vals['product'] = line.product.id
        vals['from_location'] = line.purchase.party.supplier_location.id
        vals['to_location'] = line.purchase.warehouse.input_location.id
        vals['state'] = 'draft'
        vals['company'] = line.purchase.company.id
        vals['unit_price'] = line.unit_price
        vals['currency'] = line.purchase.currency.id

        if line.product.product_suppliers:
            for product_supplier in line.product.product_suppliers:
                if product_supplier.party.id == line.purchase.party.id:
                    vals['planned_date'] = \
                            product_supplier_obj.compute_supply_date(
                                    cursor, user, product_supplier,
                                    date=line.purchase.purchase_date,
                                    context=context)[0]
                    break

        ctx = context.copy()
        ctx['user'] = user
        move_id = move_obj.create(cursor, 0, vals, context=ctx)

        self.write(cursor, 0, line.id, {
            'moves': [('add', move_id)],
        }, context=ctx)
        return move_id

PurchaseLine()


class PurchaseLineTax(ModelSQL):
    'Purchase Line - Tax'
    _name = 'purchase.line-account.tax'
    _table = 'purchase_line_account_tax'
    _description = __doc__
    line = fields.Many2One('purchase.line', 'Purchase Line',
            ondelete='CASCADE', select=1, required=True,
            domain=[('type', '=', 'line')])
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
            select=1, required=True, domain=[('parent', '=', False)])

PurchaseLineTax()


class PurchaseLineInvoiceLine(ModelSQL):
    'Purchase Line - Invoice Line'
    _name = 'purchase.line-account.invoice.line'
    _table = 'purchase_line_invoice_lines_rel'
    _description = __doc__
    purchase_line = fields.Many2One('purchase.line', 'Purchase Line',
            ondelete='CASCADE', select=1, required=True)
    invoice_line = fields.Many2One('account.invoice.line', 'Invoice Line',
            ondelete='RESTRICT', select=1, required=True)

PurchaseLineInvoiceLine()


class PurchaseLineIgnoredMove(ModelSQL):
    'Purchase Line - Ignored Move'
    _name = 'purchase.line-ignored-stock.move'
    _table = 'purchase_line_moves_ignored_rel'
    _description = __doc__
    purchase_line = fields.Many2One('purchase.line', 'Purchase Line',
            ondelete='CASCADE', select=1, required=True)
    move = fields.Many2One('stock.move', 'Move', ondelete='RESTRICT',
            select=1, required=True)

PurchaseLineIgnoredMove()


class PurchaseLineRecreatedMove(ModelSQL):
    'Purchase Line - Ignored Move'
    _name = 'purchase.line-recreated-stock.move'
    _table = 'purchase_line_moves_recreated_rel'
    _description = __doc__
    purchase_line = fields.Many2One('purchase.line', 'Purchase Line',
            ondelete='CASCADE', select=1, required=True)
    move = fields.Many2One('stock.move', 'Move', ondelete='RESTRICT',
            select=1, required=True)

PurchaseLineRecreatedMove()


class PurchaseReport(CompanyReport):
    _name = 'purchase.purchase'

PurchaseReport()


class Template(ModelSQL, ModelView):
    _name = "product.template"

    purchasable = fields.Boolean('Purchasable', states={
        'readonly': "active == False",
        })
    product_suppliers = fields.One2Many('purchase.product_supplier',
            'product', 'Suppliers', states={
                'readonly': "active == False",
                'invisible': "(not purchasable) or (not company)",
            })
    purchase_uom = fields.Many2One('product.uom', 'Purchase UOM', states={
        'readonly': "active == False",
        'invisible': "not purchasable",
        'required': "purchasable",
        }, domain=["('category', '=', (default_uom, 'uom.category'))"],
        context="{'category': (default_uom, 'uom.category')}",
        on_change_with=['default_uom', 'purchase_uom', 'purchasable'])

    def __init__(self):
        super(Template, self).__init__()
        self._error_messages.update({
                'change_purchase_uom': 'Purchase prices are based on the purchase uom, '\
                    'are you sure to change it?',
            })
        if 'not bool(account_category) and bool(purchasable)' not in \
                self.account_expense.states.get('required', ''):
            self.account_expense = copy.copy(self.account_expense)
            self.account_expense.states = copy.copy(self.account_expense.states)
            if not self.account_expense.states.get('required'):
                self.account_expense.states['required'] = \
                        "not bool(account_category) and bool(purchasable)"
            else:
                self.account_expense.states['required'] = '(' + \
                        self.account_expense.states['required'] + ') ' \
                        'or (not bool(account_category) and bool(purchasable))'
        if 'account_category' not in self.account_expense.depends:
            self.account_expense = copy.copy(self.account_expense)
            self.account_expense.depends = \
                    copy.copy(self.account_expense.depends)
            self.account_expense.depends.append('account_category')
        if 'purchasable' not in self.account_expense.depends:
            self.account_expense = copy.copy(self.account_expense)
            self.account_expense.depends = \
                    copy.copy(self.account_expense.depends)
            self.account_expense.depends.append('purchasable')
        self._reset_columns()

    def default_purchasable(self, cursor, user, context=None):
        if context is None:
            context = {}
        if context.get('purchasable'):
            return True
        return False

    def on_change_with_purchase_uom(self, cursor, user, ids, vals,
            context=None):
        uom_obj = self.pool.get('product.uom')
        res = False

        if vals.get('default_uom'):
            default_uom = uom_obj.browse(cursor, user, vals['default_uom'],
                    context=context)
            if vals.get('purchase_uom'):
                purchase_uom = uom_obj.browse(cursor, user, vals['purchase_uom'],
                        context=context)
                if default_uom.category.id == purchase_uom.category.id:
                    res = purchase_uom.id
                else:
                    res = default_uom.id
            else:
                res = default_uom.id
        return res

    def write(self, cursor, user, ids, vals, context=None):
        if vals.get("purchase_uom"):
            templates = self.browse(cursor, user, ids, context=context)
            for template in templates:
                if not template.purchase_uom:
                    continue
                if template.purchase_uom.id == vals["purchase_uom"]:
                    continue
                for product in template.products:
                    if not product.product_suppliers:
                        continue
                    self.raise_user_warning(
                        cursor, user, '%s@product_template' % template.id,
                        'change_purchase_uom')

        super(Template, self).write(cursor, user, ids, vals, context=context)

Template()


class Product(ModelSQL, ModelView):
    _name = 'product.product'

    def on_change_with_purchase_uom(self, cursor, user, ids, vals, context=None):
        template_obj = self.pool.get('product.template')
        return template_obj.on_change_with_purchase_uom(cursor, user, ids, vals,
                context=context)

    def get_purchase_price(self, cursor, user, ids, quantity=0, context=None):
        '''
        Return purchase price for product ids.

        :param cursor: the database cursor
        :param user: the user id
        :param ids: the product ids
        :param quantity: the quantity of products
        :param context: the context that can have as keys:
            uom: the unit of measure
            supplier: the supplier party id
            currency: the currency id for the returned price
        :return: a dictionary with for each product ids keys the computed price
        '''
        uom_obj = self.pool.get('product.uom')
        user_obj = self.pool.get('res.user')
        currency_obj = self.pool.get('currency.currency')

        if context is None:
            context = {}

        res = {}

        uom = None
        if context.get('uom'):
            uom = uom_obj.browse(cursor, user, context['uom'],
                    context=context)

        currency = None
        if context.get('currency'):
            currency = currency_obj.browse(cursor, user, context['currency'],
                    context=context)

        user2 = user_obj.browse(cursor, user, user, context=context)

        for product in self.browse(cursor, user, ids, context=context):
            res[product.id] = product.cost_price
            default_uom = product.default_uom
            if not uom:
                uom = default_uom
            if context.get('supplier') and product.product_suppliers:
                supplier_id = context['supplier']
                for product_supplier in product.product_suppliers:
                    if product_supplier.party.id == supplier_id:
                        for price in product_supplier.prices:
                            if uom_obj.compute_qty(cursor, user,
                                    product.purchase_uom, price.quantity, uom,
                                    context=context) <= quantity:
                                res[product.id] = price.unit_price
                                default_uom = product.purchase_uom
                        break
            res[product.id] = uom_obj.compute_price(cursor, user,
                    default_uom, res[product.id], uom, context=context)
            if currency and user2.company:
                if user2.company.currency.id != currency.id:
                    res[product.id] = currency_obj.compute(cursor, user,
                            user2.company.currency, res[product.id],
                            currency, context=context)
        return res

Product()


class ProductSupplier(ModelSQL, ModelView):
    'Product Supplier'
    _name = 'purchase.product_supplier'
    _description = __doc__

    product = fields.Many2One('product.template', 'Product', required=True,
            ondelete='CASCADE', select=1)
    party = fields.Many2One('party.party', 'Supplier', required=True,
            ondelete='CASCADE', select=1)
    name = fields.Char('Name', size=None, translate=True, select=1)
    code = fields.Char('Code', size=None, select=1)
    sequence = fields.Integer('Sequence')
    prices = fields.One2Many('purchase.product_supplier.price',
            'product_supplier', 'Prices')
    company = fields.Many2One('company.company', 'Company', required=True,
            ondelete='CASCADE', select=1,
            domain=["('id', 'company' in context and '=' or '!=', " \
                    "context.get('company', 0))"])
    delivery_time = fields.Integer('Delivery Time',
            help="In number of days")

    def __init__(self):
        super(ProductSupplier, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))

    def default_company(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        if context is None:
            context = {}
        if context.get('company'):
            return context['company']
        return False

    def compute_supply_date(self, cursor, user, product_supplier, date=None,
            context=None):
        '''
        Compute the supply date for the Product Supplier at the given date
            and the next supply date

        :param cursor: the database cursor
        :param user: the user id
        :param product_supplier: a BrowseRecord of the Product Supplier
        :param date: the date of the purchase if None the current date
        :param context: the context
        :return: a tuple with the supply date and the next one
        '''
        date_obj = self.pool.get('ir.date')

        if not date:
            date = date_obj.today(cursor, user, context=context)
        next_date = date + datetime.timedelta(1)
        return (date + datetime.timedelta(product_supplier.delivery_time),
                next_date + datetime.timedelta(product_supplier.delivery_time))

    def compute_purchase_date(self, cursor, user, product_supplier, date,
            context=None):
        '''
        Compute the purchase date for the Product Supplier at the given date

        :param cursor: the database cursor
        :param user: the user id
        :param product_supplier: a BrowseRecord of the Product Supplier
        :param date: the date of the supply
        :param context: the context
        :return: the purchase date
        '''
        date_obj = self.pool.get('ir.date')

        if not product_supplier.delivery_time:
            return date_obj.today(cursor, user, context=context)
        return date - datetime.timedelta(product_supplier.delivery_time)

ProductSupplier()


class ProductSupplierPrice(ModelSQL, ModelView):
    'Product Supplier Price'
    _name = 'purchase.product_supplier.price'
    _description = __doc__

    product_supplier = fields.Many2One('purchase.product_supplier',
            'Supplier', required=True, ondelete='CASCADE')
    quantity = fields.Float('Quantity', required=True, help='Minimal quantity')
    unit_price = fields.Numeric('Unit Price', required=True, digits=(16, 4))

    def __init__(self):
        super(ProductSupplierPrice, self).__init__()
        self._order.insert(0, ('quantity', 'ASC'))

    def default_currency(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        currency_obj = self.pool.get('currency.currency')
        if context is None:
            context = {}
        company = None
        if context.get('company'):
            company = company_obj.browse(cursor, user, context['company'],
                    context=context)
            return company.currency.id
        return False

ProductSupplierPrice()


class ShipmentIn(ModelSQL, ModelView):
    _name = 'stock.shipment.in'

    def __init__(self):
        super(ShipmentIn, self).__init__()
        self.incoming_moves = copy.copy(self.incoming_moves)
        if "('supplier', '=', supplier)" not in self.incoming_moves.add_remove:
            self.incoming_moves.add_remove = "[" + \
                    self.incoming_moves.add_remove + ", " \
                    "('supplier', '=', supplier)]"
        self._reset_columns()

        self._error_messages.update({
                'reset_move': 'You cannot reset to draft a move generated '\
                    'by a purchase.',
            })

    def write(self, cursor, user, ids, vals, context=None):
        purchase_obj = self.pool.get('purchase.purchase')
        purchase_line_obj = self.pool.get('purchase.line')

        res = super(ShipmentIn, self).write(cursor, user, ids, vals,
                context=context)

        if 'state' in vals and vals['state'] in ('received', 'cancel'):
            purchase_ids = []
            move_ids = []
            if isinstance(ids, (int, long)):
                ids = [ids]
            for shipment in self.browse(cursor, user, ids, context=context):
                move_ids.extend([x.id for x in shipment.incoming_moves])

            purchase_line_ids = purchase_line_obj.search(cursor, user, [
                ('moves', 'in', move_ids),
                ], context=context)
            if purchase_line_ids:
                for purchase_line in purchase_line_obj.browse(cursor, user,
                        purchase_line_ids, context=context):
                    if purchase_line.purchase.id not in purchase_ids:
                        purchase_ids.append(purchase_line.purchase.id)

            purchase_obj.workflow_trigger_validate(cursor, user, purchase_ids,
                    'shipment_update', context=context)
        return res

    def button_draft(self, cursor, user, ids, context=None):
        for shipment in self.browse(cursor, user, ids, context=context):
            for move in shipment.incoming_moves:
                if move.state == 'cancel' and move.purchase_line:
                    self.raise_user_error(cursor, 'reset_move')

        return super(ShipmentIn, self).button_draft(
            cursor, user, ids, context=context)

ShipmentIn()


class Move(ModelSQL, ModelView):
    _name = 'stock.move'

    purchase_line = fields.Many2One('purchase.line', select=1,
            states={
                'readonly': "state != 'draft'",
            })
    purchase = fields.Function('get_purchase', type='many2one',
            relation='purchase.purchase', string='Purchase',
            fnct_search='search_purchase', select=1, states={
                'invisible': "not purchase_visible",
            }, depends=['purchase_visible'])
    purchase_quantity = fields.Function('get_purchase_fields',
            type='float', digits="(16, unit_digits)",
            string='Purchase Quantity',
            states={
                'invisible': "not purchase_visible",
            }, depends=['purchase_visible'])
    purchase_unit = fields.Function('get_purchase_fields',
            type='many2one', relation='product.uom',
            string='Purchase Unit',
            states={
                'invisible': "not purchase_visible",
            }, depends=['purchase_visible'])
    purchase_unit_digits = fields.Function('get_purchase_fields',
            type='integer', string='Purchase Unit Digits')
    purchase_unit_price = fields.Function('get_purchase_fields',
            type='numeric', digits=(16, 4), string='Purchase Unit Price',
            states={
                'invisible': "not purchase_visible",
            }, depends=['purchase_visible'])
    purchase_currency = fields.Function('get_purchase_fields',
            type='many2one', relation='currency.currency',
            string='Purchase Currency',
            states={
                'invisible': "not purchase_visible",
            }, depends=['purchase_visible'])
    purchase_visible = fields.Function('get_purchase_visible',
            type="boolean", string='Purchase Visible',
            on_change_with=['from_location'])
    supplier = fields.Function('get_supplier', type='many2one',
            relation='party.party', string='Supplier',
            fnct_search='search_supplier', select=1)

    purchase_exception_state = fields.Function('get_purchase_exception_state',
            type='selection',
            selection=[('', ''),
                       ('ignored', 'Ignored'),
                       ('recreated', 'Recreated')],
            string='Exception State')

    def get_purchase(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for move in self.browse(cursor, user, ids, context=context):
            res[move.id] = False
            if move.purchase_line:
                res[move.id] = move.purchase_line.purchase.id
        return res

    def get_purchase_exception_state(self, cursor, user, ids, name, arg,
                                     context=None):
        res = {}.fromkeys(ids, '')
        for move in self.browse(cursor, user, ids, context=context):
            if not move.purchase_line:
                continue
            if move.id in (x.id for x in move.purchase_line.moves_recreated):
                res[move.id] = 'recreated'
            if move.id in (x.id for x in move.purchase_line.moves_ignored):
                res[move.id] = 'ignored'
        return res

    def search_purchase(self, cursor, user, name, args, context=None):
        args2 = []
        i = 0
        while i < len(args):
            field = args[i][0]
            args2.append(('purchase_line.' + field, args[i][1], args[i][2]))
            i += 1
        return args2

    def get_purchase_fields(self, cursor, user, ids, names, arg, context=None):
        res = {}
        for name in names:
            res[name] = {}

        for move in self.browse(cursor, user, ids, context=context):
            for name in res.keys():
                if name[9:] == 'quantity':
                    res[name][move.id] = 0.0
                elif name[9:] == 'unit_digits':
                    res[name][move.id] = 2
                else:
                    res[name][move.id] = False
            if move.purchase_line:
                for name in res.keys():
                    if name[9:] == 'currency':
                        res[name][move.id] = move.purchase_line.\
                                purchase.currency.id
                    elif name[9:] in ('quantity', 'unit_digits', 'unit_price'):
                        res[name][move.id] = move.purchase_line[name[9:]]
                    else:
                        res[name][move.id] = move.purchase_line[name[9:]].id
        return res

    def default_purchase_visible(self, cursor, user, context=None):
        from_location = self.default_from_location(cursor, user,
                context=context)
        vals = {
            'from_location': from_location,
        }
        return self.on_change_with_purchase_visible(cursor, user, [], vals,
                context=context)

    def on_change_with_purchase_visible(self, cursor, user, ids, vals,
            context=None):
        location_obj = self.pool.get('stock.location')
        if vals.get('from_location'):
            from_location = location_obj.browse(cursor, user,
                    vals['from_location'], context=context)
            if from_location.type == 'supplier':
                return True
        return False

    def get_purchase_visible(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for move in self.browse(cursor, user, ids, context=context):
            res[move.id] = False
            if move.from_location.type == 'supplier':
                res[move.id] = True
        return res

    def get_supplier(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for move in self.browse(cursor, user, ids, context=context):
            res[move.id] = False
            if move.purchase_line:
                res[move.id] = move.purchase_line.purchase.party.id
        return res

    def search_supplier(self, cursor, user, name, args, context=None):
        args2 = []
        i = 0
        while i < len(args):
            args2.append(('purchase_line.purchase.party', args[i][1],
                args[i][2]))
            i += 1
        return args2

    def write(self, cursor, user, ids, vals, context=None):
        purchase_obj = self.pool.get('purchase.purchase')
        purchase_line_obj = self.pool.get('purchase.line')

        res = super(Move, self).write(cursor, user, ids, vals,
                context=context)
        if 'state' in vals and vals['state'] in ('cancel',):
            if isinstance(ids, (int, long)):
                ids = [ids]
            purchase_ids = set()
            purchase_line_ids = purchase_line_obj.search(cursor, user, [
                ('moves', 'in', ids),
                ], context=context)
            if purchase_line_ids:
                for purchase_line in purchase_line_obj.browse(cursor, user,
                        purchase_line_ids, context=context):
                    purchase_ids.add(purchase_line.purchase.id)
            if purchase_ids:
                purchase_obj.workflow_trigger_validate(cursor, user,
                        list(purchase_ids), 'shipment_update', context=context)
        return res

    def delete(self, cursor, user, ids, context=None):
        purchase_obj = self.pool.get('purchase.purchase')
        purchase_line_obj = self.pool.get('purchase.line')

        if isinstance(ids, (int, long)):
            ids = [ids]

        purchase_ids = set()
        purchase_line_ids = purchase_line_obj.search(cursor, user, [
            ('moves', 'in', ids),
            ], context=context)

        res = super(Move, self).delete(cursor, user, ids, context=context)

        if purchase_line_ids:
            for purchase_line in purchase_line_obj.browse(cursor, user,
                    purchase_line_ids, context=context):
                purchase_ids.add(purchase_line.purchase.id)
            if purchase_ids:
                purchase_obj.workflow_trigger_validate(cursor, user,
                        list(purchase_ids), 'shipment_update', context=context)
        return res
Move()


class Invoice(ModelSQL, ModelView):
    _name = 'account.invoice'

    purchase_exception_state = fields.Function('get_purchase_exception_state',
            type='selection',
            selection=[('', ''),
                       ('ignored', 'Ignored'),
                       ('recreated', 'Recreated')],
            string='Exception State')

    def __init__(self):
        super(Invoice, self).__init__()
        self._error_messages.update({
                'delete_purchase_invoice': 'You can not delete invoices ' \
                    'that come from a purchase!',
                'reset_invoice_purchase': 'You cannot reset to draft ' \
                        'an invoice generated by a purchase.',
            })

    def button_draft(self, cursor, user, ids, context=None):
        purchase_obj = self.pool.get('purchase.purchase')
        purchase_ids = purchase_obj.search(
            cursor, user, [('invoices', 'in', ids)], context=context)

        if purchase_ids:
            self.raise_user_error(cursor, 'reset_invoice_purchase')

        return super(Invoice, self).button_draft(
            cursor, user, ids, context=context)

    def get_purchase_exception_state(self, cursor, user, ids, name, arg,
                                     context=None):
        purchase_obj = self.pool.get('purchase.purchase')
        purchase_ids = purchase_obj.search(
            cursor, user, [('invoices', 'in', ids)], context=context)

        purchases = purchase_obj.browse(
            cursor, user, purchase_ids, context=context)

        recreated_ids = tuple(i.id for p in purchases for i in p.invoices_recreated)
        ignored_ids = tuple(i.id for p in purchases for i in p.invoices_ignored)

        res = {}.fromkeys(ids, '')
        for invoice in self.browse(cursor, user, ids, context=context):
            if invoice.id in recreated_ids:
                res[invoice.id] = 'recreated'
            elif invoice.id in ignored_ids:
                res[invoice.id] = 'ignored'

        return res

    def delete(self, cursor, user, ids, context=None):
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        cursor.execute('SELECT id FROM purchase_invoices_rel ' \
                'WHERE invoice IN (' + ','.join(('%s',) * len(ids)) + ')',
                ids)
        if cursor.fetchone():
            self.raise_user_error(cursor, 'delete_purchase_invoice',
                    context=context)
        return super(Invoice, self).delete(cursor, user, ids,
                context=context)

Invoice()


class OpenSupplier(Wizard):
    'Open Suppliers'
    _name = 'purchase.open_supplier'
    states = {
        'init': {
            'result': {
                'type': 'action',
                'action': '_action_open',
                'state': 'end',
            },
        },
    }

    def _action_open(self, cursor, user, datas, context=None):
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')
        wizard_obj = self.pool.get('ir.action.wizard')

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_party_form'),
            ('module', '=', 'party'),
            ('inherit', '=', False),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id,
                context=context)
        cursor.execute("SELECT DISTINCT(party) FROM purchase_purchase")
        supplier_ids = [line[0] for line in cursor.fetchall()]
        res['domain'] = str([('id', 'in', supplier_ids)])

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_open_supplier'),
            ('module', '=', 'purchase'),
            ('inherit', '=', False),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        wizard = wizard_obj.browse(cursor, user, model_data.db_id,
                context=context)

        res['name'] = wizard.name
        return res

OpenSupplier()


class HandleShipmentExceptionAsk(ModelView):
    'Shipment Exception Ask'
    _name = 'purchase.handle.shipment.exception.ask'
    _description = __doc__

    recreate_moves = fields.Many2Many(
        'stock.move', None, None, 'Recreate Moves',
        domain=["('id', 'in', domain_moves)"], depends=['domain_moves'],
        help='The selected moves will be recreated. '\
            'The other ones will be ignored.')
    domain_moves = fields.Many2Many(
        'stock.move', None, None, 'Domain Moves')

    def init(self, cursor, module_name):
        # Migration from 1.2: packing renamed into shipment
        cursor.execute("UPDATE ir_model "\
                "SET model = REPLACE(model, 'packing', 'shipment') "\
                "WHERE model like '%%packing%%' AND module = %s",
                (module_name,))
        super(HandleShipmentExceptionAsk, self).init(cursor, module_name)

    def default_recreate_moves(self, cursor, user, context=None):
        return self.default_domain_moves(cursor, user, context=context)

    def default_domain_moves(self, cursor, user, context=None):
        purchase_line_obj = self.pool.get('purchase.line')
        active_id = context and context.get('active_id')
        if not active_id:
            return []

        line_ids = purchase_line_obj.search(
            cursor, user, [('purchase', '=', active_id)],
            context=context)
        lines = purchase_line_obj.browse(cursor, user, line_ids, context=context)

        domain_moves = []
        for line in lines:
            skip_ids = set(x.id for x in line.moves_ignored + \
                               line.moves_recreated)
            for move in line.moves:
                if move.state == 'cancel' and move.id not in skip_ids:
                    domain_moves.append(move.id)

        return domain_moves

HandleShipmentExceptionAsk()

class HandleShipmentException(Wizard):
    'Handle Shipment Exception'
    _name = 'purchase.handle.shipment.exception'
    states = {
        'init': {
            'actions': [],
            'result': {
                'type': 'form',
                'object': 'purchase.handle.shipment.exception.ask',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('ok', 'Ok', 'tryton-ok', True),
                ],
            },
        },
        'ok': {
            'result': {
                'type': 'action',
                'action': '_handle_moves',
                'state': 'end',
            },
        },
    }

    def _handle_moves(self, cursor, user, data, context=None):
        purchase_obj = self.pool.get('purchase.purchase')
        purchase_line_obj = self.pool.get('purchase.line')
        move_obj = self.pool.get('stock.move')
        to_recreate = data['form']['recreate_moves'][0][1]
        domain_moves = data['form']['domain_moves'][0][1]

        line_ids = purchase_line_obj.search(
            cursor, user, [('purchase', '=', data['id'])],
            context=context)
        lines = purchase_line_obj.browse(cursor, user, line_ids, context=context)

        for line in lines:
            moves_ignored = []
            moves_recreated = []
            skip_ids = set(x.id for x in line.moves_ignored)
            skip_ids.update(x.id for x in line.moves_recreated)
            for move in line.moves:
                if move.id not in domain_moves or move.id in skip_ids:
                    continue
                if move.id in to_recreate:
                    moves_recreated.append(move.id)
                else:
                    moves_ignored.append(move.id)

            purchase_line_obj.write(
                cursor, user, line.id,
                {'moves_ignored': [('add', moves_ignored)],
                 'moves_recreated': [('add', moves_recreated)]},
                context=context)

        purchase_obj.workflow_trigger_validate(cursor, user, data['id'],
                'shipment_ok', context=context)

HandleShipmentException()


class HandleInvoiceExceptionAsk(ModelView):
    'Invoice Exception Ask'
    _name = 'purchase.handle.invoice.exception.ask'
    _description = __doc__

    recreate_invoices = fields.Many2Many(
        'account.invoice', None, None, 'Recreate Invoices',
        domain=["('id', 'in', domain_invoices)"], depends=['domain_invoices'],
        help='The selected invoices will be recreated. '\
            'The other ones will be ignored.')
    domain_invoices = fields.Many2Many(
        'account.invoice', None, None, 'Domain Invoices')

    def default_recreate_invoices(self, cursor, user, context=None):
        return self.default_domain_invoices(cursor, user, context=context)

    def default_domain_invoices(self, cursor, user, context=None):
        purchase_obj = self.pool.get('purchase.purchase')
        active_id = context and context.get('active_id')
        if not active_id:
            return []

        purchase = purchase_obj.browse(
            cursor, user, active_id, context=context)
        skip_ids = set(x.id for x in purchase.invoices_ignored)
        skip_ids.update(x.id for x in purchase.invoices_recreated)
        domain_invoices = []
        for invoice in purchase.invoices:
            if invoice.state == 'cancel' and invoice.id not in skip_ids:
                domain_invoices.append(invoice.id)

        return domain_invoices

HandleInvoiceExceptionAsk()


class HandleInvoiceException(Wizard):
    'Handle Invoice Exception'
    _name = 'purchase.handle.invoice.exception'
    states = {
        'init': {
            'actions': [],
            'result': {
                'type': 'form',
                'object': 'purchase.handle.invoice.exception.ask',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('ok', 'Ok', 'tryton-ok', True),
                ],
            },
        },
        'ok': {
            'result': {
                'type': 'action',
                'action': '_handle_invoices',
                'state': 'end',
            },
        },
    }

    def _handle_invoices(self, cursor, user, data, context=None):
        purchase_obj = self.pool.get('purchase.purchase')
        invoice_obj = self.pool.get('account.invoice')
        to_recreate = data['form']['recreate_invoices'][0][1]
        domain_invoices = data['form']['domain_invoices'][0][1]

        purchase = purchase_obj.browse(cursor, user, data['id'], context=context)

        skip_ids = set(x.id for x in purchase.invoices_ignored)
        skip_ids.update(x.id for x in purchase.invoices_recreated)
        invoices_ignored = []
        invoices_recreated = []
        for invoice in purchase.invoices:
            if invoice.id not in domain_invoices or invoice.id in skip_ids:
                continue
            if invoice.id in to_recreate:
                invoices_recreated.append(invoice.id)
            else:
                invoices_ignored.append(invoice.id)

        purchase_obj.write(
            cursor, user, purchase.id,
            {'invoices_ignored': [('add', invoices_ignored)],
             'invoices_recreated': [('add', invoices_recreated)],},
            context=context)

        purchase_obj.workflow_trigger_validate(cursor, user, data['id'],
                'invoice_ok', context=context)

HandleInvoiceException()
