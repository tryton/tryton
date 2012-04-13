#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from __future__ import with_statement
import datetime
import copy
from decimal import Decimal
from trytond.model import ModelWorkflow, ModelView, ModelSQL, fields
from trytond.modules.company import CompanyReport
from trytond.wizard import Wizard
from trytond.backend import TableHandler
from trytond.pyson import Not, Equal, Eval, Or, Bool, If, In, Get, And, \
        PYSONEncoder
from trytond.transaction import Transaction

_STATES = {
    'readonly': Not(Equal(Eval('state'), 'draft')),
}


class Purchase(ModelWorkflow, ModelSQL, ModelView):
    'Purchase'
    _name = 'purchase.purchase'
    _description = __doc__

    company = fields.Many2One('company.company', 'Company', required=True,
            states={
                'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                    Bool(Eval('lines'))),
            }, domain=[
                ('id', If(In('company', Eval('context', {})), '=', '!='),
                    Get(Eval('context', {}), 'company', 0)),
            ])
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
    party_lang = fields.Function(fields.Char('Party Language',
        on_change_with=['party']), 'get_function_fields')
    invoice_address = fields.Many2One('party.address', 'Invoice Address',
            domain=[('party', '=', Eval('party'))], states=_STATES)
    warehouse = fields.Many2One('stock.location', 'Warehouse',
            domain=[('type', '=', 'warehouse')], required=True, states=_STATES)
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states={
            'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                And(Bool(Eval('lines')), Bool(Eval('currency')))),
        })
    currency_digits = fields.Function(fields.Integer('Currency Digits',
        on_change_with=['currency']), 'get_function_fields')
    lines = fields.One2Many('purchase.line', 'purchase', 'Lines',
            states=_STATES, on_change=['lines', 'currency', 'party'])
    comment = fields.Text('Comment')
    untaxed_amount = fields.Function(fields.Numeric('Untaxed',
        digits=(16, Eval('currency_digits', 2))), 'get_function_fields')
    tax_amount = fields.Function(fields.Numeric('Tax',
        digits=(16, Eval('currency_digits', 2))), 'get_function_fields')
    total_amount = fields.Function(fields.Numeric('Total',
        digits=(16, Eval('currency_digits', 2))), 'get_function_fields')
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
    invoice_paid = fields.Function(fields.Boolean('Invoices Paid'),
            'get_function_fields')
    invoice_exception = fields.Function(fields.Boolean('Invoices Exception'),
            'get_function_fields')
    shipment_state = fields.Selection([
        ('none', 'None'),
        ('waiting', 'Waiting'),
        ('received', 'Received'),
        ('exception', 'Exception'),
    ], 'Shipment State', readonly=True, required=True)
    shipments = fields.Function(fields.One2Many('stock.shipment.in', None,
        'Shipments'), 'get_function_fields')
    moves = fields.Function(fields.One2Many('stock.move', None, 'Moves'),
            'get_function_fields')
    shipment_done = fields.Function(fields.Boolean('Shipment Done'),
            'get_function_fields')
    shipment_exception = fields.Function(fields.Boolean('Shipments Exception'),
            'get_function_fields')

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

    def init(self, module_name):
        cursor = Transaction().cursor
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

        super(Purchase, self).init(module_name)

        # Migration from 1.2: rename packing to shipment in
        # invoice_method values
        cursor.execute("UPDATE " + self._table + " "\
                "SET invoice_method = 'shipment' "\
                "WHERE invoice_method = 'packing'")

        # Add index on create_date
        table = TableHandler(cursor, self, module_name)
        table.index_action('create_date', action='add')

    def default_payment_term(self):
        payment_term_obj = self.pool.get('account.invoice.payment_term')
        payment_term_ids = payment_term_obj.search(self.payment_term.domain)
        if len(payment_term_ids) == 1:
            return payment_term_ids[0]
        return False

    def default_warehouse(self):
        location_obj = self.pool.get('stock.location')
        location_ids = location_obj.search(self.warehouse.domain)
        if len(location_ids) == 1:
            return location_ids[0]
        return False

    def default_company(self):
        return Transaction().context.get('company') or False

    def default_state(self):
        return 'draft'

    def default_purchase_date(self):
        date_obj = self.pool.get('ir.date')
        return date_obj.today()

    def default_currency(self):
        company_obj = self.pool.get('company.company')
        currency_obj = self.pool.get('currency.currency')
        company = Transaction().context.get('company')
        if company:
            company = company_obj.browse(company)
            return company.currency.id
        return False

    def default_currency_digits(self):
        company_obj = self.pool.get('company.company')
        company = Transaction().context.get('company')
        if company:
            company = company_obj.browse(company)
            return company.currency.digits
        return 2

    def default_invoice_method(self):
        return 'order'

    def default_invoice_state(self):
        return 'none'

    def default_shipment_state(self):
        return 'none'

    def on_change_party(self, vals):
        party_obj = self.pool.get('party.party')
        address_obj = self.pool.get('party.address')
        payment_term_obj = self.pool.get('account.invoice.payment_term')
        res = {
            'invoice_address': False,
            'payment_term': False,
        }
        if vals.get('party'):
            party = party_obj.browse(vals['party'])
            res['invoice_address'] = party_obj.address_get(party.id,
                    type='invoice')
            if party.supplier_payment_term:
                res['payment_term'] = party.supplier_payment_term.id

        if res['invoice_address']:
            res['invoice_address.rec_name'] = address_obj.browse(
                    res['invoice_address']).rec_name
        if not res['payment_term']:
            res['payment_term'] = self.default_payment_term()
        if res['payment_term']:
            res['payment_term.rec_name'] = payment_term_obj.browse(
                    res['payment_term']).rec_name
        return res

    def on_change_with_currency_digits(self, vals):
        currency_obj = self.pool.get('currency.currency')
        if vals.get('currency'):
            currency = currency_obj.browse(vals['currency'])
            return currency.digits
        return 2

    def get_currency_digits(self, purchases):
        '''
        Return the number of digits of the currency for each purchases

        :param purchases: a BrowseRecordList of purchases
        :return: a dictionary with purchase id as key and
            number of digits as value
        '''
        res = {}
        for purchase in purchases:
            res[purchase.id] = purchase.currency.digits
        return res

    def on_change_with_party_lang(self, vals):
        party_obj = self.pool.get('party.party')
        if vals.get('party'):
            party = party_obj.browse(vals['party'])
            if party.lang:
                return party.lang.code
        return 'en_US'

    def get_tax_context(self, purchase):
        party_obj = self.pool.get('party.party')
        res = {}
        if isinstance(purchase, dict):
            if purchase.get('party'):
                party = party_obj.browse(purchase['party'])
                if party.lang:
                    res['language'] = party.lang.code
        else:
            if purchase.party.lang:
                res['language'] = purchase.party.lang.code
        return res

    def on_change_lines(self, vals):
        currency_obj = self.pool.get('currency.currency')
        tax_obj = self.pool.get('account.tax')
        invoice_obj = self.pool.get('account.invoice')

        res = {
            'untaxed_amount': Decimal('0.0'),
            'tax_amount': Decimal('0.0'),
            'total_amount': Decimal('0.0'),
        }
        currency = None
        if vals.get('currency'):
            currency = currency_obj.browse(vals['currency'])
        if vals.get('lines'):
            context = self.get_tax_context(vals)
            taxes = {}
            for line in vals['lines']:
                if line.get('type', 'line') != 'line':
                    continue
                res['untaxed_amount'] += line.get('amount', Decimal('0.0'))

                with Transaction().set_context(context):
                    tax_list = tax_obj.compute(line.get('taxes', []),
                            line.get('unit_price', Decimal('0.0')),
                            line.get('quantity', 0.0))
                for tax in tax_list:
                    key, val = invoice_obj._compute_tax(tax, 'in_invoice')
                    if not key in taxes:
                        taxes[key] = val['amount']
                    else:
                        taxes[key] += val['amount']
            if currency:
                for key in taxes:
                    res['tax_amount'] += currency_obj.round(currency, taxes[key])
        if currency:
            res['untaxed_amount'] = currency_obj.round(currency,
                    res['untaxed_amount'])
            res['tax_amount'] = currency_obj.round(currency, res['tax_amount'])
        res['total_amount'] = res['untaxed_amount'] + res['tax_amount']
        if currency:
            res['total_amount'] = currency_obj.round(currency,
                    res['total_amount'])
        return res

    def get_function_fields(self, ids, names):
        '''
        Function to compute function fields for purchase ids.

        :param ids: the ids of the purchases
        :param names: the list of field name to compute
        :param args: optional argument
        :return: a dictionary with all field names as key and
            a dictionary as value with id as key
        '''
        res = {}
        purchases = self.browse(ids)
        if 'currency_digits' in names:
            res['currency_digits'] = self.get_currency_digits(purchases)
        if 'party_lang' in names:
            res['party_lang'] = self.get_party_lang(purchases)
        if 'untaxed_amount' in names:
            res['untaxed_amount'] = self.get_untaxed_amount(purchases)
        if 'tax_amount' in names:
            res['tax_amount'] = self.get_tax_amount(purchases)
        if 'total_amount' in names:
            res['total_amount'] = self.get_total_amount(purchases)
        if 'invoice_paid' in names:
            res['invoice_paid'] = self.get_invoice_paid(purchases)
        if 'invoice_exception' in names:
            res['invoice_exception'] = self.get_invoice_exception(purchases)
        if 'shipments' in names:
            res['shipments'] = self.get_shipments(purchases)
        if 'moves' in names:
            res['moves'] = self.get_moves(purchases)
        if 'shipment_done' in names:
            res['shipment_done'] = self.get_shipment_done(purchases)
        if 'shipment_exception' in names:
            res['shipment_exception'] = self.get_shipment_exception(purchases)
        return res

    def get_party_lang(self, purchases):
        '''
        Return the language code of the party of each purchases

        :param purchases: a BrowseRecordList of purchases
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

    def get_untaxed_amount(self, purchases):
        '''
        Return the untaxed amount for each purchases

        :param purchases: a BrowseRecordList of purchases
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
            res[purchase.id] = currency_obj.round(purchase.currency,
                    res[purchase.id])
        return res

    def get_tax_amount(self, purchases):
        '''
        Return the tax amount for each purchases

        :param purchases: a BrowseRecordList of purchases
        :return: a dictionary with purchase id as key and
            the tax amount as value
        '''
        currency_obj = self.pool.get('currency.currency')
        tax_obj = self.pool.get('account.tax')
        invoice_obj = self.pool.get('account.invoice')

        res = {}
        for purchase in purchases:
            context = self.get_tax_context(purchase)
            res.setdefault(purchase.id, Decimal('0.0'))
            taxes = {}
            for line in purchase.lines:
                if line.type != 'line':
                    continue
                with Transaction().set_context(context):
                    tax_list = tax_obj.compute([t.id for t in line.taxes],
                            line.unit_price, line.quantity)
                # Don't round on each line to handle rounding error
                for tax in tax_list:
                    key, val = invoice_obj._compute_tax(tax, 'in_invoice')
                    if not key in taxes:
                        taxes[key] = val['amount']
                    else:
                        taxes[key] += val['amount']
            for key in taxes:
                res[purchase.id] += currency_obj.round(purchase.currency,
                        taxes[key])
            res[purchase.id] = currency_obj.round(purchase.currency,
                    res[purchase.id])
        return res

    def get_total_amount(self, purchases):
        '''
        Return the total amount of each purchases

        :param purchases: a BrowseRecordList of purchases
        :return: a dictionary with purchase id as key and
            total amount as value
        '''
        currency_obj = self.pool.get('currency.currency')
        res = {}
        untaxed_amounts = self.get_untaxed_amount(purchases)
        tax_amounts = self.get_tax_amount(purchases)
        for purchase in purchases:
            res[purchase.id] = currency_obj.round(purchase.currency,
                    untaxed_amounts[purchase.id] + tax_amounts[purchase.id])
        return res

    def get_invoice_paid(self, purchases):
        '''
        Return if all invoices have been paid for each purchases

        :param purchases: a BrowseRecordList of purchases
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

    def get_invoice_exception(self, purchases):
        '''
        Return if there is an invoice exception for each purchases

        :param purchases: a BrowseRecordList of purchases
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

    def get_shipments(self, purchases):
        '''
        Return the shipments for the purchases.

        :param purchases: a BrowseRecordList of purchases
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

    def get_moves(self, purchases):
        '''
        Return the moves for the purchases.

        :param purchases: a BrowseRecordList of purchases
        :return: a dictionary with purchase id as key and
            a list of moves id as value
        '''
        res = {}
        for purchase in purchases:
            res[purchase.id] = []
            for line in purchase.lines:
                res[purchase.id].extend([x.id for x in line.moves])
        return res

    def get_shipment_done(self, purchases):
        '''
        Return if all the move have been done for the purchases

        :param purchases: a BrowseRecordList of purchases
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

    def get_shipment_exception(self, purchases):
        '''
        Return if there is a shipment in exception for the purchases

        :param purchases: a BrowseRecordList of purchases
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

    def get_rec_name(self, ids, name):
        if not ids:
            return {}
        res = {}
        for purchase in self.browse(ids):
            res[purchase.id] = purchase.reference or str(purchase.id) \
                    + ' - ' + purchase.party.name
        return res

    def search_rec_name(self, name, clause):
        names = clause[2].split(' - ', 1)
        ids = self.search(['OR',
            ('reference', clause[1], names[0]),
            ('supplier_reference', clause[1], names[0]),
            ], order=[])
        res = [('id', 'in', ids)]
        if len(names) != 1 and names[1]:
            res.append(('party', clause[1], names[1]))
        return res

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['state'] = 'draft'
        default['reference'] = False
        default['invoice_state'] = 'none'
        default['invoices'] = False
        default['invoices_ignored'] = False
        default['shipment_state'] = 'none'
        return super(Purchase, self).copy(ids, default=default)

    def check_for_quotation(self, purchase_id):
        purchase = self.browse(purchase_id)
        if not purchase.invoice_address:
            self.raise_user_error('invoice_addresse_required')
        return True

    def set_reference(self, purchase_id):
        sequence_obj = self.pool.get('ir.sequence')
        config_obj = self.pool.get('purchase.configuration')

        purchase = self.browse(purchase_id)

        if purchase.reference:
            return True

        config = config_obj.browse(1)
        reference = sequence_obj.get_id(config.purchase_sequence.id)
        self.write(purchase_id, {
            'reference': reference,
            })
        return True

    def set_purchase_date(self, purchase_id):
        date_obj = self.pool.get('ir.date')

        self.write(purchase_id, {
            'purchase_date': date_obj.today(),
            })
        return True

    def _get_invoice_line_purchase_line(self, purchase):
        '''
        Return invoice line values for each purchase lines

        :param purchase: a BrowseRecord of the purchase
        :return: a dictionary with invoiced purchase line id as key
            and a list of invoice line values as value
        '''
        line_obj = self.pool.get('purchase.line')
        res = {}
        for line in purchase.lines:
            val = line_obj.get_invoice_line(line)
            if val:
                res[line.id] = val
        return res

    def _get_invoice_purchase(self, purchase):
        '''
        Return invoice values for purchase

        :param purchase: the BrowseRecord of the purchase

        :return: a dictionary with purchase fields as key and
            purchase values as value
        '''
        journal_obj = self.pool.get('account.journal')

        journal_id = journal_obj.search([
            ('type', '=', 'expense'),
            ], limit=1)
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

    def create_invoice(self, purchase_id):
        '''
        Create invoice for the purchase id

        :param purchase_id: the id of the purchase
        :return: the id of the invoice or None
        '''
        invoice_obj = self.pool.get('account.invoice')
        invoice_line_obj = self.pool.get('account.invoice.line')
        purchase_line_obj = self.pool.get('purchase.line')

        purchase = self.browse(purchase_id)

        if not purchase.party.account_payable:
            self.raise_user_error('missing_account_payable',
                    error_args=(purchase.party.rec_name,))

        invoice_lines = self._get_invoice_line_purchase_line(purchase)
        if not invoice_lines:
            return

        vals = self._get_invoice_purchase(purchase)
        with Transaction().set_user(0, set_context=True):
            invoice_id = invoice_obj.create(vals)

        for line in purchase.lines:
            if line.id not in invoice_lines:
                continue
            for vals in invoice_lines[line.id]:
                vals['invoice'] = invoice_id
                with Transaction().set_user(0, set_context=True):
                    invoice_line_id = invoice_line_obj.create(vals)
                purchase_line_obj.write(line.id, {
                    'invoice_lines': [('add', invoice_line_id)],
                    })

        with Transaction().set_user(0, set_context=True):
            invoice_obj.update_taxes([invoice_id])

        self.write(purchase_id, {
            'invoices': [('add', invoice_id)],
        })
        return invoice_id

    def create_move(self, purchase_id):
        '''
        Create move for each purchase lines
        '''
        line_obj = self.pool.get('purchase.line')

        purchase = self.browse(purchase_id)
        for line in purchase.lines:
            line_obj.create_move(line)

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
            digits=(16, Eval('unit_digits', 2)),
            states={
                'invisible': Not(Equal(Eval('type'), 'line')),
                'required': Equal(Eval('type'), 'line'),
                'readonly': Not(Bool(Eval('_parent_purchase'))),
            }, on_change=['product', 'quantity', 'unit',
                '_parent_purchase.currency', '_parent_purchase.party'])
    unit = fields.Many2One('product.uom', 'Unit',
            states={
                'required': Bool(Eval('product')),
                'invisible': Not(Equal(Eval('type'), 'line')),
                'readonly': Not(Bool(Eval('_parent_purchase'))),
            }, domain=[
                ('category', '=',
                    (Eval('product'), 'product.default_uom.category')),
            ],
            context={
                'category': (Eval('product'), 'product.default_uom.category'),
            },
            on_change=['product', 'quantity', 'unit', '_parent_purchase.currency',
                '_parent_purchase.party'])
    unit_digits = fields.Function(fields.Integer('Unit Digits',
        on_change_with=['unit']), 'get_unit_digits')
    product = fields.Many2One('product.product', 'Product',
            domain=[('purchasable', '=', True)],
            states={
                'invisible': Not(Equal(Eval('type'), 'line')),
                'readonly': Not(Bool(Eval('_parent_purchase'))),
            }, on_change=['product', 'unit', 'quantity', 'description',
                '_parent_purchase.party', '_parent_purchase.currency'],
            context={
                'locations': If(Bool(Get(Eval('_parent_purchase', {}),
                    'warehouse')),
                    [Get(Eval('_parent_purchase', {}), 'warehouse')],
                    []),
                'stock_date_end': Get(Eval('_parent_purchase', {}),
                    'purchase_date'),
                'purchasable': True,
                'stock_skip_warehouse': True,
            })
    unit_price = fields.Numeric('Unit Price', digits=(16, 4),
            states={
                'invisible': Not(Equal(Eval('type'), 'line')),
                'required': Equal(Eval('type'), 'line'),
            })
    amount = fields.Function(fields.Numeric('Amount',
        digits=(16, Get(Eval('_parent_purchase', {}), 'currency_digits', 2)),
        states={
            'invisible': Not(In(Eval('type'), ['line', 'subtotal'])),
            'readonly': Not(Bool(Eval('_parent_purchase'))),
        }, on_change_with=['type', 'quantity', 'unit_price', 'unit',
            '_parent_purchase.currency']), 'get_amount')
    description = fields.Text('Description', size=None, required=True)
    note = fields.Text('Note')
    taxes = fields.Many2Many('purchase.line-account.tax',
            'line', 'tax', 'Taxes', domain=[('parent', '=', False)],
            states={
                'invisible': Not(Equal(Eval('type'), 'line')),
            })
    invoice_lines = fields.Many2Many('purchase.line-account.invoice.line',
            'purchase_line', 'invoice_line', 'Invoice Lines', readonly=True)
    moves = fields.One2Many('stock.move', 'purchase_line', 'Moves',
            readonly=True, select=1)
    moves_ignored = fields.Many2Many('purchase.line-ignored-stock.move',
            'purchase_line', 'move', 'Ignored Moves', readonly=True)
    moves_recreated = fields.Many2Many('purchase.line-recreated-stock.move',
            'purchase_line', 'move', 'Recreated Moves', readonly=True)
    move_done = fields.Function(fields.Boolean('Moves Done'), 'get_move_done')
    move_exception = fields.Function(fields.Boolean('Moves Exception'),
            'get_move_exception')

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

    def init(self, module_name):
        super(PurchaseLine, self).init(module_name)
        cursor = Transaction().cursor
        table = TableHandler(cursor, self, module_name)

        # Migration from 1.0 comment change into note
        if table.column_exist('comment'):
            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET note = comment')
            table.drop_column('comment', exception=True)

    def default_type(self):
        return 'line'

    def default_quantity(self):
        return 0.0

    def default_unit_price(self):
        return Decimal('0.0')

    def get_move_done(self, ids, name):
        uom_obj = self.pool.get('product.uom')
        res = {}
        for line in self.browse(ids):
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
                quantity -= uom_obj.compute_qty(move.uom, move.quantity,
                        line.unit)
            if val:
                if quantity > 0.0:
                    val = False
            res[line.id] = val
        return res

    def get_move_exception(self, ids, name):
        res = {}
        for line in self.browse(ids):
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

    def on_change_with_unit_digits(self, vals):
        uom_obj = self.pool.get('product.uom')
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
        party_obj = self.pool.get('party.party')
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        tax_rule_obj = self.pool.get('account.tax.rule')

        if not vals.get('product'):
            return {}
        res = {}

        context = {}
        party = None
        if vals.get('_parent_purchase.party'):
            party = party_obj.browse(vals['_parent_purchase.party'])
            if party.lang:
                context['language'] = party.lang.code

        product = product_obj.browse(vals['product'])

        context2 = {}
        if vals.get('_parent_purchase.currency'):
            context2['currency'] = vals['_parent_purchase.currency']
        if vals.get('_parent_purchase.party'):
            context2['supplier'] = vals['_parent_purchase.party']
        if vals.get('unit'):
            context2['uom'] = vals['unit']
        else:
            context2['uom'] = product.purchase_uom.id
        with Transaction().set_context(context2):
            res['unit_price'] = product_obj.get_purchase_price([product.id],
                    vals.get('quantity', 0))[product.id]
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
            tax_ids = tax_rule_obj.apply(party.supplier_tax_rule, False,
                    pattern)
            if tax_ids:
                res['taxes'].extend(tax_ids)

        if not vals.get('description'):
            with Transaction().set_context(context):
                res['description'] = product_obj.browse(product.id).rec_name

        category = product.purchase_uom.category
        if not vals.get('unit') \
                or vals.get('unit') not in [x.id for x in category.uoms]:
            res['unit'] = product.purchase_uom.id
            res['unit.rec_name'] = product.purchase_uom.rec_name
            res['unit_digits'] = product.purchase_uom.digits

        vals = vals.copy()
        vals['unit_price'] = res['unit_price']
        vals['type'] = 'line'
        res['amount'] = self.on_change_with_amount(vals)
        return res

    def on_change_quantity(self, vals):
        product_obj = self.pool.get('product.product')

        if not vals.get('product'):
            return {}
        res = {}

        product = product_obj.browse(vals['product'])

        context = {}
        if vals.get('_parent_purchase.currency'):
            context['currency'] = vals['_parent_purchase.currency']
        if vals.get('_parent_purchase.party'):
            context['supplier'] = vals['_parent_purchase.party']
        if vals.get('unit'):
            context['uom'] = vals['unit']
        with Transaction().set_context(context):
            res['unit_price'] = product_obj.get_purchase_price(
                    [vals['product']], vals.get('quantity', 0)
                    )[vals['product']]
        return res

    def on_change_unit(self, vals):
        return self.on_change_quantity(vals)

    def on_change_with_amount(self, vals):
        currency_obj = self.pool.get('currency.currency')
        if vals.get('type') == 'line':
            if isinstance(vals.get('_parent_purchase.currency'), (int, long)):
                currency = currency_obj.browse(
                        vals['_parent_purchase.currency'])
            else:
                currency = vals['_parent_purchase.currency']
            amount = Decimal(str(vals.get('quantity') or '0.0')) * \
                    (vals.get('unit_price') or Decimal('0.0'))
            if currency:
                return currency_obj.round(currency, amount)
            return amount
        return Decimal('0.0')

    def get_amount(self, ids, name):
        currency_obj = self.pool.get('currency.currency')
        res = {}
        for line in self.browse(ids):
            if line.type == 'line':
                res[line.id] = currency_obj.round(line.purchase.currency,
                        Decimal(str(line.quantity)) * line.unit_price)
            elif line.type == 'subtotal':
                res[line.id] = Decimal('0.0')
                for line2 in line.purchase.lines:
                    if line2.type == 'line':
                        res[line.id] += currency_obj.round(
                                line2.purchase.currency,
                                Decimal(str(line2.quantity)) * line2.unit_price)
                    elif line2.type == 'subtotal':
                        if line.id == line2.id:
                            break
                        res[line.id] = Decimal('0.0')
            else:
                res[line.id] = Decimal('0.0')
        return res

    def get_invoice_line(self, line):
        '''
        Return invoice line values for purchase line

        :param line: a BrowseRecord of the purchase line
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
                    quantity += uom_obj.compute_qty(move.uom, move.quantity,
                            line.unit)

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
                quantity -= uom_obj.compute_qty(invoice_line.unit,
                        invoice_line.quantity, line.unit)
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
                self.raise_user_error('missing_account_expense',
                        error_args=(line.product.rec_name,))
        else:
            for model in ('product.template', 'product.category'):
                res['account'] = property_obj.get('account_expense', model)
                if res['account']:
                    break
            if not res['account']:
                self.raise_user_error('missing_account_expense_property')
        return [res]

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['moves'] = False
        default['moves_ignored'] = False
        default['moves_recreated'] = False
        default['invoice_lines'] = False
        return super(PurchaseLine, self).copy(ids, default=default)

    def create_move(self, line):
        '''
        Create move line
        '''
        move_obj = self.pool.get('stock.move')
        uom_obj = self.pool.get('product.uom')
        product_supplier_obj = self.pool.get('purchase.product_supplier')

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
                quantity -= uom_obj.compute_qty(move.uom, move.quantity,
                        line.unit)
        if quantity <= 0.0:
            return
        if not line.purchase.party.supplier_location:
            self.raise_user_error('supplier_location_required')
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
                                    product_supplier,
                                    date=line.purchase.purchase_date)[0]
                    break

        with Transaction().set_user(0, set_context=True):
            move_id = move_obj.create(vals)

            self.write(line.id, {
                'moves': [('add', move_id)],
            })
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
        'readonly': Not(Bool(Eval('active'))),
        })
    product_suppliers = fields.One2Many('purchase.product_supplier',
            'product', 'Suppliers', states={
                'readonly': Not(Bool(Eval('active'))),
                'invisible': Or(Not(Bool(Eval('purchasable'))),
                    Not(Bool(Eval('company')))),
            })
    purchase_uom = fields.Many2One('product.uom', 'Purchase UOM', states={
        'readonly': Not(Bool(Eval('active'))),
        'invisible': Not(Bool(Eval('purchasable'))),
        'required': Bool(Eval('purchasable')),
        }, domain=[('category', '=', (Eval('default_uom'), 'uom.category'))],
        context={'category': (Eval('default_uom'), 'uom.category')},
        on_change_with=['default_uom', 'purchase_uom', 'purchasable'])

    def __init__(self):
        super(Template, self).__init__()
        self._error_messages.update({
                'change_purchase_uom': 'Purchase prices are based on the purchase uom, '\
                    'are you sure to change it?',
            })
        self.account_expense = copy.copy(self.account_expense)
        self.account_expense.states = copy.copy(self.account_expense.states)
        required = And(Not(Bool(Eval('account_category'))),
                Bool(Eval('purchasable')))
        if not self.account_expense.states.get('required'):
            self.account_expense.states['required'] = required
        else:
            self.account_expense.states['required'] = \
                    Or(self.account_expense.states['required'],
                            required)
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

    def default_purchasable(self):
        return Transaction().context.get('purchasable') or False

    def on_change_with_purchase_uom(self, vals):
        uom_obj = self.pool.get('product.uom')
        res = False

        if vals.get('default_uom'):
            default_uom = uom_obj.browse(vals['default_uom'])
            if vals.get('purchase_uom'):
                purchase_uom = uom_obj.browse(vals['purchase_uom'])
                if default_uom.category.id == purchase_uom.category.id:
                    res = purchase_uom.id
                else:
                    res = default_uom.id
            else:
                res = default_uom.id
        return res

    def write(self, ids, vals):
        if vals.get("purchase_uom"):
            templates = self.browse(ids)
            for template in templates:
                if not template.purchase_uom:
                    continue
                if template.purchase_uom.id == vals["purchase_uom"]:
                    continue
                for product in template.products:
                    if not product.product_suppliers:
                        continue
                    self.raise_user_warning(
                            '%s@product_template' % template.id,
                            'change_purchase_uom')

        return super(Template, self).write(ids, vals)

