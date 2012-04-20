#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime
import copy
from decimal import Decimal
from trytond.model import Workflow, ModelView, ModelSQL, fields
from trytond.modules.company import CompanyReport
from trytond.wizard import Wizard, StateAction, StateView, StateTransition, \
    Button
from trytond.backend import TableHandler
from trytond.pyson import Eval, Bool, If, PYSONEncoder
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.config import CONFIG

_STATES = {
    'readonly': Eval('state') != 'draft',
    }
_DEPENDS = ['state']


class Purchase(Workflow, ModelSQL, ModelView):
    'Purchase'
    _name = 'purchase.purchase'
    _rec_name = 'reference'
    _description = __doc__

    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': (Eval('state') != 'draft') | Eval('lines', [0]),
            },
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', 0)),
            ],
        depends=['state'], select=True)
    reference = fields.Char('Reference', size=None, readonly=True, select=True)
    supplier_reference = fields.Char('Supplier Reference', select=True)
    description = fields.Char('Description', size=None, states=_STATES,
        depends=_DEPENDS)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('quotation', 'Quotation'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancel', 'Canceled'),
    ], 'State', readonly=True, required=True)
    purchase_date = fields.Date('Purchase Date',
        states={
            'readonly': ~Eval('state').in_(['draft', 'quotation']),
            'required': ~Eval('state').in_(['draft', 'quotation', 'cancel']),
            },
        depends=['state'])
    payment_term = fields.Many2One('account.invoice.payment_term',
        'Payment Term', required=True, states=_STATES, depends=_DEPENDS)
    party = fields.Many2One('party.party', 'Party',
            required=True, states=_STATES, on_change=['party', 'payment_term'],
            select=True, depends=_DEPENDS)
    party_lang = fields.Function(fields.Char('Party Language',
        on_change_with=['party']), 'get_function_fields')
    invoice_address = fields.Many2One('party.address', 'Invoice Address',
        domain=[('party', '=', Eval('party'))], states=_STATES,
        depends=['state', 'party'])
    warehouse = fields.Many2One('stock.location', 'Warehouse',
        domain=[('type', '=', 'warehouse')], states=_STATES,
        depends=_DEPENDS)
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states={
            'readonly': ((Eval('state') != 'draft')
                | (Eval('lines', [0]) & Eval('currency'))),
            },
        depends=['state'])
    currency_digits = fields.Function(fields.Integer('Currency Digits',
        on_change_with=['currency']), 'get_function_fields')
    lines = fields.One2Many('purchase.line', 'purchase', 'Lines',
        states=_STATES, on_change=['lines', 'currency', 'party'],
        depends=_DEPENDS)
    comment = fields.Text('Comment')
    untaxed_amount = fields.Function(fields.Numeric('Untaxed',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_untaxed_amount')
    untaxed_amount_cache = fields.Numeric('Untaxed Cache',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    tax_amount = fields.Function(fields.Numeric('Tax',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_tax_amount')
    tax_amount_cache = fields.Numeric('Tax Cache',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    total_amount = fields.Function(fields.Numeric('Total',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_total_amount')
    total_amount_cache = fields.Numeric('Total Cache',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    invoice_method = fields.Selection([
            ('manual', 'Manual'),
            ('order', 'Based On Order'),
            ('shipment', 'Based On Shipment'),
            ], 'Invoice Method', required=True, states=_STATES,
        depends=_DEPENDS)
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

    def __init__(self):
        super(Purchase, self).__init__()
        self._order.insert(0, ('purchase_date', 'DESC'))
        self._order.insert(1, ('id', 'DESC'))
        self._error_messages.update({
                'invoice_addresse_required': 'Invoice addresses must be '
                'defined for the quotation.',
                'warehouse_required': 'A warehouse must be defined for the ' \
                    'quotation.',
                'missing_account_payable': 'It misses ' \
                        'an "Account Payable" on the party "%s"!',
                'delete_cancel': 'Purchase "%s" must be cancelled before '\
                    'deletion!',
            })
        self._transitions |= set((
                ('draft', 'quotation'),
                ('quotation', 'confirmed'),
                ('confirmed', 'confirmed'),
                ('draft', 'cancel'),
                ('quotation', 'cancel'),
                ('quotation', 'draft'),
                ))
        self._buttons.update({
                'cancel': {
                    'invisible': ((Eval('state') == 'cancel')
                        | (~Eval('state').in_(['draft', 'quotation'])
                            & (Eval('invoice_state') != 'exception')
                            & (Eval('shipment_state') != 'exception'))),
                    },
                'draft': {
                    'invisible': Eval('state') != 'quotation',
                    },
                'quote': {
                    'invisible': Eval('state') != 'draft',
                    'readonly': ~Eval('lines', []),
                    },
                'confirm': {
                    'invisible': Eval('state') != 'quotation',
                    },
                })
        # The states where amounts are cached
        self._states_cached = ['confirmed', 'done', 'cancel']

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

        table = TableHandler(cursor, self, module_name)
        # Migration from 2.2: warehouse is no more required
        table.not_null_action('warehouse', 'remove')

        # Migration from 2.2: purchase_date is no more required
        table.not_null_action('purchase_date', 'remove')

        # Add index on create_date
        table = TableHandler(cursor, self, module_name)
        table.index_action('create_date', action='add')

    def default_payment_term(self):
        payment_term_obj = Pool().get('account.invoice.payment_term')
        payment_term_ids = payment_term_obj.search(self.payment_term.domain)
        if len(payment_term_ids) == 1:
            return payment_term_ids[0]

    def default_warehouse(self):
        location_obj = Pool().get('stock.location')
        location_ids = location_obj.search(self.warehouse.domain)
        if len(location_ids) == 1:
            return location_ids[0]

    def default_company(self):
        return Transaction().context.get('company')

    def default_state(self):
        return 'draft'

    def default_currency(self):
        company_obj = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            company = company_obj.browse(company)
            return company.currency.id

    def default_currency_digits(self):
        company_obj = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            company = company_obj.browse(company)
            return company.currency.digits
        return 2

    def default_invoice_method(self):
        configuration_obj = Pool().get('purchase.configuration')
        configuration = configuration_obj.browse(1)
        return configuration.purchase_invoice_method

    def default_invoice_state(self):
        return 'none'

    def default_shipment_state(self):
        return 'none'

    def on_change_party(self, vals):
        pool = Pool()
        party_obj = pool.get('party.party')
        address_obj = pool.get('party.address')
        payment_term_obj = pool.get('account.invoice.payment_term')
        currency_obj = pool.get('currency.currency')
        cursor = Transaction().cursor
        res = {
            'invoice_address': None,
            'payment_term': None,
            'currency': self.default_currency(),
            'currency_digits': self.default_currency_digits(),
        }
        if vals.get('party'):
            party = party_obj.browse(vals['party'])
            res['invoice_address'] = party_obj.address_get(party.id,
                    type='invoice')
            if party.supplier_payment_term:
                res['payment_term'] = party.supplier_payment_term.id

            subquery = cursor.limit_clause('SELECT currency '
                'FROM "' + self._table + '" '
                'WHERE party = %s '
                'ORDER BY id DESC', 10)
            cursor.execute('SELECT currency FROM (' + subquery + ') AS p '
                'GROUP BY currency '
                'ORDER BY COUNT(1) DESC', (party.id,))
            row = cursor.fetchone()
            if row:
                currency_id, = row
                currency = currency_obj.browse(currency_id)
                res['currency'] = currency.id
                res['currency_digits'] = currency.digits

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
        currency_obj = Pool().get('currency.currency')
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
        party_obj = Pool().get('party.party')
        if vals.get('party'):
            party = party_obj.browse(vals['party'])
            if party.lang:
                return party.lang.code
        return CONFIG['language']

    def get_tax_context(self, purchase):
        party_obj = Pool().get('party.party')
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
        pool = Pool()
        currency_obj = pool.get('currency.currency')
        tax_obj = pool.get('account.tax')
        invoice_obj = pool.get('account.invoice')

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
                res['untaxed_amount'] += line.get('amount') or Decimal(0)

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
                for value in taxes.itervalues():
                    res['tax_amount'] += currency_obj.round(currency, value)
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
        if 'shipments' in names:
            res['shipments'] = self.get_shipments(purchases)
        if 'moves' in names:
            res['moves'] = self.get_moves(purchases)
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
                res[purchase.id] = CONFIG['language']
        return res

    def get_untaxed_amount(self, ids, name):
        '''
        Return the untaxed amount for each purchases
        '''
        currency_obj = Pool().get('currency.currency')
        amounts = {}
        for purchase in self.browse(ids):
            if (purchase.state in self._states_cached
                    and purchase.untaxed_amount_cache is not None):
                amounts[purchase.id] = purchase.untaxed_amount_cache
                continue
            amount = sum((l.amount for l in purchase.lines
                    if l.type == 'line'), Decimal(0))
            amounts[purchase.id] = currency_obj.round(purchase.currency,
                    amount)
        return amounts

    def get_tax_amount(self, ids, name):
        '''
        Return the tax amount for each purchases
        '''
        pool = Pool()
        currency_obj = pool.get('currency.currency')
        tax_obj = pool.get('account.tax')
        invoice_obj = pool.get('account.invoice')

        amounts = {}
        for purchase in self.browse(ids):
            if (purchase.state in self._states_cached
                    and purchase.tax_amount_cache is not None):
                amounts[purchase.id] = purchase.tax_amount_cache
                continue
            context = self.get_tax_context(purchase)
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
            amount = sum((currency_obj.round(purchase.currency, tax)
                    for tax in taxes.itervalues()), Decimal(0))
            amounts[purchase.id] = currency_obj.round(purchase.currency,
                amount)
        return amounts

    def get_total_amount(self, ids, name):
        '''
        Return the total amount of each purchases
        '''
        currency_obj = Pool().get('currency.currency')
        amounts = {}
        for purchase in self.browse(ids):
            if (purchase.state in self._states_cached
                    and purchase.total_amount_cache is not None):
                amounts[purchase.id] = purchase.total_amount_cache
                continue
            amounts[purchase.id] = currency_obj.round(purchase.currency,
                    purchase.untaxed_amount + purchase.tax_amount)
        return amounts

    def get_invoice_state(self, purchase):
        '''
        Return the invoice state for the purchase.
        '''
        skip_ids = set(x.id for x in purchase.invoices_ignored)
        skip_ids.update(x.id for x in purchase.invoices_recreated)
        invoices = [i for i in purchase.invoices if i.id not in skip_ids]
        if invoices:
            if any(i.state == 'cancel' for i in invoices):
                return 'exception'
            elif all(i.state == 'paid' for i in invoices):
                return 'paid'
            else:
                return 'waiting'
        return 'none'

    def set_invoice_state(self, purchase):
        '''
        Set the invoice state.
        '''
        state = self.get_invoice_state(purchase)
        if purchase.invoice_state != state:
            self.write(purchase.id, {
                    'invoice_state': state,
                    })

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

    def get_shipment_state(self, purchase):
        '''
        Return the shipment state for the purchase.
        '''
        if purchase.moves:
            if any(l.move_exception for l in purchase.lines):
                return 'exception'
            elif all(l.move_done for l in purchase.lines):
                return 'received'
            else:
                return 'waiting'
        return 'none'

    def set_shipment_state(self, purchase):
        '''
        Set the shipment state.
        '''
        state = self.get_shipment_state(purchase)
        if purchase.shipment_state != state:
            self.write(purchase.id, {
                    'shipment_state': state,
                    })

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
        default['reference'] = None
        default['invoice_state'] = 'none'
        default['invoices'] = None
        default['invoices_ignored'] = None
        default['shipment_state'] = 'none'
        default.setdefault('purchase_date', None)
        return super(Purchase, self).copy(ids, default=default)

    def check_for_quotation(self, ids):
        purchases = self.browse(ids)
        for purchase in purchases:
            if not purchase.invoice_address:
                self.raise_user_error('invoice_addresse_required')
            for line in purchase.lines:
                if (not line.to_location
                        and line.product
                        and line.product.type in ('goods', 'assets')):
                    self.raise_user_error('warehouse_required')

    def set_reference(self, ids):
        '''
        Fill the reference field with the purchase sequence
        '''
        sequence_obj = Pool().get('ir.sequence')
        config_obj = Pool().get('purchase.configuration')

        config = config_obj.browse(1)
        purchases = self.browse(ids)
        for purchase in purchases:
            if purchase.reference:
                continue
            reference = sequence_obj.get_id(config.purchase_sequence.id)
            self.write(purchase.id, {
                'reference': reference,
                })

    def set_purchase_date(self, ids):
        date_obj = Pool().get('ir.date')
        for purchase in self.browse(ids):
            if not purchase.purchase_date:
                self.write(purchase.id, {
                    'purchase_date': date_obj.today(),
                    })

    def store_cache(self, ids):
        for purchase in self.browse(ids):
            self.write(purchase.id, {
                    'untaxed_amount_cache': purchase.untaxed_amount,
                    'tax_amount_cache': purchase.tax_amount,
                    'total_amount_cache': purchase.total_amount,
                    })

    def _get_invoice_line_purchase_line(self, purchase):
        '''
        Return invoice line values for each purchase lines

        :param purchase: a BrowseRecord of the purchase
        :return: a dictionary with invoiced purchase line id as key
            and a list of invoice line values as value
        '''
        line_obj = Pool().get('purchase.line')
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
        journal_obj = Pool().get('account.journal')

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

    def create_invoice(self, purchase):
        '''
        Create an invoice for the purchase and return the id
        '''
        pool = Pool()
        invoice_obj = pool.get('account.invoice')
        invoice_line_obj = pool.get('account.invoice.line')
        purchase_line_obj = pool.get('purchase.line')

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

        self.write(purchase.id, {
            'invoices': [('add', invoice_id)],
        })
        return invoice_id

    def create_move(self, purchase):
        '''
        Create move for each purchase lines
        '''
        line_obj = Pool().get('purchase.line')

        for line in purchase.lines:
            line_obj.create_move(line)

    def is_done(self, purchase):
        return (purchase.invoice_state == 'paid'
            and purchase.shipment_state == 'received')

    def delete(self, ids):
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Cancel before delete
        self.cancel(ids)
        for purchase in self.browse(ids):
            if purchase.state != 'cancel':
                self.raise_user_error('delete_cancel', purchase.rec_name)
        return super(Purchase, self).delete(ids)

    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(self, ids):
        self.store_cache(ids)

    @ModelView.button
    @Workflow.transition('draft')
    def draft(self, ids):
        pass

    @ModelView.button
    @Workflow.transition('quotation')
    def quote(self, ids):
        self.check_for_quotation(ids)
        self.set_reference(ids)

    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(self, ids):
        self.set_purchase_date(ids)
        self.store_cache(ids)
        self.process(ids)

    def process(self, ids):
        done = []
        for purchase in self.browse(ids):
            if purchase.state in ('done', 'cancel'):
                continue
            self.create_invoice(purchase)
            self.set_invoice_state(purchase)
            self.create_move(purchase)
            self.set_shipment_state(purchase)
            if self.is_done(purchase):
                done.append(purchase.id)
        if done:
            self.write(done, {
                    'state': 'done',
                    })

Purchase()


class PurchaseInvoice(ModelSQL):
    'Purchase - Invoice'
    _name = 'purchase.purchase-account.invoice'
    _table = 'purchase_invoices_rel'
    _description = __doc__
    purchase = fields.Many2One('purchase.purchase', 'Purchase',
            ondelete='CASCADE', select=True, required=True)
    invoice = fields.Many2One('account.invoice', 'Invoice',
            ondelete='RESTRICT', select=True, required=True)

PurchaseInvoice()


class PuchaseIgnoredInvoice(ModelSQL):
    'Purchase - Ignored Invoice'
    _name = 'purchase.purchase-ignored-account.invoice'
    _table = 'purchase_invoice_ignored_rel'
    _description = __doc__
    purchase = fields.Many2One('purchase.purchase', 'Purchase',
            ondelete='CASCADE', select=True, required=True)
    invoice = fields.Many2One('account.invoice', 'Invoice',
            ondelete='RESTRICT', select=True, required=True)

PuchaseIgnoredInvoice()


class PurchaseRecreadtedInvoice(ModelSQL):
    'Purchase - Recreated Invoice'
    _name = 'purchase.purchase-recreated-account.invoice'
    _table = 'purchase_invoice_recreated_rel'
    _description = __doc__
    purchase = fields.Many2One('purchase.purchase', 'Purchase',
            ondelete='CASCADE', select=True, required=True)
    invoice = fields.Many2One('account.invoice', 'Invoice',
            ondelete='RESTRICT', select=True, required=True)

PurchaseRecreadtedInvoice()


class PurchaseLine(ModelSQL, ModelView):
    'Purchase Line'
    _name = 'purchase.line'
    _rec_name = 'description'
    _description = __doc__

    purchase = fields.Many2One('purchase.purchase', 'Purchase',
            ondelete='CASCADE', select=True, required=True)
    sequence = fields.Integer('Sequence', required=True)
    type = fields.Selection([
        ('line', 'Line'),
        ('subtotal', 'Subtotal'),
        ('title', 'Title'),
        ('comment', 'Comment'),
        ], 'Type', select=True, required=True)
    quantity = fields.Float('Quantity',
        digits=(16, Eval('unit_digits', 2)),
        states={
            'invisible': Eval('type') != 'line',
            'required': Eval('type') == 'line',
            'readonly': ~Eval('_parent_purchase'),
            }, on_change=['product', 'quantity', 'unit',
            '_parent_purchase.currency', '_parent_purchase.party'],
        depends=['unit_digits', 'type'])
    unit = fields.Many2One('product.uom', 'Unit',
        states={
            'required': Bool(Eval('product')),
            'invisible': Eval('type') != 'line',
            'readonly': ~Eval('_parent_purchase'),
            },
        domain=[
            If(Bool(Eval('product_uom_category')),
                ('category', '=', Eval('product_uom_category')),
                ('category', '!=', -1)),
            ],
        on_change=['product', 'quantity', 'unit', '_parent_purchase.currency',
            '_parent_purchase.party'],
        depends=['product', 'type', 'product_uom_category'])
    unit_digits = fields.Function(fields.Integer('Unit Digits',
        on_change_with=['unit']), 'get_unit_digits')
    product = fields.Many2One('product.product', 'Product',
        domain=[('purchasable', '=', True)],
        states={
            'invisible': Eval('type') != 'line',
            'readonly': ~Eval('_parent_purchase'),
            }, on_change=['product', 'unit', 'quantity', 'description',
            '_parent_purchase.party', '_parent_purchase.currency'],
        context={
            'locations': If(Bool(Eval('_parent_purchase', {}).get(
                        'warehouse')),
                [Eval('_parent_purchase', {}).get('warehouse', None)],
                []),
            'stock_date_end': Eval('_parent_purchase', {}).get(
                'purchase_date'),
            'purchasable': True,
            'stock_skip_warehouse': True,
            }, depends=['type'])
    product_uom_category = fields.Function(
        fields.Many2One('product.uom.category', 'Product Uom Category',
            on_change_with=['product']),
        'get_product_uom_category')
    unit_price = fields.Numeric('Unit Price', digits=(16, 4),
        states={
            'invisible': Eval('type') != 'line',
            'required': Eval('type') == 'line',
            }, depends=['type'])
    amount = fields.Function(fields.Numeric('Amount',
            digits=(16,
                Eval('_parent_purchase', {}).get('currency_digits', 2)),
            states={
                'invisible': ~Eval('type').in_(['line', 'subtotal']),
                'readonly': ~Eval('_parent_purchase'),
                }, on_change_with=['type', 'quantity', 'unit_price', 'unit',
                '_parent_purchase.currency'],
            depends=['type']), 'get_amount')
    description = fields.Text('Description', size=None, required=True)
    note = fields.Text('Note')
    taxes = fields.Many2Many('purchase.line-account.tax',
        'line', 'tax', 'Taxes', domain=[('parent', '=', None)],
        states={
            'invisible': Eval('type') != 'line',
            }, depends=['type'])
    invoice_lines = fields.Many2Many('purchase.line-account.invoice.line',
            'purchase_line', 'invoice_line', 'Invoice Lines', readonly=True)
    moves = fields.One2Many('stock.move', 'purchase_line', 'Moves',
            readonly=True)
    moves_ignored = fields.Many2Many('purchase.line-ignored-stock.move',
            'purchase_line', 'move', 'Ignored Moves', readonly=True)
    moves_recreated = fields.Many2Many('purchase.line-recreated-stock.move',
            'purchase_line', 'move', 'Recreated Moves', readonly=True)
    move_done = fields.Function(fields.Boolean('Moves Done'), 'get_move_done')
    move_exception = fields.Function(fields.Boolean('Moves Exception'),
            'get_move_exception')
    from_location = fields.Function(fields.Many2One('stock.location',
            'From Location'), 'get_from_location')
    to_location = fields.Function(fields.Many2One('stock.location',
            'To Location'), 'get_to_location')
    delivery_date = fields.Function(fields.Date('Delivery Date',
            on_change_with=['product', '_parent_purchase.purchase_date',
                '_parent_purchase.party']),
        'get_delivery_date')

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

    def get_move_done(self, ids, name):
        uom_obj = Pool().get('product.uom')
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
        party_obj = pool.get('party.party')
        product_obj = pool.get('product.product')
        tax_rule_obj = pool.get('account.tax.rule')

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
        if vals.get('_parent_purchase.purchase_date'):
            context2['purchase_date'] = vals['_parent_purchase.purchase_date']
        with Transaction().set_context(context2):
            res['unit_price'] = product_obj.get_purchase_price([product.id],
                    vals.get('quantity', 0))[product.id]
            if res['unit_price']:
                res['unit_price'] = res['unit_price'].quantize(
                    Decimal(1) / 10 ** self.unit_price.digits[1])
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

    def on_change_quantity(self, vals):
        product_obj = Pool().get('product.product')

        if not vals.get('product'):
            return {}
        res = {}

        context = {}
        if vals.get('_parent_purchase.currency'):
            context['currency'] = vals['_parent_purchase.currency']
        if vals.get('_parent_purchase.party'):
            context['supplier'] = vals['_parent_purchase.party']
        if vals.get('_parent_purchase.purchase_date'):
            context['purchase_date'] = vals['_parent_purchase.purchase_date']
        if vals.get('unit'):
            context['uom'] = vals['unit']
        with Transaction().set_context(context):
            res['unit_price'] = product_obj.get_purchase_price(
                    [vals['product']], vals.get('quantity', 0)
                    )[vals['product']]
            if res['unit_price']:
                res['unit_price'] = res['unit_price'].quantize(
                    Decimal(1) / 10 ** self.unit_price.digits[1])
        return res

    def on_change_unit(self, vals):
        return self.on_change_quantity(vals)

    def on_change_with_amount(self, vals):
        currency_obj = Pool().get('currency.currency')
        if vals.get('type') == 'line':
            currency = vals.get('_parent_purchase.currency')
            if currency and isinstance(currency, (int, long)):
                currency = currency_obj.browse(
                        vals['_parent_purchase.currency'])
            amount = Decimal(str(vals.get('quantity') or '0.0')) * \
                    (vals.get('unit_price') or Decimal('0.0'))
            if currency:
                return currency_obj.round(currency, amount)
            return amount
        return Decimal('0.0')

    def get_amount(self, ids, name):
        currency_obj = Pool().get('currency.currency')
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

    def get_from_location(self, ids, name):
        result = {}
        for line in self.browse(ids):
            result[line.id] = line.purchase.party.supplier_location.id
        return result

    def get_to_location(self, ids, name):
        result = {}
        for line in self.browse(ids):
            if line.purchase.warehouse:
                result[line.id] = line.purchase.warehouse.input_location.id
            else:
                result[line.id] = None
        return result

    def _compute_delivery_date(self, product, party, date):
        product_supplier_obj = Pool().get('purchase.product_supplier')
        if product and product.product_suppliers:
            for product_supplier in product.product_suppliers:
                if product_supplier.party.id == party.id:
                    return product_supplier_obj.compute_supply_date(
                        product_supplier, date=date)

    def on_change_with_delivery_date(self, values):
        pool = Pool()
        product_obj = pool.get('product.product')
        party_obj = pool.get('party.party')
        if values.get('product') and values.get('_parent_purchase.party'):
            product = product_obj.browse(values['product'])
            party = party_obj.browse(values['_parent_purchase.party'])
            return self._compute_delivery_date(product, party,
                values.get('_parent_purchase.purchase_date'))

    def get_delivery_date(self, ids, name):
        dates = {}
        for line in self.browse(ids):
            dates[line.id] = self._compute_delivery_date(line.product,
                line.purchase.party, line.purchase.purchase_date)
        return dates

    def get_invoice_line(self, line):
        '''
        Return invoice line values for purchase line

        :param line: a BrowseRecord of the purchase line
        :return: a list of invoice line values
        '''
        uom_obj = Pool().get('product.uom')
        property_obj = Pool().get('ir.property')

        res = {}
        res['sequence'] = line.sequence
        res['type'] = line.type
        res['description'] = line.description
        res['note'] = line.note
        if line.type != 'line':
            if (line.purchase.invoice_method == 'order'
                    and (all(l.quantity >= 0 for l in line.sale.lines
                            if l.type == 'line')
                        or all(l.quantity <= 0 for l in line.sale.lines
                            if l.type == 'line'))):
                return [res]
            else:
                return []
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
            return []
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
        default['moves'] = None
        default['moves_ignored'] = None
        default['moves_recreated'] = None
        default['invoice_lines'] = None
        return super(PurchaseLine, self).copy(ids, default=default)

    def get_move(self, line):
        '''
        Return move values for purchase line
        '''
        pool = Pool()
        uom_obj = pool.get('product.uom')

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
        vals['from_location'] = line.from_location.id
        vals['to_location'] = line.to_location.id
        vals['state'] = 'draft'
        vals['company'] = line.purchase.company.id
        vals['unit_price'] = line.unit_price
        vals['currency'] = line.purchase.currency.id
        vals['planned_date'] = line.delivery_date
        return vals

    def create_move(self, line):
        '''
        Create move line
        '''
        pool = Pool()
        move_obj = pool.get('stock.move')

        vals = self.get_move(line)
        if not vals:
            return
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
            ondelete='CASCADE', select=True, required=True,
            domain=[('type', '=', 'line')])
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
            select=True, required=True, domain=[('parent', '=', None)])

PurchaseLineTax()


class PurchaseLineInvoiceLine(ModelSQL):
    'Purchase Line - Invoice Line'
    _name = 'purchase.line-account.invoice.line'
    _table = 'purchase_line_invoice_lines_rel'
    _description = __doc__
    purchase_line = fields.Many2One('purchase.line', 'Purchase Line',
            ondelete='CASCADE', select=True, required=True)
    invoice_line = fields.Many2One('account.invoice.line', 'Invoice Line',
            ondelete='RESTRICT', select=True, required=True)

PurchaseLineInvoiceLine()


class PurchaseLineIgnoredMove(ModelSQL):
    'Purchase Line - Ignored Move'
    _name = 'purchase.line-ignored-stock.move'
    _table = 'purchase_line_moves_ignored_rel'
    _description = __doc__
    purchase_line = fields.Many2One('purchase.line', 'Purchase Line',
            ondelete='CASCADE', select=True, required=True)
    move = fields.Many2One('stock.move', 'Move', ondelete='RESTRICT',
            select=True, required=True)

PurchaseLineIgnoredMove()


class PurchaseLineRecreatedMove(ModelSQL):
    'Purchase Line - Ignored Move'
    _name = 'purchase.line-recreated-stock.move'
    _table = 'purchase_line_moves_recreated_rel'
    _description = __doc__
    purchase_line = fields.Many2One('purchase.line', 'Purchase Line',
            ondelete='CASCADE', select=True, required=True)
    move = fields.Many2One('stock.move', 'Move', ondelete='RESTRICT',
            select=True, required=True)

PurchaseLineRecreatedMove()


class PurchaseReport(CompanyReport):
    _name = 'purchase.purchase'

PurchaseReport()


class Template(ModelSQL, ModelView):
    _name = "product.template"

    purchasable = fields.Boolean('Purchasable', states={
            'readonly': ~Eval('active', True),
            }, depends=['active'])
    product_suppliers = fields.One2Many('purchase.product_supplier',
        'product', 'Suppliers', states={
            'readonly': ~Eval('active', True),
            'invisible': (~Eval('purchasable', False)
                | ~Eval('context', {}).get('company', 0)),
            }, depends=['active', 'purchasable'])
    purchase_uom = fields.Many2One('product.uom', 'Purchase UOM', states={
            'readonly': ~Eval('active'),
            'invisible': ~Eval('purchasable'),
            'required': Eval('purchasable', False),
            },
        domain=[('category', '=', Eval('default_uom_category'))],
        on_change_with=['default_uom', 'purchase_uom', 'purchasable'],
        depends=['active', 'purchasable', 'default_uom_category'])

    def __init__(self):
        super(Template, self).__init__()
        self._error_messages.update({
                'change_purchase_uom': 'Purchase prices are based ' \
                    'on the purchase uom, are you sure to change it?',
            })
        self.account_expense = copy.copy(self.account_expense)
        self.account_expense.states = copy.copy(self.account_expense.states)
        required = ~Eval('account_category') & Eval('purchasable', False)
        if not self.account_expense.states.get('required'):
            self.account_expense.states['required'] = required
        else:
            self.account_expense.states['required'] = (
                self.account_expense.states['required'] | required)
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
        uom_obj = Pool().get('product.uom')
        res = None

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
        pool = Pool()
        uom_obj = pool.get('product.uom')
        user_obj = pool.get('res.user')
        currency_obj = pool.get('currency.currency')
        date_obj = pool.get('ir.date')

        today = date_obj.today()
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
            default_currency = (user.company.currency.id if user.company
                else None)
            if not uom:
                uom = default_uom
            if (Transaction().context.get('supplier')
                    and product.product_suppliers):
                supplier_id = Transaction().context['supplier']
                for product_supplier in product.product_suppliers:
                    if product_supplier.party.id == supplier_id:
                        for price in product_supplier.prices:
                            if uom_obj.compute_qty(product.purchase_uom,
                                    price.quantity, uom) <= quantity:
                                res[product.id] = price.unit_price
                                default_uom = product.purchase_uom
                                default_currency = product_supplier.currency.id
                        break
            res[product.id] = uom_obj.compute_price(default_uom,
                    res[product.id], uom)
            if currency and default_currency:
                date = Transaction().context.get('purchase_date') or today
                with Transaction().set_context(date=date):
                    res[product.id] = currency_obj.compute(default_currency,
                        res[product.id], currency.id, round=False)
        return res

Product()


class ProductSupplier(ModelSQL, ModelView):
    'Product Supplier'
    _name = 'purchase.product_supplier'
    _description = __doc__

    product = fields.Many2One('product.template', 'Product', required=True,
            ondelete='CASCADE', select=True)
    party = fields.Many2One('party.party', 'Supplier', required=True,
            ondelete='CASCADE', select=True, on_change=['party'])
    name = fields.Char('Name', size=None, translate=True, select=True)
    code = fields.Char('Code', size=None, select=True)
    sequence = fields.Integer('Sequence', required=True)
    prices = fields.One2Many('purchase.product_supplier.price',
            'product_supplier', 'Prices')
    company = fields.Many2One('company.company', 'Company', required=True,
        ondelete='CASCADE', select=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', 0)),
            ])
    delivery_time = fields.Integer('Delivery Time', required=True,
            help="In number of days")
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        ondelete='RESTRICT')

    def __init__(self):
        super(ProductSupplier, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))

    def init(self, module_name):
        cursor = Transaction().cursor
        table = TableHandler(cursor, self, module_name)

        # Migration from 2.2 new field currency
        created_currency = table.column_exist('currency')

        super(ProductSupplier, self).init(module_name)

        # Migration from 2.2 fill currency
        if not created_currency:
            company_obj = Pool().get('company.company')
            limit = cursor.IN_MAX
            cursor.execute('SELECT count(id) FROM "' + self._table + '"')
            product_supplier_count, = cursor.fetchone()
            for offset in range(0, product_supplier_count, limit):
                cursor.execute(cursor.limit_clause(
                        'SELECT p.id, c.currency '
                        'FROM "' + self._table + '" AS p '
                        'INNER JOIN "' + company_obj._table + '" AS c '
                            'ON p.company = c.id '
                        'ORDER BY p.id',
                        limit, offset))
                for product_supplier_id, currency_id in cursor.fetchall():
                    cursor.execute('UPDATE "' + self._table + '" '
                        'SET currency = %s '
                        'WHERE id = %s', (currency_id, product_supplier_id))

    def default_company(self):
        return Transaction().context.get('company')

    def default_currency(self):
        company_obj = Pool().get('company.company')
        company = None
        if Transaction().context.get('company'):
            company = company_obj.browse(Transaction().context['company'])
            return company.currency.id

    def on_change_party(self, values):
        cursor = Transaction().cursor
        changes = {
            'currency': self.default_currency(),
            }
        if values.get('party'):
            cursor.execute('SELECT currency FROM "' + self._table + '" '
                'WHERE party = %s '
                'GROUP BY currency '
                'ORDER BY COUNT(1) DESC', (values['party'],))
            row = cursor.fetchone()
            if row:
                changes['currency'], = row
        return changes

    def compute_supply_date(self, product_supplier, date=None):
        '''
        Compute the supply date for the Product Supplier at the given date
            and the next supply date

        :param product_supplier: a BrowseRecord of the Product Supplier
        :param date: the date of the purchase if None the current date
        :return: the supply date
        '''
        date_obj = Pool().get('ir.date')

        if not date:
            date = date_obj.today()
        if not product_supplier.delivery_time:
            return datetime.date.max
        return date + datetime.timedelta(product_supplier.delivery_time)

    def compute_purchase_date(self, product_supplier, date):
        '''
        Compute the purchase date for the Product Supplier at the given date

        :param product_supplier: a BrowseRecord of the Product Supplier
        :param date: the date of the supply
        :return: the purchase date
        '''
        date_obj = Pool().get('ir.date')

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

    def default_quantity(self):
        return 0.0

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
        purchase_obj = Pool().get('purchase.purchase')
        purchase_line_obj = Pool().get('purchase.line')

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

            with Transaction().set_user(0, set_context=True):
                purchase_obj.process(purchase_ids)
        return res

    @ModelView.button
    @Workflow.transition('draft')
    def draft(self, ids):
        for shipment in self.browse(ids):
            for move in shipment.incoming_moves:
                if move.state == 'cancel' and move.purchase_line:
                    self.raise_user_error('reset_move')

        return super(ShipmentIn, self).draft(ids)

ShipmentIn()


class Move(ModelSQL, ModelView):
    _name = 'stock.move'

    purchase_line = fields.Many2One('purchase.line', 'Purchase Line',
        select=True, states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])
    purchase = fields.Function(fields.Many2One('purchase.purchase', 'Purchase',
            select=True, states={
                'invisible': ~Eval('purchase_visible', False),
                }, depends=['purchase_visible']), 'get_purchase',
        searcher='search_purchase')
    purchase_quantity = fields.Function(fields.Float('Purchase Quantity',
            digits=(16, Eval('unit_digits', 2)),
            states={
                'invisible': ~Eval('purchase_visible', False),
                },
            depends=['purchase_visible', 'unit_digits']),
        'get_purchase_fields')
    purchase_unit = fields.Function(fields.Many2One('product.uom',
            'Purchase Unit', states={
                'invisible': ~Eval('purchase_visible', False),
                }, depends=['purchase_visible']), 'get_purchase_fields')
    purchase_unit_digits = fields.Function(fields.Integer(
        'Purchase Unit Digits'), 'get_purchase_fields')
    purchase_unit_price = fields.Function(fields.Numeric('Purchase Unit Price',
            digits=(16, 4), states={
                'invisible': ~Eval('purchase_visible', False),
                }, depends=['purchase_visible']), 'get_purchase_fields')
    purchase_currency = fields.Function(fields.Many2One('currency.currency',
            'Purchase Currency', states={
                'invisible': ~Eval('purchase_visible', False),
                }, depends=['purchase_visible']), 'get_purchase_fields')
    purchase_visible = fields.Function(fields.Boolean('Purchase Visible',
        on_change_with=['from_location']), 'get_purchase_visible')
    supplier = fields.Function(fields.Many2One('party.party', 'Supplier',
        select=True), 'get_supplier', searcher='search_supplier')
    purchase_exception_state = fields.Function(fields.Selection([
        ('', ''),
        ('ignored', 'Ignored'),
        ('recreated', 'Recreated'),
        ], 'Exception State'), 'get_purchase_exception_state')

    def get_purchase(self, ids, name):
        res = {}
        for move in self.browse(ids):
            res[move.id] = None
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
                    res[name][move.id] = None
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

    def on_change_with_purchase_visible(self, vals):
        location_obj = Pool().get('stock.location')
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
            res[move.id] = None
            if move.purchase_line:
                res[move.id] = move.purchase_line.purchase.party.id
        return res

    def search_supplier(self, name, clause):
        return [('purchase_line.purchase.party',) + clause[1:]]

    def write(self, ids, vals):
        purchase_obj = Pool().get('purchase.purchase')
        purchase_line_obj = Pool().get('purchase.line')

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
                with Transaction().set_user(0, set_context=True):
                    purchase_obj.process(list(purchase_ids))
        return res

    def delete(self, ids):
        purchase_obj = Pool().get('purchase.purchase')
        purchase_line_obj = Pool().get('purchase.line')

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
                with Transaction().set_user(0, set_context=True):
                    purchase_obj.process(list(purchase_ids))
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

    @ModelView.button
    @Workflow.transition('draft')
    def draft(self, ids):
        purchase_obj = Pool().get('purchase.purchase')
        purchase_ids = purchase_obj.search([
            ('invoices', 'in', ids),
            ])

        if purchase_ids:
            self.raise_user_error('reset_invoice_purchase')

        return super(Invoice, self).draft(ids)

    def get_purchase_exception_state(self, ids, name):
        purchase_obj = Pool().get('purchase.purchase')
        purchase_ids = purchase_obj.search([
            ('invoices', 'in', ids),
            ])

        purchases = purchase_obj.browse(purchase_ids)

        recreated_ids = tuple(i.id for p in purchases
            for i in p.invoices_recreated)
        ignored_ids = tuple(i.id for p in purchases
            for i in p.invoices_ignored)

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
    start_state = 'open_'
    open_ = StateAction('party.act_party_form')

    def do_open_(self, session, action):
        pool = Pool()
        model_data_obj = pool.get('ir.model.data')
        wizard_obj = pool.get('ir.action.wizard')
        cursor = Transaction().cursor

        cursor.execute("SELECT DISTINCT(party) FROM purchase_purchase")
        supplier_ids = [line[0] for line in cursor.fetchall()]
        action['pyson_domain'] = PYSONEncoder().encode(
            [('id', 'in', supplier_ids)])

        model_data_ids = model_data_obj.search([
            ('fs_id', '=', 'act_open_supplier'),
            ('module', '=', 'purchase'),
            ('inherit', '=', None),
            ], limit=1)
        model_data = model_data_obj.browse(model_data_ids[0])
        wizard = wizard_obj.browse(model_data.db_id)

        action['name'] = wizard.name
        return action, {}

OpenSupplier()


class HandleShipmentExceptionAsk(ModelView):
    'Handle Shipment Exception'
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

HandleShipmentExceptionAsk()


class HandleShipmentException(Wizard):
    'Handle Shipment Exception'
    _name = 'purchase.handle.shipment.exception'
    start_state = 'ask'
    ask = StateView('purchase.handle.shipment.exception.ask',
        'purchase.handle_shipment_exception_ask_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Ok', 'handle', 'tryton-ok', default=True),
            ])
    handle = StateTransition()

    def default_ask(self, session, fields):
        purchase_obj = Pool().get('purchase.purchase')

        purchase = purchase_obj.browse(Transaction().context['active_id'])

        moves = []
        for line in purchase.lines:
            skip_ids = set(x.id for x in line.moves_ignored + \
                               line.moves_recreated)
            for move in line.moves:
                if move.state == 'cancel' and move.id not in skip_ids:
                    moves.append(move.id)
        return {
            'to_recreate': moves,
            'domain_moves': moves,
            }

    def transition_handle(self, session):
        pool = Pool()
        purchase_obj = pool.get('purchase.purchase')
        purchase_line_obj = pool.get('purchase.line')
        to_recreate = [x.id for x in session.ask.recreate_moves]
        domain_moves = [x.id for x in session.ask.domain_moves]

        purchase = purchase_obj.browse(Transaction().context['active_id'])

        for line in purchase.lines:
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

        purchase_obj.process([purchase.id])

HandleShipmentException()


class HandleInvoiceExceptionAsk(ModelView):
    'Handle Invoice Exception'
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

HandleInvoiceExceptionAsk()


class HandleInvoiceException(Wizard):
    'Handle Invoice Exception'
    _name = 'purchase.handle.invoice.exception'
    start_state = 'ask'
    ask = StateView('purchase.handle.invoice.exception.ask',
        'purchase.handle_invoice_exception_ask_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Ok', 'handle', 'tryton-ok', default=True),
            ])
    handle = StateTransition()

    def default_ask(self, session, fields):
        purchase_obj = Pool().get('purchase.purchase')

        purchase = purchase_obj.browse(Transaction().context['active_id'])
        skip_ids = set(x.id for x in purchase.invoices_ignored)
        skip_ids.update(x.id for x in purchase.invoices_recreated)
        invoices = []
        for invoice in purchase.invoices:
            if invoice.state == 'cancel' and invoice.id not in skip_ids:
                invoices.append(invoice.id)
        return {
            'to_recreate': invoices,
            'domain_invoices': invoices,
            }

    def transition_handle(self, session):
        purchase_obj = Pool().get('purchase.purchase')
        to_recreate = [x.id for x in session.ask.recreate_invoices]
        domain_invoices = [x.id for x in session.ask.domain_invoices]

        purchase = purchase_obj.browse(Transaction().context['active_id'])

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

        purchase_obj.process([purchase.id])

HandleInvoiceException()
