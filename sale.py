#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import copy
from decimal import Decimal
import datetime
from itertools import groupby
from functools import partial
from trytond.model import Workflow, ModelView, ModelSQL, fields
from trytond.modules.company import CompanyReport
from trytond.wizard import Wizard, StateAction, StateView, StateTransition, \
    Button
from trytond.backend import TableHandler
from trytond.pyson import If, Eval, Bool, PYSONEncoder
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.config import CONFIG


class Sale(Workflow, ModelSQL, ModelView):
    'Sale'
    _name = 'sale.sale'
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
    reference = fields.Char('Reference', readonly=True, select=True)
    description = fields.Char('Description',
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])
    state = fields.Selection([
        ('draft', 'Draft'),
        ('quotation', 'Quotation'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('done', 'Done'),
        ('cancel', 'Canceled'),
    ], 'State', readonly=True, required=True)
    sale_date = fields.Date('Sale Date',
        states={
            'readonly': ~Eval('state').in_(['draft', 'quotation']),
            'required': ~Eval('state').in_(['draft', 'quotation', 'cancel']),
            },
        depends=['state'])
    payment_term = fields.Many2One('account.invoice.payment_term',
        'Payment Term', required=True, states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])
    party = fields.Many2One('party.party', 'Party', required=True, select=True,
        states={
            'readonly': Eval('state') != 'draft',
            }, on_change=['party', 'payment_term'],
        depends=['state'])
    party_lang = fields.Function(fields.Char('Party Language',
        on_change_with=['party']), 'get_function_fields')
    invoice_address = fields.Many2One('party.address', 'Invoice Address',
        domain=[('party', '=', Eval('party'))], states={
            'readonly': Eval('state') != 'draft',
            }, depends=['state', 'party'])
    shipment_address = fields.Many2One('party.address', 'Shipment Address',
        domain=[('party', '=', Eval('party'))], states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['party', 'state'])
    warehouse = fields.Many2One('stock.location', 'Warehouse',
        domain=[('type', '=', 'warehouse')], states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states={
            'readonly': (Eval('state') != 'draft') |
                (Eval('lines', [0]) & Eval('currency', 0)),
            },
        depends=['state'])
    currency_digits = fields.Function(fields.Integer('Currency Digits',
        on_change_with=['currency']), 'get_function_fields')
    lines = fields.One2Many('sale.line', 'sale', 'Lines', states={
            'readonly': Eval('state') != 'draft',
            }, on_change=['lines', 'currency', 'party'],
        depends=['party', 'state'])
    comment = fields.Text('Comment')
    untaxed_amount = fields.Function(fields.Numeric('Untaxed',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_untaxed_amount')
    untaxed_amount_cache = fields.Numeric('Untaxed Cache',
        digits=(16, Eval('currency_digits', 2)),
        readonly=True,
        depends=['currency_digits'])
    tax_amount = fields.Function(fields.Numeric('Tax',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_tax_amount')
    tax_amount_cache = fields.Numeric('Tax Cache',
        digits=(16, Eval('currency_digits', 2)),
        readonly=True,
        depends=['currency_digits'])
    total_amount = fields.Function(fields.Numeric('Total',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_total_amount')
    total_amount_cache = fields.Numeric('Total Tax',
        digits=(16, Eval('currency_digits', 2)),
        readonly=True,
        depends=['currency_digits'])
    invoice_method = fields.Selection([
            ('manual', 'Manual'),
            ('order', 'On Order Processed'),
            ('shipment', 'On Shipment Sent'),
            ],
        'Invoice Method', required=True, states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])
    invoice_state = fields.Selection([
            ('none', 'None'),
            ('waiting', 'Waiting'),
            ('paid', 'Paid'),
            ('exception', 'Exception'),
            ], 'Invoice State', readonly=True, required=True)
    invoices = fields.Many2Many('sale.sale-account.invoice',
            'sale', 'invoice', 'Invoices', readonly=True)
    invoices_ignored = fields.Many2Many('sale.sale-ignored-account.invoice',
            'sale', 'invoice', 'Ignored Invoices', readonly=True)
    invoices_recreated = fields.Many2Many(
        'sale.sale-recreated-account.invoice', 'sale', 'invoice',
        'Recreated Invoices', readonly=True)
    shipment_method = fields.Selection([
            ('manual', 'Manual'),
            ('order', 'On Order Processed'),
            ('invoice', 'On Invoice Paid'),
            ], 'Shipment Method', required=True,
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])
    shipment_state = fields.Selection([
            ('none', 'None'),
            ('waiting', 'Waiting'),
            ('sent', 'Sent'),
            ('exception', 'Exception'),
            ], 'Shipment State', readonly=True, required=True)
    shipments = fields.Function(fields.One2Many('stock.shipment.out', None,
        'Shipments'), 'get_shipments')
    shipment_returns = fields.Function(
        fields.One2Many('stock.shipment.out.return', None, 'Shipment Returns'),
        'get_shipment_returns')
    moves = fields.Function(fields.One2Many('stock.move', None, 'Moves'),
            'get_function_fields')

    def __init__(self):
        super(Sale, self).__init__()
        self._order.insert(0, ('sale_date', 'DESC'))
        self._order.insert(1, ('id', 'DESC'))
        self._constraints += [
            ('check_method', 'wrong_method')
        ]
        self._error_messages.update({
            'wrong_method': 'Wrong combination of method!',
            'addresses_required': 'Invoice and Shipment addresses must be '
            'defined for the quotation.',
            'warehouse_required': 'Warehouse must be defined for the ' \
                'quotation.',
            'missing_account_receivable': 'It misses '
                    'an "Account Receivable" on the party "%s"!',
            'delete_cancel': 'Sale "%s" must be cancelled before deletion!',
        })
        self._transitions |= set((
                ('draft', 'quotation'),
                ('quotation', 'confirmed'),
                ('confirmed', 'processing'),
                ('processing', 'processing'),
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
                'process': {
                    'invisible': Eval('state') != 'confirmed',
                    },
                })
        # The states where amounts are cached
        self._states_cached = ['confirmed', 'processing', 'done', 'cancel']

    def init(self, module_name):
        cursor = Transaction().cursor
        # Migration from 1.2: packing renamed into shipment
        cursor.execute("UPDATE ir_model_data "
                "SET fs_id = REPLACE(fs_id, 'packing', 'shipment') "
                "WHERE fs_id like '%%packing%%' AND module = %s",
                (module_name,))
        cursor.execute("UPDATE ir_model_field "
                "SET relation = REPLACE(relation, 'packing', 'shipment'), "
                    "name = REPLACE(name, 'packing', 'shipment') "
                "WHERE (relation like '%%packing%%' "
                    "OR name like '%%packing%%') AND module = %s",
                (module_name,))
        table = TableHandler(cursor, self, module_name)
        table.column_rename('packing_state', 'shipment_state')
        table.column_rename('packing_method', 'shipment_method')
        table.column_rename('packing_address', 'shipment_address')

        super(Sale, self).init(module_name)

        # Migration from 1.2
        cursor.execute("UPDATE " + self._table + " "
                "SET invoice_method = 'shipment' "
                "WHERE invoice_method = 'packing'")

        table = TableHandler(cursor, self, module_name)
        # Migration from 2.2
        table.not_null_action('sale_date', 'remove')

        # state confirmed splitted into confirmed and processing
        confirmed2processing = []
        for sale in self.browse(self.search([
                        ('state', '=', 'confirmed'),
                        ])):
            if sale.invoices or sale.moves:
                confirmed2processing.append(sale.id)
        if confirmed2processing:
            self.write(confirmed2processing, {'state': 'processing'})

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
            return company_obj.browse(company).currency.id

    def default_currency_digits(self):
        company_obj = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            return company_obj.browse(company).currency.digits
        return 2

    def default_invoice_method(self):
        config_obj = Pool().get('sale.configuration')
        config = config_obj.browse(1)
        return config.sale_invoice_method

    def default_invoice_state(self):
        return 'none'

    def default_shipment_method(self):
        config_obj = Pool().get('sale.configuration')
        config = config_obj.browse(1)
        return config.sale_shipment_method

    def default_shipment_state(self):
        return 'none'

    def on_change_party(self, vals):
        pool = Pool()
        party_obj = pool.get('party.party')
        address_obj = pool.get('party.address')
        payment_term_obj = pool.get('account.invoice.payment_term')
        res = {
            'invoice_address': None,
            'shipment_address': None,
            'payment_term': None,
        }
        if vals.get('party'):
            party = party_obj.browse(vals['party'])
            res['invoice_address'] = party_obj.address_get(party.id,
                    type='invoice')
            res['shipment_address'] = party_obj.address_get(party.id,
                    type='delivery')
            if party.customer_payment_term:
                res['payment_term'] = party.customer_payment_term.id

        if res['invoice_address']:
            res['invoice_address.rec_name'] = address_obj.browse(
                    res['invoice_address']).rec_name
        if res['shipment_address']:
            res['shipment_address.rec_name'] = address_obj.browse(
                    res['shipment_address']).rec_name
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

    def get_currency_digits(self, sales):
        '''
        Return the number of digits of the currency of each sales

        :param sales: a BrowseRecordList of puchases
        :return: a dictionary with sale id as key and
            number of digits as value
        '''
        res = {}
        for sale in sales:
            res[sale.id] = sale.currency.digits
        return res

    def get_tax_context(self, sale):
        party_obj = Pool().get('party.party')
        res = {}
        if isinstance(sale, dict):
            if sale.get('party'):
                party = party_obj.browse(sale['party'])
                if party.lang:
                    res['language'] = party.lang.code
        else:
            if sale.party.lang:
                res['language'] = sale.party.lang.code
        return res

    def on_change_with_party_lang(self, vals):
        party_obj = Pool().get('party.party')
        if vals.get('party'):
            party = party_obj.browse(vals['party'])
            if party.lang:
                return party.lang.code
        return CONFIG['language']

    def get_party_lang(self, sales):
        '''
        Return the code lang of the party for each sales

        :param sales: a BrowseRecordList of sales
        :return: a dictionary with sale id as key and
            code lang as value
        '''
        res = {}
        for sale in sales:
            if sale.party.lang:
                res[sale.id] = sale.party.lang.code
            else:
                res[sale.id] = CONFIG['language']
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
            taxes = {}
            for line in vals['lines']:
                if line.get('type', 'line') != 'line':
                    continue
                res['untaxed_amount'] += line.get('amount') or Decimal(0)
                tax_list = ()
                with Transaction().set_context(self.get_tax_context(vals)):
                    tax_list = tax_obj.compute(line.get('taxes', []),
                            line.get('unit_price', Decimal('0.0')),
                            line.get('quantity', 0.0))
                for tax in tax_list:
                    key, val = invoice_obj._compute_tax(tax, 'out_invoice')
                    if not key in taxes:
                        taxes[key] = val['amount']
                    else:
                        taxes[key] += val['amount']
            if currency:
                for key in taxes:
                    res['tax_amount'] += currency_obj.round(currency,
                            taxes[key])
        if currency:
            res['untaxed_amount'] = currency_obj.round(currency,
                    res['untaxed_amount'])
            res['tax_amount'] = currency_obj.round(currency,
                    res['tax_amount'])
        res['total_amount'] = res['untaxed_amount'] + res['tax_amount']
        if currency:
            res['total_amount'] = currency_obj.round(currency,
                    res['total_amount'])
        return res

    def get_function_fields(self, ids, names):
        '''
        Function to compute function fields for sale ids

        :param ids: the ids of the sales
        :param names: the list of field name to compute
        :return: a dictionary with all field names as key and
            a dictionary as value with id as key
        '''
        res = {}
        sales = self.browse(ids)
        if 'currency_digits' in names:
            res['currency_digits'] = self.get_currency_digits(sales)
        if 'party_lang' in names:
            res['party_lang'] = self.get_party_lang(sales)
        if 'moves' in names:
            res['moves'] = self.get_moves(sales)
        return res

    def get_untaxed_amount(self, ids, name):
        '''
        Compute the untaxed amount for each sales
        '''
        currency_obj = Pool().get('currency.currency')
        amounts = {}
        for sale in self.browse(ids):
            if (sale.state in self._states_cached
                    and sale.untaxed_amount_cache is not None):
                amounts[sale.id] = sale.untaxed_amount_cache
                continue
            amount = sum((l.amount for l in sale.lines if l.type == 'line'),
                Decimal(0))
            amounts[sale.id] = currency_obj.round(sale.currency, amount)
        return amounts

    def get_tax_amount(self, ids, name):
        '''
        Compute tax amount for each sales
        '''
        pool = Pool()
        currency_obj = pool.get('currency.currency')
        tax_obj = pool.get('account.tax')
        invoice_obj = pool.get('account.invoice')

        amounts = {}
        for sale in self.browse(ids):
            if (sale.state in self._states_cached
                    and sale.tax_amount_cache is not None):
                amounts[sale.id] = sale.tax_amount_cache
                continue
            context = self.get_tax_context(sale)
            taxes = {}
            for line in sale.lines:
                if line.type != 'line':
                    continue
                with Transaction().set_context(context):
                    tax_list = tax_obj.compute(
                            [t.id for t in line.taxes], line.unit_price,
                            line.quantity)
                # Don't round on each line to handle rounding error
                for tax in tax_list:
                    key, val = invoice_obj._compute_tax(tax, 'out_invoice')
                    if not key in taxes:
                        taxes[key] = val['amount']
                    else:
                        taxes[key] += val['amount']
            amount = sum((currency_obj.round(sale.currency, taxes[key])
                    for key in taxes), Decimal(0))
            amounts[sale.id] = currency_obj.round(sale.currency, amount)
        return amounts

    def get_total_amount(self, ids, name):
        '''
        Return the total amount of each sales
        '''
        currency_obj = Pool().get('currency.currency')
        amounts = {}
        for sale in self.browse(ids):
            if (sale.state in self._states_cached
                    and sale.total_amount_cache is not None):
                amounts[sale.id] = sale.total_amount_cache
                continue
            amounts[sale.id] = currency_obj.round(sale.currency,
                sale.untaxed_amount + sale.tax_amount)
        return amounts

    def get_invoice_state(self, sale):
        '''
        Return the invoice state for the sale.
        '''
        skip_ids = set(x.id for x in sale.invoices_ignored)
        skip_ids.update(x.id for x in sale.invoices_recreated)
        invoices = [i for i in sale.invoices if i.id not in skip_ids]
        if invoices:
            if any(i.state == 'cancel' for i in invoices):
                return 'exception'
            elif all(i.state == 'paid' for i in invoices):
                return 'paid'
            else:
                return 'waiting'
        return 'none'

    def set_invoice_state(self, sale):
        '''
        Set the invoice state.
        '''
        state = self.get_invoice_state(sale)
        if sale.invoice_state != state:
            self.write(sale.id, {
                    'invoice_state': state,
                    })

    def get_shipments_returns(attribute):
        "Computes the returns or shipments"
        def method(self, ids, name):
            shipments = {}
            for sale in self.browse(ids):
                shipments[sale.id] = []
                for line in sale.lines:
                    for move in line.moves:
                        ship_or_return = getattr(move, attribute)
                        if bool(ship_or_return):
                            if ship_or_return.id not in shipments[sale.id]:
                                shipments[sale.id].append(ship_or_return.id)
            return shipments
        return method

    get_shipments = get_shipments_returns('shipment_out')
    get_shipment_returns = get_shipments_returns('shipment_out_return')

    def get_moves(self, sales):
        '''
        Return move ids for each sales

        :param sales: a BrowseRecordList of sales
        :return: a dictionary with sale id as key and
            a list of move ids as value
        '''
        res = {}
        for sale in sales:
            res[sale.id] = []
            for line in sale.lines:
                res[sale.id].extend([x.id for x in line.moves])
        return res

    def get_shipment_state(self, sale):
        '''
        Return the shipment state for the sale.
        '''
        if sale.moves:
            if any(l.move_exception for l in sale.lines):
                return 'exception'
            elif all(l.move_done for l in sale.lines):
                return 'sent'
            else:
                return 'waiting'
        return 'none'

    def set_shipment_state(self, sale):
        '''
        Set the shipment state.
        '''
        state = self.get_shipment_state(sale)
        if sale.shipment_state != state:
            self.write(sale.id, {
                    'shipment_state': state,
                    })

    def check_method(self, ids):
        '''
        Check the methods.
        '''
        for sale in self.browse(ids):
            if sale.invoice_method == 'shipment' \
                    and sale.shipment_method in ('invoice', 'manual'):
                return False
            if sale.shipment_method == 'invoice' \
                    and sale.invoice_method in ('shipment', 'manual'):
                return False
        return True

    def get_rec_name(self, ids, name):
        if not ids:
            return []
        res = {}
        for sale in self.browse(ids):
            res[sale.id] = sale.reference or str(sale.id) \
                    + ' - ' + sale.party.rec_name
        return res

    def search_rec_name(self, name, clause):
        names = clause[2].split(' - ', 1)
        res = [('reference', clause[1], names[0])]
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
        default.setdefault('sale_date', None)
        return super(Sale, self).copy(ids, default=default)

    def check_for_quotation(self, ids):
        sales = self.browse(ids)
        for sale in sales:
            if not sale.invoice_address or not sale.shipment_address:
                self.raise_user_error('addresses_required')
            for line in sale.lines:
                if line.quantity >= 0:
                    location = line.from_location
                else:
                    location = line.to_location
                if (not location
                        and line.product
                        and line.product.type in ('goods', 'assets')):
                    self.raise_user_error('warehouse_required')

    def set_reference(self, ids):
        '''
        Fill the reference field with the sale sequence
        '''
        sequence_obj = Pool().get('ir.sequence')
        config_obj = Pool().get('sale.configuration')

        config = config_obj.browse(1)
        sales = self.browse(ids)
        for sale in sales:
            if sale.reference:
                continue
            reference = sequence_obj.get_id(config.sale_sequence.id)
            self.write(sale.id, {
                'reference': reference,
                })

    def set_sale_date(self, ids):
        date_obj = Pool().get('ir.date')
        for sale in self.browse(ids):
            if not sale.sale_date:
                self.write(sale.id, {
                        'sale_date': date_obj.today(),
                        })

    def store_cache(self, ids):
        for sale in self.browse(ids):
            self.write(sale.id, {
                    'untaxed_amount_cache': sale.untaxed_amount,
                    'tax_amount_cache': sale.tax_amount,
                    'total_amount_cache': sale.total_amount,
                    })

    def _get_invoice_line_sale_line(self, sale, invoice_type):
        '''
        Return invoice line values for each sale lines according to
        invoice_type
        '''
        line_obj = Pool().get('sale.line')
        res = {}
        for line in sale.lines:
            val = line_obj.get_invoice_line(line, invoice_type)
            if val:
                res[line.id] = val
        return res

    def _get_invoice_sale(self, sale, invoice_type):
        '''
        Return invoice values of type invoice_type for sale
        '''
        journal_obj = Pool().get('account.journal')

        journal_id = journal_obj.search([
            ('type', '=', 'revenue'),
            ], limit=1)
        if journal_id:
            journal_id = journal_id[0]

        res = {
            'company': sale.company.id,
            'type': invoice_type,
            'reference': sale.reference,
            'journal': journal_id,
            'party': sale.party.id,
            'invoice_address': sale.invoice_address.id,
            'currency': sale.currency.id,
            'account': sale.party.account_receivable.id,
            'payment_term': sale.payment_term.id,
            }
        return res

    def create_invoice(self, sale, invoice_type):
        '''
        Create an invoice of type invoice_type for the sale and return the id
        '''
        pool = Pool()
        invoice_obj = pool.get('account.invoice')
        invoice_line_obj = pool.get('account.invoice.line')
        sale_line_obj = pool.get('sale.line')

        if not sale.party.account_receivable:
            self.raise_user_error('missing_account_receivable',
                    error_args=(sale.party.rec_name,))

        invoice_lines = self._get_invoice_line_sale_line(sale, invoice_type)
        if not invoice_lines:
            return

        vals = self._get_invoice_sale(sale, invoice_type)
        with Transaction().set_user(0, set_context=True):
            invoice_id = invoice_obj.create(vals)

        for line in sale.lines:
            if line.id not in invoice_lines:
                continue
            for vals in invoice_lines[line.id]:
                vals['invoice'] = invoice_id
                with Transaction().set_user(0, set_context=True):
                    invoice_line_id = invoice_line_obj.create(vals)
                sale_line_obj.write(line.id, {
                    'invoice_lines': [('add', invoice_line_id)],
                    })

        with Transaction().set_user(0, set_context=True):
            invoice_obj.update_taxes([invoice_id])

        self.write(sale.id, {
            'invoices': [('add', invoice_id)],
        })
        return invoice_id

    def _get_move_sale_line(self, sale, shipment_type):
        '''
        Return a dictionary of move values for each sale lines of the right
        shipment_type
        '''
        line_obj = Pool().get('sale.line')
        res = {}
        for line in sale.lines:
            val = line_obj.get_move(line, shipment_type)
            if val:
                res[line.id] = val
        return res

    def _group_shipment_key(self, moves, move):
        '''
        The key to group moves by shipments

        :param moves: a list of moves values
        :param move: a tuple of line id and a dictionary of the move values

        :return: a list of key-value as tuples of the shipment
        '''
        sale_line_obj = Pool().get('sale.line')
        line_id, move = move
        line = sale_line_obj.browse(line_id)

        planned_date = max(m['planned_date'] for m in moves)
        return (
            ('planned_date', planned_date),
            ('warehouse', line.warehouse.id),
            )

    _group_return_key = _group_shipment_key

    def create_shipment(self, sale, shipment_type):
        '''
        Create a shipment of type shipment_type for the sale
        and return the list of created shipment ids
        '''
        pool = Pool()
        move_obj = pool.get('stock.move')
        sale_line_obj = pool.get('sale.line')

        moves = self._get_move_sale_line(sale, shipment_type)
        if not moves:
            return
        if shipment_type == 'out':
            keyfunc = partial(self._group_shipment_key, moves.values())
            move_shipment_key = 'shipment_out'
            shipment_obj = pool.get('stock.shipment.out')
        elif shipment_type == 'return':
            keyfunc = partial(self._group_return_key, moves.values())
            move_shipment_key = 'shipment_out_return'
            shipment_obj = pool.get('stock.shipment.out.return')
        moves = moves.items()
        moves = sorted(moves, key=keyfunc)

        shipments = []
        with Transaction().set_user(0, set_context=True):
            for key, grouped_moves in groupby(moves, key=keyfunc):
                values = {
                    'customer': sale.party.id,
                    'delivery_address': sale.shipment_address.id,
                    'reference': sale.reference,
                    'company': sale.company.id,
                    }
                values.update(dict(key))
                shipment_id = shipment_obj.create(values)
                shipments.append(shipment_id)
                for line_id, values in grouped_moves:
                    values[move_shipment_key] = shipment_id
                    move_id = move_obj.create(values)
                    sale_line_obj.write(line_id, {
                        'moves': [('add', move_id)],
                    })
            if shipment_type == 'out':
                shipment_obj.wait(shipments)
        return shipments

    def is_done(self, sale):
        return sale.invoice_state == 'paid' and sale.shipment_state == 'sent'

    def delete(self, ids):
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Cancel before delete
        self.cancel(ids)
        for sale in self.browse(ids):
            if sale.state != 'cancel':
                self.raise_user_error('delete_cancel', sale.rec_name)
        return super(Sale, self).delete(ids)

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
        self.set_sale_date(ids)
        self.store_cache(ids)

    @ModelView.button
    @Workflow.transition('processing')
    def process(self, ids):
        done = []
        for sale in self.browse(ids):
            if sale.state in ('done', 'cancel'):
                continue
            self.create_invoice(sale, 'out_invoice')
            self.create_invoice(sale, 'out_credit_note')
            self.set_invoice_state(sale)
            self.create_shipment(sale, 'out')
            self.create_shipment(sale, 'return')
            self.set_shipment_state(sale)
            if self.is_done(sale):
                done.append(sale.id)
        if done:
            self.write(done, {
                    'state': 'done',
                    })

Sale()


class SaleInvoice(ModelSQL):
    'Sale - Invoice'
    _name = 'sale.sale-account.invoice'
    _table = 'sale_invoices_rel'
    _description = __doc__
    sale = fields.Many2One('sale.sale', 'Sale', ondelete='CASCADE',
        select=True, required=True)
    invoice = fields.Many2One('account.invoice', 'Invoice',
            ondelete='RESTRICT', select=True, required=True)

SaleInvoice()


class SaleIgnoredInvoice(ModelSQL):
    'Sale - Ignored Invoice'
    _name = 'sale.sale-ignored-account.invoice'
    _table = 'sale_invoice_ignored_rel'
    _description = __doc__
    sale = fields.Many2One('sale.sale', 'Sale', ondelete='CASCADE',
        select=True, required=True)
    invoice = fields.Many2One('account.invoice', 'Invoice',
            ondelete='RESTRICT', select=True, required=True)

SaleIgnoredInvoice()


class SaleRecreatedInvoice(ModelSQL):
    'Sale - Recreated Invoice'
    _name = 'sale.sale-recreated-account.invoice'
    _table = 'sale_invoice_recreated_rel'
    _description = __doc__
    sale = fields.Many2One('sale.sale', 'Sale', ondelete='CASCADE',
        select=True, required=True)
    invoice = fields.Many2One('account.invoice', 'Invoice',
            ondelete='RESTRICT', select=True, required=True)

SaleRecreatedInvoice()


class SaleLine(ModelSQL, ModelView):
    'Sale Line'
    _name = 'sale.line'
    _rec_name = 'description'
    _description = __doc__

    sale = fields.Many2One('sale.sale', 'Sale', ondelete='CASCADE',
        select=True)
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
            'readonly': ~Eval('_parent_sale', {}),
            }, on_change=['product', 'quantity', 'unit',
            '_parent_sale.currency', '_parent_sale.party'],
        depends=['type', 'unit_digits'])
    unit = fields.Many2One('product.uom', 'Unit',
            states={
                'required': Bool(Eval('product')),
                'invisible': Eval('type') != 'line',
                'readonly': ~Eval('_parent_sale', {}),
            },
        domain=[
            If(Bool(Eval('product_uom_category')),
                ('category', '=', Eval('product_uom_category')),
                ('category', '!=', -1)),
            ],
        on_change=['product', 'quantity', 'unit', '_parent_sale.currency',
            '_parent_sale.party'],
        depends=['product', 'type', 'product_uom_category'])
    unit_digits = fields.Function(fields.Integer('Unit Digits',
        on_change_with=['unit']), 'get_unit_digits')
    product = fields.Many2One('product.product', 'Product',
        domain=[('salable', '=', True)],
        states={
            'invisible': Eval('type') != 'line',
            'readonly': ~Eval('_parent_sale', {}),
            },
        on_change=['product', 'unit', 'quantity', 'description',
            '_parent_sale.party', '_parent_sale.currency'],
        context={
            'locations': If(Bool(Eval('_parent_sale', {}).get('warehouse')),
                [Eval('_parent_sale', {}).get('warehouse', 0)], []),
            'stock_date_end': Eval('_parent_sale', {}).get('sale_date'),
            'salable': True,
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
            digits=(16, Eval('_parent_sale', {}).get('currency_digits', 2)),
            states={
                'invisible': ~Eval('type').in_(['line', 'subtotal']),
                'readonly': ~Eval('_parent_sale'),
                }, on_change_with=['type', 'quantity', 'unit_price', 'unit',
                '_parent_sale.currency'],
            depends=['type']), 'get_amount')
    description = fields.Text('Description', size=None, required=True)
    note = fields.Text('Note')
    taxes = fields.Many2Many('sale.line-account.tax', 'line', 'tax', 'Taxes',
        domain=[('parent', '=', None)], states={
            'invisible': Eval('type') != 'line',
            }, depends=['type'])
    invoice_lines = fields.Many2Many('sale.line-account.invoice.line',
            'sale_line', 'invoice_line', 'Invoice Lines', readonly=True)
    moves = fields.One2Many('stock.move', 'sale_line', 'Moves',
            readonly=True)
    moves_ignored = fields.Many2Many('sale.line-ignored-stock.move',
            'sale_line', 'move', 'Ignored Moves', readonly=True)
    moves_recreated = fields.Many2Many('sale.line-recreated-stock.move',
            'sale_line', 'move', 'Recreated Moves', readonly=True)
    move_done = fields.Function(fields.Boolean('Moves Done'), 'get_move_done')
    move_exception = fields.Function(fields.Boolean('Moves Exception'),
            'get_move_exception')
    warehouse = fields.Function(fields.Many2One('stock.location',
            'Warehouse'), 'get_warehouse')
    from_location = fields.Function(fields.Many2One('stock.location',
            'From Location'), 'get_from_location')
    to_location = fields.Function(fields.Many2One('stock.location',
            'To Location'), 'get_to_location')
    delivery_date = fields.Function(fields.Date('Delivery Date',
            on_change_with=['product', '_parent_sale.sale_date'],
            states={
                'invisible': Eval('type') != 'line',
                },
            depends=['type']),
        'get_delivery_date')

    def __init__(self):
        super(SaleLine, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))
        self._error_messages.update({
            'customer_location_required': 'The customer location is required!',
            'missing_account_revenue': 'It misses '
                    'an "Account Revenue" on product "%s"!',
            'missing_account_revenue_property': 'It misses '
                    'an "account Revenue" default property!',
            })

    def init(self, module_name):
        super(SaleLine, self).init(module_name)
        cursor = Transaction().cursor
        table = TableHandler(cursor, self, module_name)

        # Migration from 1.0 comment change into note
        if table.column_exist('comment'):
            cursor.execute('UPDATE "' + self._table + '" SET note = comment')
            table.drop_column('comment', exception=True)

    def default_type(self):
        return 'line'

    def default_unit_digits(self):
        return 2

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
            skip_ids = set(x.id for x in line.moves_ignored)
            skip_ids.update(x.id for x in line.moves_recreated)
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
            skip_ids = set(x.id for x in line.moves_ignored)
            skip_ids.update(x.id for x in line.moves_recreated)
            for move in line.moves:
                if move.state == 'cancel' \
                        and move.id not in skip_ids:
                    val = True
                    break
            res[line.id] = val
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

    def _get_context_sale_price(self, product, vals):
        context = {}
        if vals.get('_parent_sale.currency'):
            context['currency'] = vals['_parent_sale.currency']
        if vals.get('_parent_sale.party'):
            context['customer'] = vals['_parent_sale.party']
        if vals.get('_parent_sale.sale_date'):
            context['sale_date'] = vals['_parent_sale.sale_date']
        if vals.get('unit'):
            context['uom'] = vals['unit']
        else:
            context['uom'] = product.sale_uom.id
        return context

    def on_change_product(self, vals):
        pool = Pool()
        party_obj = pool.get('party.party')
        product_obj = pool.get('product.product')
        tax_rule_obj = pool.get('account.tax.rule')

        if not vals.get('product'):
            return {}
        res = {}

        party = None
        party_context = {}
        if vals.get('_parent_sale.party'):
            party = party_obj.browse(vals['_parent_sale.party'])
            if party.lang:
                party_context['language'] = party.lang.code

        product = product_obj.browse(vals['product'])

        with Transaction().set_context(
                self._get_context_sale_price(product, vals)):
            res['unit_price'] = product_obj.get_sale_price([product.id],
                    vals.get('quantity', 0))[product.id]
            if res['unit_price']:
                res['unit_price'] = res['unit_price'].quantize(
                    Decimal(1) / 10 ** self.unit_price.digits[1])
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
            with Transaction().set_context(party_context):
                res['description'] = product_obj.browse(product.id).rec_name

        category = product.sale_uom.category
        if not vals.get('unit') \
                or vals.get('unit') not in [x.id for x in category.uoms]:
            res['unit'] = product.sale_uom.id
            res['unit.rec_name'] = product.sale_uom.rec_name
            res['unit_digits'] = product.sale_uom.digits

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

        product = product_obj.browse(vals['product'])

        with Transaction().set_context(
                self._get_context_sale_price(product, vals)):
            res['unit_price'] = product_obj.get_sale_price([vals['product']],
                    vals.get('quantity', 0))[vals['product']]
            if res['unit_price']:
                res['unit_price'] = res['unit_price'].quantize(
                    Decimal(1) / 10 ** self.unit_price.digits[1])
        return res

    def on_change_unit(self, vals):
        return self.on_change_quantity(vals)

    def on_change_with_amount(self, vals):
        currency_obj = Pool().get('currency.currency')
        if vals.get('type') == 'line':
            currency = vals.get('_parent_sale.currency')
            if currency and isinstance(currency, (int, long)):
                currency = currency_obj.browse(vals['_parent_sale.currency'])
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
                res[line.id] = currency_obj.round(line.sale.currency,
                        Decimal(str(line.quantity)) * line.unit_price)
            elif line.type == 'subtotal':
                res[line.id] = Decimal('0.0')
                for line2 in line.sale.lines:
                    if line2.type == 'line':
                        res[line.id] += currency_obj.round(line2.sale.currency,
                                Decimal(str(line2.quantity)) *
                                        line2.unit_price)
                    elif line2.type == 'subtotal':
                        if line.id == line2.id:
                            break
                        res[line.id] = Decimal('0.0')
            else:
                res[line.id] = Decimal('0.0')
        return res

    def get_warehouse(self, ids, name):
        result = {}
        for line in self.browse(ids):
            result[line.id] = line.sale.warehouse.id
        return result

    def get_from_location(self, ids, name):
        result = {}
        for line in self.browse(ids):
            if line.quantity >= 0 and line.warehouse:
                result[line.id] = line.warehouse.output_location.id
            else:
                result[line.id] = line.sale.party.customer_location.id
        return result

    def get_to_location(self, ids, name):
        result = {}
        for line in self.browse(ids):
            if line.quantity >= 0:
                result[line.id] = line.sale.party.customer_location.id
            else:
                if line.warehouse:
                    result[line.id] = line.warehouse.input_location.id
                else:
                    result[line.id] = None
        return result

    def _compute_delivery_date(self, product, date):
        product_obj = Pool().get('product.product')
        if product:
            return product_obj.compute_delivery_date(product, date=date)
        else:
            return None

    def on_change_with_delivery_date(self, values):
        product_obj = Pool().get('product.product')
        if values.get('product'):
            product = product_obj.browse(values['product'])
            return self._compute_delivery_date(product,
                values.get('_parent_sale.sale_date'))
        return None

    def get_delivery_date(self, ids, name):
        dates = {}
        for line in self.browse(ids):
            dates[line.id] = self._compute_delivery_date(line.product,
                line.sale.sale_date)
        return dates

    def get_invoice_line(self, line, invoice_type):
        '''
        Return a list of invoice line values for sale line according to
        invoice_type
        '''
        uom_obj = Pool().get('product.uom')
        property_obj = Pool().get('ir.property')

        res = {}
        res['sequence'] = line.sequence
        res['type'] = line.type
        res['description'] = line.description
        res['note'] = line.note
        if line.type != 'line':
            if (line.sale.invoice_method == 'order'
                    and (all(l.quantity >= 0 for l in line.sale.lines
                            if l.type == 'line')
                        or all(l.quantity <= 0 for l in line.sale.lines
                            if l.type == 'line'))):
                return [res]
            else:
                return []

        if (invoice_type == 'out_invoice') != (line.quantity >= 0):
            return []

        if (line.sale.invoice_method == 'order'
                or not line.product
                or line.product.type == 'service'):
            quantity = abs(line.quantity)
        else:
            quantity = 0.0
            for move in line.moves:
                if move.state == 'done':
                    quantity += uom_obj.compute_qty(move.uom, move.quantity,
                            line.unit)

        ignored_ids = set(
            l.id for i in line.sale.invoices_ignored for l in i.lines)
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
            res['account'] = line.product.account_revenue_used.id
            if not res['account']:
                self.raise_user_error('missing_account_revenue',
                        error_args=(line.product.rec_name,))
        else:
            for model in ('product.template', 'product.category'):
                res['account'] = property_obj.get('account_revenue', model)
                if res['account']:
                    break
            if not res['account']:
                self.raise_user_error('missing_account_revenue_property')
        return [res]

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['moves'] = None
        default['moves_ignored'] = None
        default['moves_recreated'] = None
        default['invoice_lines'] = None
        return super(SaleLine, self).copy(ids, default=default)

    def get_move(self, line, shipment_type):
        '''
        Return move values for the sale line according ot shipment_type
        '''
        uom_obj = Pool().get('product.uom')

        res = {}
        if line.type != 'line':
            return
        if not line.product:
            return
        if line.product.type == 'service':
            return
        if (shipment_type == 'out') != (line.quantity >= 0):
            return
        skip_ids = set(x.id for x in line.moves_recreated)
        quantity = abs(line.quantity)
        for move in line.moves:
            if move.id not in skip_ids:
                quantity -= uom_obj.compute_qty(move.uom, move.quantity,
                        line.unit)
        if quantity <= 0.0:
            return
        if not line.sale.party.customer_location:
            self.raise_user_error('customer_location_required')
        res['quantity'] = quantity
        res['uom'] = line.unit.id
        res['product'] = line.product.id
        res['from_location'] = line.from_location.id
        res['to_location'] = line.to_location.id
        res['state'] = 'draft'
        res['company'] = line.sale.company.id
        res['unit_price'] = line.unit_price
        res['currency'] = line.sale.currency.id
        res['planned_date'] = line.delivery_date
        return res

SaleLine()


class SaleLineTax(ModelSQL):
    'Sale Line - Tax'
    _name = 'sale.line-account.tax'
    _table = 'sale_line_account_tax'
    _description = __doc__
    line = fields.Many2One('sale.line', 'Sale Line', ondelete='CASCADE',
            select=True, required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
            select=True, required=True)

SaleLineTax()


class SaleLineInvoiceLine(ModelSQL):
    'Sale Line - Invoice Line'
    _name = 'sale.line-account.invoice.line'
    _table = 'sale_line_invoice_lines_rel'
    _description = __doc__
    sale_line = fields.Many2One('sale.line', 'Sale Line', ondelete='CASCADE',
            select=True, required=True)
    invoice_line = fields.Many2One('account.invoice.line', 'Invoice Line',
            ondelete='RESTRICT', select=True, required=True)

SaleLineInvoiceLine()


class SaleLineIgnoredMove(ModelSQL):
    'Sale Line - Ignored Move'
    _name = 'sale.line-ignored-stock.move'
    _table = 'sale_line_moves_ignored_rel'
    _description = __doc__
    sale_line = fields.Many2One('sale.line', 'Sale Line', ondelete='CASCADE',
            select=True, required=True)
    move = fields.Many2One('stock.move', 'Move', ondelete='RESTRICT',
            select=True, required=True)

SaleLineIgnoredMove()


class SaleLineRecreatedMove(ModelSQL):
    'Sale Line - Recreated Move'
    _name = 'sale.line-recreated-stock.move'
    _table = 'sale_line_moves_recreated_rel'
    _description = __doc__
    sale_line = fields.Many2One('sale.line', 'Sale Line', ondelete='CASCADE',
            select=True, required=True)
    move = fields.Many2One('stock.move', 'Move', ondelete='RESTRICT',
            select=True, required=True)

SaleLineRecreatedMove()


class SaleReport(CompanyReport):
    _name = 'sale.sale'

SaleReport()


class Template(ModelSQL, ModelView):
    _name = 'product.template'

    salable = fields.Boolean('Salable', states={
            'readonly': ~Eval('active', True),
            }, depends=['active'])
    sale_uom = fields.Many2One('product.uom', 'Sale UOM', states={
            'readonly': ~Eval('active', True),
            'invisible': ~Eval('salable', False),
            'required': Eval('salable', False),
            },
        domain=[
            ('category', '=', Eval('default_uom_category')),
            ],
        on_change_with=['default_uom', 'sale_uom', 'salable'],
        depends=['active', 'salable', 'default_uom_category'])
    delivery_time = fields.Integer('Delivery Time', states={
            'readonly': ~Eval('active', True),
            'invisible': ~Eval('salable', False),
            'required': Eval('salable', False),
            },
        depends=['active', 'salable'],
        help='In number of days')

    def __init__(self):
        super(Template, self).__init__()
        self.account_revenue = copy.copy(self.account_revenue)
        self.account_revenue.states = copy.copy(self.account_revenue.states)
        required = ~Eval('account_category', False) & Eval('salable', False)
        if not self.account_revenue.states.get('required'):
            self.account_revenue.states['required'] = required
        else:
            self.account_revenue.states['required'] = (
                    self.account_revenue.states['required'] | required)
        if 'account_category' not in self.account_revenue.depends:
            self.account_revenue = copy.copy(self.account_revenue)
            self.account_revenue.depends = \
                    copy.copy(self.account_revenue.depends)
            self.account_revenue.depends.append('account_category')
        if 'salable' not in self.account_revenue.depends:
            self.account_revenue = copy.copy(self.account_revenue)
            self.account_revenue.depends = \
                    copy.copy(self.account_revenue.depends)
            self.account_revenue.depends.append('salable')
        self._reset_columns()

    def default_salable(self):
        return True if Transaction().context.get('salable') else False

    def default_delivery_time(self):
        return 0

    def on_change_with_sale_uom(self, vals):
        uom_obj = Pool().get('product.uom')
        res = None

        if vals.get('default_uom'):
            default_uom = uom_obj.browse(vals['default_uom'])
            if vals.get('sale_uom'):
                sale_uom = uom_obj.browse(vals['sale_uom'])
                if default_uom.category.id == sale_uom.category.id:
                    res = sale_uom.id
                else:
                    res = default_uom.id
            else:
                res = default_uom.id
        return res

Template()


class Product(ModelSQL, ModelView):
    _name = 'product.product'

    def get_sale_price(self, ids, quantity=0):
        '''
        Return the sale price for product ids.

        :param ids: the product ids
        :param quantity: the quantity of the products
            uom: the unit of measure
            currency: the currency id for the returned price
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
            uom = uom_obj.browse(Transaction().context.get('uom'))

        currency = None
        if Transaction().context.get('currency'):
            currency = currency_obj.browse(
                    Transaction().context.get('currency'))

        user2 = user_obj.browse(Transaction().user)

        for product in self.browse(ids):
            res[product.id] = product.list_price
            if uom:
                res[product.id] = uom_obj.compute_price(
                        product.default_uom, res[product.id], uom)
            if currency and user2.company:
                if user2.company.currency.id != currency.id:
                    date = Transaction().context.get('sale_date') or today
                    with Transaction().set_context(date=date):
                        res[product.id] = currency_obj.compute(
                                user2.company.currency.id, res[product.id],
                                currency.id, round=False)
        return res

    def compute_delivery_date(self, product, date=None):
        '''
        Compute the delivery date for the Product at a the given date
        '''
        date_obj = Pool().get('ir.date')

        if not date:
            date = date_obj.today()
        return date + datetime.timedelta(product.delivery_time)

Product()


class ShipmentOut(ModelSQL, ModelView):
    _name = 'stock.shipment.out'

    def __init__(self):
        super(ShipmentOut, self).__init__()
        self._error_messages.update({
                'reset_move': 'You cannot reset to draft a move generated '
                    'by a sale.',
            })

    def write(self, ids, vals):
        sale_obj = Pool().get('sale.sale')
        sale_line_obj = Pool().get('sale.line')

        res = super(ShipmentOut, self).write(ids, vals)

        if 'state' in vals and vals['state'] in ('done', 'cancel'):
            sale_ids = []
            move_ids = []
            if isinstance(ids, (int, long)):
                ids = [ids]
            for shipment in self.browse(ids):
                move_ids.extend([x.id for x in shipment.outgoing_moves])

            sale_line_ids = sale_line_obj.search([
                ('moves', 'in', move_ids),
                ])
            if sale_line_ids:
                for sale_line in sale_line_obj.browse(sale_line_ids):
                    if sale_line.sale.id not in sale_ids:
                        sale_ids.append(sale_line.sale.id)

            with Transaction().set_user(0, set_context=True):
                sale_obj.process(sale_ids)
        return res

    @ModelView.button
    @Workflow.transition('draft')
    def draft(self, ids):
        for shipment in self.browse(ids):
            for move in shipment.outgoing_moves:
                if move.state == 'cancel' and move.sale_line:
                    self.raise_user_error('reset_move')

        return super(ShipmentOut, self).draft(ids)

ShipmentOut()


class ShipmentOutReturn(ModelSQL, ModelView):
    _name = 'stock.shipment.out.return'

    def __init__(self):
        super(ShipmentOutReturn, self).__init__()
        self._error_messages.update({
                'reset_move': 'You cannot reset to draft a move generated '
                    'by a sale.',
            })

    def write(self, ids, vals):
        sale_obj = Pool().get('sale.sale')
        sale_line_obj = Pool().get('sale.line')

        res = super(ShipmentOutReturn, self).write(ids, vals)

        if 'state' in vals and vals['state'] == 'received':
            sale_ids = []
            move_ids = []
            if isinstance(ids, (int, long)):
                ids = [ids]
            for shipment in self.browse(ids):
                move_ids.extend([x.id for x in shipment.incoming_moves])

            sale_line_ids = sale_line_obj.search([
                ('moves', 'in', move_ids),
                ])
            if sale_line_ids:
                for sale_line in sale_line_obj.browse(sale_line_ids):
                    if sale_line.sale.id not in sale_ids:
                        sale_ids.append(sale_line.sale.id)

            with Transaction().set_user(0, set_context=True):
                sale_obj.process(sale_ids)
        return res

    @ModelView.button
    @Workflow.transition('draft')
    def draft(self, ids):
        for shipment in self.browse(ids):
            for move in shipment.incoming_moves:
                if move.state == 'cancel' and move.sale_line:
                    self.raise_user_error('reset_move')

        return super(ShipmentOutReturn, self).draft(ids)

ShipmentOutReturn()


class Move(ModelSQL, ModelView):
    _name = 'stock.move'

    sale_line = fields.Many2One('sale.line', 'Sale Line', select=True,
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])
    sale = fields.Function(fields.Many2One('sale.sale', 'Sale', select=True),
            'get_sale', searcher='search_sale')
    sale_exception_state = fields.Function(fields.Selection([
        ('', ''),
        ('ignored', 'Ignored'),
        ('recreated', 'Recreated'),
        ], 'Exception State'), 'get_sale_exception_state')

    def get_sale(self, ids, name):
        res = {}
        for move in self.browse(ids):
            res[move.id] = None
            if move.sale_line:
                res[move.id] = move.sale_line.sale.id
        return res

    def search_sale(self, name, clause):
        return [('sale_line.' + name,) + clause[1:]]

    def get_sale_exception_state(self, ids, name):
        res = {}.fromkeys(ids, '')
        for move in self.browse(ids):
            if not move.sale_line:
                continue
            if move.id in (x.id for x in move.sale_line.moves_recreated):
                res[move.id] = 'recreated'
            if move.id in (x.id for x in move.sale_line.moves_ignored):
                res[move.id] = 'ignored'
        return res

    def write(self, ids, vals):
        sale_obj = Pool().get('sale.sale')
        sale_line_obj = Pool().get('sale.line')

        res = super(Move, self).write(ids, vals)
        if 'state' in vals and vals['state'] in ('cancel',):
            if isinstance(ids, (int, long)):
                ids = [ids]
            sale_ids = set()
            sale_line_ids = sale_line_obj.search([
                ('moves', 'in', ids),
                ])
            if sale_line_ids:
                for sale_line in sale_line_obj.browse(sale_line_ids):
                    sale_ids.add(sale_line.sale.id)
            if sale_ids:
                with Transaction().set_user(0, set_context=True):
                    sale_obj.process(list(sale_ids))
        return res

    def delete(self, ids):
        sale_obj = Pool().get('sale.sale')
        sale_line_obj = Pool().get('sale.line')

        if isinstance(ids, (int, long)):
            ids = [ids]

        sale_ids = set()
        sale_line_ids = sale_line_obj.search([
            ('moves', 'in', ids),
            ])

        res = super(Move, self).delete(ids)

        if sale_line_ids:
            for sale_line in sale_line_obj.browse(sale_line_ids):
                sale_ids.add(sale_line.sale.id)
            if sale_ids:
                with Transaction().set_user(0, set_context=True):
                    sale_obj.process(list(sale_ids))
        return res

Move()


class Invoice(ModelSQL, ModelView):
    _name = 'account.invoice'

    sale_exception_state = fields.Function(fields.Selection([
        ('', ''),
        ('ignored', 'Ignored'),
        ('recreated', 'Recreated'),
        ], 'Exception State'), 'get_sale_exception_state')

    def __init__(self):
        super(Invoice, self).__init__()
        self._error_messages.update({
            'delete_sale_invoice': 'You can not delete invoices '
                    'that come from a sale!',
            'reset_invoice_sale': 'You cannot reset to draft '
                    'an invoice generated by a sale.',
            })

    @Workflow.transition('draft')
    def draft(self, ids):
        sale_obj = Pool().get('sale.sale')
        sale_ids = sale_obj.search([
            ('invoices', 'in', ids),
            ])

        if sale_ids:
            self.raise_user_error('reset_invoice_sale')

        return super(Invoice, self).draft(ids)

    def get_sale_exception_state(self, ids, name):
        sale_obj = Pool().get('sale.sale')
        sale_ids = sale_obj.search([
            ('invoices', 'in', ids),
            ])

        sales = sale_obj.browse(sale_ids)

        recreated_ids = tuple(i.id for p in sales
            for i in p.invoices_recreated)
        ignored_ids = tuple(i.id for p in sales for i in p.invoices_ignored)

        res = {}.fromkeys(ids, '')
        for invoice in self.browse(ids):
            if invoice.id in recreated_ids:
                res[invoice.id] = 'recreated'
            elif invoice.id in ignored_ids:
                res[invoice.id] = 'ignored'

        return res

    def delete(self, ids):
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        Transaction().cursor.execute('SELECT id FROM sale_invoices_rel '
                'WHERE invoice IN (' + ','.join(('%s',) * len(ids)) + ')',
                ids)
        if Transaction().cursor.fetchone():
            self.raise_user_error('delete_sale_invoice')
        return super(Invoice, self).delete(ids)

Invoice()


class OpenCustomer(Wizard):
    'Open Customers'
    _name = 'sale.open_customer'
    start_state = 'open_'
    open_ = StateAction('party.act_party_form')

    def do_open_(self, session, action):
        pool = Pool()
        model_data_obj = pool.get('ir.model.data')
        wizard_obj = pool.get('ir.action.wizard')
        Transaction().cursor.execute("SELECT DISTINCT(party) FROM sale_sale")
        customer_ids = [line[0] for line in Transaction().cursor.fetchall()]
        action['pyson_domain'] = PYSONEncoder().encode(
            [('id', 'in', customer_ids)])

        model_data_ids = model_data_obj.search([
            ('fs_id', '=', 'act_open_customer'),
            ('module', '=', 'sale'),
            ('inherit', '=', None),
            ], limit=1)
        model_data = model_data_obj.browse(model_data_ids[0])
        wizard = wizard_obj.browse(model_data.db_id)

        action['name'] = wizard.name
        return action, {}

    def transition_open_(self, session):
        return 'end'

OpenCustomer()


class HandleShipmentExceptionAsk(ModelView):
    'Handle Shipment Exception'
    _name = 'sale.handle.shipment.exception.ask'
    _description = __doc__

    recreate_moves = fields.Many2Many(
        'stock.move', None, None, 'Recreate Moves',
        domain=[('id', 'in', Eval('domain_moves'))], depends=['domain_moves'])
    domain_moves = fields.Many2Many(
        'stock.move', None, None, 'Domain Moves')

    def init(self, module_name):
        cursor = Transaction().cursor
        # Migration from 1.2: packing renamed into shipment
        cursor.execute("UPDATE ir_model "
                "SET model = REPLACE(model, 'packing', 'shipment') "
                "WHERE model like '%%packing%%' AND module = %s",
                (module_name,))
        super(HandleShipmentExceptionAsk, self).init(module_name)

HandleShipmentExceptionAsk()


class HandleShipmentException(Wizard):
    'Handle Shipment Exception'
    _name = 'sale.handle.shipment.exception'
    start_state = 'ask'
    ask = StateView('sale.handle.shipment.exception.ask',
        'sale.handle_shipment_exception_ask_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Ok', 'handle', 'tryton-ok', default=True),
            ])
    handle = StateTransition()

    def default_ask(self, session, fields):
        sale_obj = Pool().get('sale.sale')
        sale = sale_obj.browse(Transaction().context.get('active_id'))

        moves = []
        for line in sale.lines:
            skip_ids = set(x.id for x in line.moves_ignored)
            skip_ids.update(x.id for x in line.moves_recreated)
            for move in line.moves:
                if move.state == 'cancel' and move.id not in skip_ids:
                    moves.append(move.id)
        return {
            'recreate_moves': moves,
            'domain_moves': moves,
            }

    def transition_handle(self, session):
        pool = Pool()
        sale_obj = pool.get('sale.sale')
        sale_line_obj = pool.get('sale.line')
        to_recreate = [x.id for x in session.ask.recreate_moves]
        domain_moves = [x.id for x in session.ask.domain_moves]

        sale = sale_obj.browse(Transaction().context['active_id'])

        for line in sale.lines:
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

            sale_line_obj.write(line.id, {
                    'moves_ignored': [('add', moves_ignored)],
                    'moves_recreated': [('add', moves_recreated)],
                    })
        sale_obj.process([sale.id])
        return 'end'

HandleShipmentException()


class HandleInvoiceExceptionAsk(ModelView):
    'Handle Invoice Exception'
    _name = 'sale.handle.invoice.exception.ask'
    _description = __doc__

    recreate_invoices = fields.Many2Many(
        'account.invoice', None, None, 'Recreate Invoices',
        domain=[('id', 'in', Eval('domain_invoices'))],
        depends=['domain_invoices'],
        help='The selected invoices will be recreated. '
            'The other ones will be ignored.')
    domain_invoices = fields.Many2Many(
        'account.invoice', None, None, 'Domain Invoices')

HandleInvoiceExceptionAsk()


class HandleInvoiceException(Wizard):
    'Handle Invoice Exception'
    _name = 'sale.handle.invoice.exception'
    start_state = 'ask'
    ask = StateView('sale.handle.invoice.exception.ask',
        'sale.handle_invoice_exception_ask_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Ok', 'handle', 'tryton-ok', default=True),
            ])
    handle = StateTransition()

    def default_ask(self, session, fields):
        sale_obj = Pool().get('sale.sale')

        sale = sale_obj.browse(Transaction().context['active_id'])
        skip_ids = set(x.id for x in sale.invoices_ignored)
        skip_ids.update(x.id for x in sale.invoices_recreated)
        invoices = []
        for invoice in sale.invoices:
            if invoice.state == 'cancel' and invoice.id not in skip_ids:
                invoices.append(invoice.id)
        return {
            'to_recreate': invoices,
            'domain_invoices': invoices,
            }

    def transition_handle(self, session):
        sale_obj = Pool().get('sale.sale')
        to_recreate = [x.id for x in session.ask.recreate_invoices]
        domain_invoices = [x.id for x in session.ask.domain_invoices]

        sale = sale_obj.browse(Transaction().context['active_id'])

        skip_ids = set(x.id for x in sale.invoices_ignored)
        skip_ids.update(x.id for x in sale.invoices_recreated)
        invoices_ignored = []
        invoices_recreated = []
        for invoice in sale.invoices:
            if invoice.id not in domain_invoices or invoice.id in skip_ids:
                continue
            if invoice.id in to_recreate:
                invoices_recreated.append(invoice.id)
            else:
                invoices_ignored.append(invoice.id)

        sale_obj.write(sale.id, {
                'invoices_ignored': [('add', invoices_ignored)],
                'invoices_recreated': [('add', invoices_recreated)],
                })
        sale_obj.process([sale.id])
        return 'end'

HandleInvoiceException()


class ReturnSale(Wizard):
    _name = 'sale.return_sale'
    start_state = 'make_return'
    make_return = StateTransition()

    def transition_make_return(self, session):
        pool = Pool()
        sale_obj = pool.get('sale.sale')
        line_obj = pool.get('sale.line')

        sale_id = Transaction().context['active_id']
        new_sale_id = sale_obj.copy(sale_id)
        new_line_ids = line_obj.search([('sale', '=', new_sale_id)])
        for new_line in line_obj.browse(new_line_ids):
            line_obj.write(new_line.id, {'quantity': -new_line.quantity})
        return 'end'

ReturnSale()