Template()


class Product(ModelSQL, ModelView):
    _name = 'product.product'

    def get_purchase_price(self, ids, quantity=0):
        '''
        Return purchase price for product ids.
        The context that can have as keys:
            uom: the unit of measure
            supplier: the supplier party id
            currency: the currency id for the returned price

        :param ids: the product ids
        :param quantity: the quantity of products
        :return: a dictionary with for each product ids keys the computed price
        '''
        uom_obj = self.pool.get('product.uom')
        user_obj = self.pool.get('res.user')
        currency_obj = self.pool.get('currency.currency')

        res = {}

        uom = None
        if Transaction().context.get('uom'):
            uom = uom_obj.browse(Transaction().context['uom'])

        currency = None
        if Transaction().context.get('currency'):
            currency = currency_obj.browse(Transaction().context['currency'])

        user = user_obj.browse(Transaction().user)

        for product in self.browse(ids):
            res[product.id] = product.cost_price
            default_uom = product.default_uom
            if not uom:
                uom = default_uom
            if Transaction().context.get('supplier') and product.product_suppliers:
                supplier_id = Transaction().context['supplier']
                for product_supplier in product.product_suppliers:
                    if product_supplier.party.id == supplier_id:
                        for price in product_supplier.prices:
                            if uom_obj.compute_qty(product.purchase_uom,
                                    price.quantity, uom) <= quantity:
                                res[product.id] = price.unit_price
                                default_uom = product.purchase_uom
                        break
            res[product.id] = uom_obj.compute_price(default_uom,
                    res[product.id], uom)
            if currency and user.company:
                if user.company.currency.id != currency.id:
                    res[product.id] = currency_obj.compute(
                            user.company.currency, res[product.id], currency)
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
            domain=[
                ('id', If(In('company', Eval('context', {})), '=', '!='),
                    Get(Eval('context', {}), 'company', 0)),
            ])
    delivery_time = fields.Integer('Delivery Time',
            help="In number of days")

    def __init__(self):
        super(ProductSupplier, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))

    def default_company(self):
        return Transaction().context.get('company') or False

    def compute_supply_date(self, product_supplier, date=None):
        '''
        Compute the supply date for the Product Supplier at the given date
            and the next supply date

        :param product_supplier: a BrowseRecord of the Product Supplier
        :param date: the date of the purchase if None the current date
        :return: a tuple with the supply date and the next one
        '''
        date_obj = self.pool.get('ir.date')

        if not date:
            date = date_obj.today()
        next_date = date + datetime.timedelta(1)
        return (date + datetime.timedelta(product_supplier.delivery_time),
                next_date + datetime.timedelta(product_supplier.delivery_time))

    def compute_purchase_date(self, product_supplier, date):
        '''
        Compute the purchase date for the Product Supplier at the given date

        :param product_supplier: a BrowseRecord of the Product Supplier
        :param date: the date of the supply
        :return: the purchase date
        '''
        date_obj = self.pool.get('ir.date')

        if not product_supplier.delivery_time:
            return date_obj.today()
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

    def default_currency(self):
        company_obj = self.pool.get('company.company')
        currency_obj = self.pool.get('currency.currency')
        company = None
        if Transaction().context.get('company'):
            company = company_obj.browse(Transaction().context['company'])
            return company.currency.id
        return False

ProductSupplierPrice()


class ShipmentIn(ModelSQL, ModelView):
    _name = 'stock.shipment.in'

    def __init__(self):
        super(ShipmentIn, self).__init__()
        self.incoming_moves = copy.copy(self.incoming_moves)
        add_remove = [
            ('supplier', '=', Eval('supplier')),
        ]
        if not self.incoming_moves.add_remove:
            self.incoming_moves.add_remove = add_remove
        else:
            self.incoming_moves.add_remove = \
                    copy.copy(self.incoming_moves.add_remove)
            self.incoming_moves.add_remove = [
                add_remove,
                self.incoming_moves.add_remove,
            ]
        self._reset_columns()

        self._error_messages.update({
                'reset_move': 'You cannot reset to draft a move generated '\
                    'by a purchase.',
            })

    def write(self, ids, vals):
        purchase_obj = self.pool.get('purchase.purchase')
        purchase_line_obj = self.pool.get('purchase.line')

        res = super(ShipmentIn, self).write(ids, vals)

        if 'state' in vals and vals['state'] in ('received', 'cancel'):
            purchase_ids = []
            move_ids = []
            if isinstance(ids, (int, long)):
                ids = [ids]
            for shipment in self.browse(ids):
                move_ids.extend([x.id for x in shipment.incoming_moves])

            purchase_line_ids = purchase_line_obj.search([
                ('moves', 'in', move_ids),
                ])
            if purchase_line_ids:
                for purchase_line in purchase_line_obj.browse(
                        purchase_line_ids):
                    if purchase_line.purchase.id not in purchase_ids:
                        purchase_ids.append(purchase_line.purchase.id)

            purchase_obj.workflow_trigger_validate(purchase_ids,
                    'shipment_update')
        return res

    def button_draft(self, ids):
        for shipment in self.browse(ids):
            for move in shipment.incoming_moves:
                if move.state == 'cancel' and move.purchase_line:
                    self.raise_user_error('reset_move')

        return super(ShipmentIn, self).button_draft(ids)

ShipmentIn()


class Move(ModelSQL, ModelView):
    _name = 'stock.move'

    purchase_line = fields.Many2One('purchase.line', 'Purchase Line', select=1,
            states={
                'readonly': Not(Equal(Eval('state'), 'draft')),
            })
    purchase = fields.Function(fields.Many2One('purchase.purchase', 'Purchase',
        select=1, states={
            'invisible': Not(Bool(Eval('purchase_visible'))),
        }, depends=['purchase_visible']), 'get_purchase',
        searcher='search_purchase')
    purchase_quantity = fields.Function(fields.Float('Purchase Quantity',
        digits=(16, Eval('unit_digits', 2)), states={
            'invisible': Not(Bool(Eval('purchase_visible'))),
        }, depends=['purchase_visible']), 'get_purchase_fields')
    purchase_unit = fields.Function(fields.Many2One('product.uom',
        'Purchase Unit', states={
            'invisible': Not(Bool(Eval('purchase_visible'))),
        }, depends=['purchase_visible']), 'get_purchase_fields')
    purchase_unit_digits = fields.Function(fields.Integer(
        'Purchase Unit Digits'), 'get_purchase_fields')
    purchase_unit_price = fields.Function(fields.Numeric('Purchase Unit Price',
        digits=(16, 4), states={
            'invisible': Not(Bool(Eval('purchase_visible'))),
        }, depends=['purchase_visible']), 'get_purchase_fields')
    purchase_currency = fields.Function(fields.Many2One('currency.currency',
        'Purchase Currency', states={
            'invisible': Not(Bool(Eval('purchase_visible'))),
        }, depends=['purchase_visible']), 'get_purchase_fields')
    purchase_visible = fields.Function(fields.Boolean('Purchase Visible',
        on_change_with=['from_location']), 'get_purchase_visible')
    supplier = fields.Function(fields.Many2One('party.party', 'Supplier',
        select=1), 'get_supplier', searcher='search_supplier')
    purchase_exception_state = fields.Function(fields.Selection([
        ('', ''),
        ('ignored', 'Ignored'),
        ('recreated', 'Recreated'),
        ], 'Exception State'), 'get_purchase_exception_state')

    def get_purchase(self, ids, name):
        res = {}
        for move in self.browse(ids):
            res[move.id] = False
            if move.purchase_line:
                res[move.id] = move.purchase_line.purchase.id
        return res

    def get_purchase_exception_state(self, ids, name):
        res = {}.fromkeys(ids, '')
        for move in self.browse(ids):
            if not move.purchase_line:
                continue
            if move.id in (x.id for x in move.purchase_line.moves_recreated):
                res[move.id] = 'recreated'
            if move.id in (x.id for x in move.purchase_line.moves_ignored):
                res[move.id] = 'ignored'
        return res

    def search_purchase(self, name, clause):
        return [('purchase_line.' + name,) + clause[1:]]

    def get_purchase_fields(self, ids, names):
        res = {}
        for name in names:
            res[name] = {}

        for move in self.browse(ids):
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

    def default_purchase_visible(self):
        from_location = self.default_from_location()
        vals = {
            'from_location': from_location,
        }
        return self.on_change_with_purchase_visible(vals)

    def on_change_with_purchase_visible(self, vals):
        location_obj = self.pool.get('stock.location')
        if vals.get('from_location'):
            from_location = location_obj.browse(vals['from_location'])
            if from_location.type == 'supplier':
                return True
        return False

    def get_purchase_visible(self, ids, name):
        res = {}
        for move in self.browse(ids):
            res[move.id] = False
            if move.from_location.type == 'supplier':
                res[move.id] = True
        return res

    def get_supplier(self, ids, name):
        res = {}
        for move in self.browse(ids):
            res[move.id] = False
            if move.purchase_line:
                res[move.id] = move.purchase_line.purchase.party.id
        return res

    def search_supplier(self, name, clause):
        return [('purchase_line.purchase.party',) + clause[1:]]

    def write(self, ids, vals):
        purchase_obj = self.pool.get('purchase.purchase')
        purchase_line_obj = self.pool.get('purchase.line')

        res = super(Move, self).write(ids, vals)
        if 'state' in vals and vals['state'] in ('cancel',):
            if isinstance(ids, (int, long)):
                ids = [ids]
            purchase_ids = set()
            purchase_line_ids = purchase_line_obj.search([
                ('moves', 'in', ids),
                ])
            if purchase_line_ids:
                for purchase_line in purchase_line_obj.browse(
                        purchase_line_ids):
                    purchase_ids.add(purchase_line.purchase.id)
            if purchase_ids:
                purchase_obj.workflow_trigger_validate(list(purchase_ids),
                        'shipment_update')
        return res

    def delete(self, ids):
        purchase_obj = self.pool.get('purchase.purchase')
        purchase_line_obj = self.pool.get('purchase.line')

        if isinstance(ids, (int, long)):
            ids = [ids]

        purchase_ids = set()
        purchase_line_ids = purchase_line_obj.search([
            ('moves', 'in', ids),
            ])

        res = super(Move, self).delete(ids)

        if purchase_line_ids:
            for purchase_line in purchase_line_obj.browse(purchase_line_ids):
                purchase_ids.add(purchase_line.purchase.id)
            if purchase_ids:
                purchase_obj.workflow_trigger_validate(list(purchase_ids),
                        'shipment_update')
        return res
Move()


class Invoice(ModelSQL, ModelView):
    _name = 'account.invoice'

    purchase_exception_state = fields.Function(fields.Selection([
        ('', ''),
        ('ignored', 'Ignored'),
        ('recreated', 'Recreated'),
        ], 'Exception State'), 'get_purchase_exception_state')

    def __init__(self):
        super(Invoice, self).__init__()
        self._error_messages.update({
                'delete_purchase_invoice': 'You can not delete invoices ' \
                    'that come from a purchase!',
                'reset_invoice_purchase': 'You cannot reset to draft ' \
                        'an invoice generated by a purchase.',
            })

    def button_draft(self, ids):
        purchase_obj = self.pool.get('purchase.purchase')
        purchase_ids = purchase_obj.search([
            ('invoices', 'in', ids),
            ])

        if purchase_ids:
            self.raise_user_error('reset_invoice_purchase')

        return super(Invoice, self).button_draft(ids)

    def get_purchase_exception_state(self, ids, name):
        purchase_obj = self.pool.get('purchase.purchase')
        purchase_ids = purchase_obj.search([
            ('invoices', 'in', ids),
            ])

        purchases = purchase_obj.browse(purchase_ids)

        recreated_ids = tuple(i.id for p in purchases for i in p.invoices_recreated)
        ignored_ids = tuple(i.id for p in purchases for i in p.invoices_ignored)

        res = {}.fromkeys(ids, '')
        for invoice in self.browse(ids):
            if invoice.id in recreated_ids:
                res[invoice.id] = 'recreated'
            elif invoice.id in ignored_ids:
                res[invoice.id] = 'ignored'

        return res

    def delete(self, ids):
        cursor = Transaction().cursor
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        cursor.execute('SELECT id FROM purchase_invoices_rel ' \
                'WHERE invoice IN (' + ','.join(('%s',) * len(ids)) + ')',
                ids)
        if cursor.fetchone():
            self.raise_user_error('delete_purchase_invoice')
        return super(Invoice, self).delete(ids)

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

    def _action_open(self, datas):
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')
        wizard_obj = self.pool.get('ir.action.wizard')
        cursor = Transaction().cursor

        act_window_id = model_data_obj.get_id('party', 'act_party_form')
        res = act_window_obj.read(act_window_id)
        cursor.execute("SELECT DISTINCT(party) FROM purchase_purchase")
        supplier_ids = [line[0] for line in cursor.fetchall()]
        res['pyson_domain'] = PYSONEncoder().encode(
                [('id', 'in', supplier_ids)])

        model_data_ids = model_data_obj.search([
            ('fs_id', '=', 'act_open_supplier'),
            ('module', '=', 'purchase'),
            ('inherit', '=', False),
            ], limit=1)
        model_data = model_data_obj.browse(model_data_ids[0])
        wizard = wizard_obj.browse(model_data.db_id)

        res['name'] = wizard.name
        return res

OpenSupplier()


class HandleShipmentExceptionAsk(ModelView):
    'Shipment Exception Ask'
    _name = 'purchase.handle.shipment.exception.ask'
    _description = __doc__

    recreate_moves = fields.Many2Many(
        'stock.move', None, None, 'Recreate Moves',
        domain=[('id', 'in', Eval('domain_moves'))], depends=['domain_moves'],
        help='The selected moves will be recreated. '\
            'The other ones will be ignored.')
    domain_moves = fields.Many2Many(
        'stock.move', None, None, 'Domain Moves')

    def init(self, module_name):
        cursor = Transaction().cursor
        # Migration from 1.2: packing renamed into shipment
        cursor.execute("UPDATE ir_model "\
                "SET model = REPLACE(model, 'packing', 'shipment') "\
                "WHERE model like '%%packing%%' AND module = %s",
                (module_name,))
        super(HandleShipmentExceptionAsk, self).init(module_name)

    def default_recreate_moves(self):
        return self.default_domain_moves()

    def default_domain_moves(self):
        purchase_line_obj = self.pool.get('purchase.line')
        active_id = Transaction().context.get('active_id')
        if not active_id:
            return []

        line_ids = purchase_line_obj.search([
            ('purchase', '=', active_id),
            ])
        lines = purchase_line_obj.browse(line_ids)

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

    def _handle_moves(self, data):
        purchase_obj = self.pool.get('purchase.purchase')
        purchase_line_obj = self.pool.get('purchase.line')
        move_obj = self.pool.get('stock.move')
        to_recreate = data['form']['recreate_moves'][0][1]
        domain_moves = data['form']['domain_moves'][0][1]

        line_ids = purchase_line_obj.search([
            ('purchase', '=', data['id']),
            ])
        lines = purchase_line_obj.browse(line_ids)

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

            purchase_line_obj.write(line.id, {
                'moves_ignored': [('add', moves_ignored)],
                'moves_recreated': [('add', moves_recreated)],
                })

        purchase_obj.workflow_trigger_validate(data['id'], 'shipment_ok')

HandleShipmentException()


class HandleInvoiceExceptionAsk(ModelView):
    'Invoice Exception Ask'
    _name = 'purchase.handle.invoice.exception.ask'
    _description = __doc__

    recreate_invoices = fields.Many2Many(
        'account.invoice', None, None, 'Recreate Invoices',
        domain=[('id', 'in', Eval('domain_invoices'))],
        depends=['domain_invoices'],
        help='The selected invoices will be recreated. '\
            'The other ones will be ignored.')
    domain_invoices = fields.Many2Many(
        'account.invoice', None, None, 'Domain Invoices')

    def default_recreate_invoices(self):
        return self.default_domain_invoices()

    def default_domain_invoices(self):
        purchase_obj = self.pool.get('purchase.purchase')
        active_id = Transaction().context.get('active_id')
        if not active_id:
            return []

        purchase = purchase_obj.browse(active_id)
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

    def _handle_invoices(self, data):
        purchase_obj = self.pool.get('purchase.purchase')
        invoice_obj = self.pool.get('account.invoice')
        to_recreate = data['form']['recreate_invoices'][0][1]
        domain_invoices = data['form']['domain_invoices'][0][1]

        purchase = purchase_obj.browse(data['id'])

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

        purchase_obj.write(purchase.id, {
            'invoices_ignored': [('add', invoices_ignored)],
            'invoices_recreated': [('add', invoices_recreated)],
            })

        purchase_obj.workflow_trigger_validate(data['id'], 'invoice_ok')

HandleInvoiceException()
