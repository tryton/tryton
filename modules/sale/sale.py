#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from __future__ import with_statement
import copy
from decimal import Decimal
from trytond.model import ModelWorkflow, ModelView, ModelSQL, fields
from trytond.modules.company import CompanyReport
from trytond.wizard import Wizard
from trytond.backend import TableHandler
from trytond.pyson import If, In, Eval, Get, Or, Not, Equal, Bool, And, \
        PYSONEncoder
from trytond.transaction import Transaction

class Sale(ModelWorkflow, ModelSQL, ModelView):
    'Sale'
    _name = 'sale.sale'
    _rec_name = 'reference'
    _description = __doc__

    company = fields.Many2One('company.company', 'Company', required=True,
            states={
                'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                    Bool(Eval('lines'))),
            }, domain=[
                ('id', If(In('company', Eval('context', {})), '=', '!='),
                    Get(Eval('context', {}), 'company', 0)),
            ])
    reference = fields.Char('Reference', readonly=True, select=1)
    description = fields.Char('Description',
            states={
                'readonly': Not(Equal(Eval('state'), 'draft')),
            })
    state = fields.Selection([
        ('draft', 'Draft'),
        ('quotation', 'Quotation'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancel', 'Canceled'),
    ], 'State', readonly=True, required=True)
    sale_date = fields.Date('Sale Date', required=True,
            states={
                'readonly': Not(Equal(Eval('state'), 'draft')),
            })
    payment_term = fields.Many2One('account.invoice.payment_term',
            'Payment Term', required=True, states={
                'readonly': Not(Equal(Eval('state'), 'draft')),
            })
    party = fields.Many2One('party.party', 'Party', change_default=True,
            required=True, select=1, states={
                'readonly': Not(Equal(Eval('state'), 'draft')),
            }, on_change=['party', 'payment_term'])
    party_lang = fields.Function(fields.Char('Party Language',
        on_change_with=['party']), 'get_function_fields')
    invoice_address = fields.Many2One('party.address', 'Invoice Address',
            domain=[('party', '=', Eval('party'))], states={
                'readonly': Not(Equal(Eval('state'), 'draft')),
            })
    shipment_address = fields.Many2One('party.address', 'Shipment Address',
            domain=[('party', '=', Eval('party'))], states={
                'readonly': Not(Equal(Eval('state'), 'draft')),
            })
    warehouse = fields.Many2One('stock.location', 'Warehouse',
            domain=[('type', '=', 'warehouse')], required=True, states={
                'readonly': Not(Equal(Eval('state'), 'draft')),
            })
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states={
            'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                And(Bool(Eval('lines')), Bool(Eval('currency')))),
        })
    currency_digits = fields.Function(fields.Integer('Currency Digits',
        on_change_with=['currency']), 'get_function_fields')
    lines = fields.One2Many('sale.line', 'sale', 'Lines', states={
        'readonly': Not(Equal(Eval('state'), 'draft')),
        }, on_change=['lines', 'currency', 'party'])
    comment = fields.Text('Comment')
    untaxed_amount = fields.Function(fields.Numeric('Untaxed',
        digits=(16, Eval('currency_digits', 2))), 'get_function_fields')
    tax_amount = fields.Function(fields.Numeric('Tax',
        digits=(16, Eval('currency_digits', 2))), 'get_function_fields')
    total_amount = fields.Function(fields.Numeric('Total',
        digits=(16, Eval('currency_digits', 2))), 'get_function_fields')
    invoice_method = fields.Selection([
        ('manual', 'Manual'),
        ('order', 'On Order Confirmed'),
        ('shipment', 'On Shipment Sent'),
    ], 'Invoice Method', required=True, states={
        'readonly': Not(Equal(Eval('state'), 'draft')),
        })
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
    invoices_recreated = fields.Many2Many('sale.sale-recreated-account.invoice',
            'sale', 'invoice', 'Recreated Invoices', readonly=True)
    invoice_paid = fields.Function(fields.Boolean('Invoices Paid'),
            'get_function_fields')
    invoice_exception = fields.Function(fields.Boolean('Invoices Exception'),
            'get_function_fields')
    shipment_method = fields.Selection([
        ('manual', 'Manual'),
        ('order', 'On Order Confirmed'),
        ('invoice', 'On Invoice Paid'),
    ], 'Shipment Method', required=True, states={
        'readonly': Not(Equal(Eval('state'), 'draft')),
        })
    shipment_state = fields.Selection([
        ('none', 'None'),
        ('waiting', 'Waiting'),
        ('sent', 'Sent'),
        ('exception', 'Exception'),
    ], 'Shipment State', readonly=True, required=True)
    shipments = fields.Function(fields.One2Many('stock.shipment.out', None,
        'Shipments'), 'get_function_fields')
    moves = fields.Function(fields.One2Many('stock.move', None, 'Moves'),
            'get_function_fields')
    shipment_done = fields.Function(fields.Boolean('Shipment Done'),
            'get_function_fields')
    shipment_exception = fields.Function(fields.Boolean('Shipments Exception'),
            'get_function_fields')

    def __init__(self):
        super(Sale, self).__init__()
        self._order[0] = ('sale_date', 'DESC')
        self._order[0] = ('id', 'DESC')
        self._constraints += [
            ('check_method', 'wrong_method')
        ]
        self._error_messages.update({
            'wrong_method': 'Wrong combination of method!',
            'addresses_required': 'Invoice and Shipment addresses must be '
            'defined for the quotation.',
            'missing_account_receivable': 'It misses ' 
                    'an "Account Receivable" on the party "%s"!',
        })

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

    def default_sale_date(self):
        date_obj = self.pool.get('ir.date')
        return date_obj.today()

    def default_currency(self):
        company_obj = self.pool.get('company.company')
        currency_obj = self.pool.get('currency.currency')
        company = Transaction().context.get('company')
        if company:
            return company_obj.browse(company).currency.id
        return False

    def default_currency_digits(self):
        company_obj = self.pool.get('company.company')
        company = Transaction().context.get('company')
        if company:
            return company_obj.browse(company).currency.digits
        return 2

    def default_invoice_method(self):
        return 'order'

    def default_invoice_state(self):
        return 'none'

    def default_shipment_method(self):
        return 'order'

    def default_shipment_state(self):
        return 'none'

    def on_change_party(self, vals):
        party_obj = self.pool.get('party.party')
        address_obj = self.pool.get('party.address')
        payment_term_obj = self.pool.get('account.invoice.payment_term')
        res = {
            'invoice_address': False,
            'shipment_address': False,
            'payment_term': False,
        }
        if vals.get('party'):
            party = party_obj.browse(vals['party'])
            res['invoice_address'] = party_obj.address_get(party.id, 
                    type='invoice')
            res['shipment_address'] = party_obj.address_get(party.id, 
                    type='delivery')
            if party.payment_term:
                res['payment_term'] = party.payment_term.id

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
        currency_obj = self.pool.get('currency.currency')
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
        party_obj = self.pool.get('party.party')
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
        party_obj = self.pool.get('party.party')
        if vals.get('party'):
            party = party_obj.browse(vals['party'])
            if party.lang:
                return party.lang.code
        return 'en_US'

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
                res[sale.id] = 'en_US'
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
            taxes = {}
            for line in vals['lines']:
                if line.get('type', 'line') != 'line':
                    continue
                res['untaxed_amount'] += line.get('amount', Decimal('0.0'))
                tax_list = ()
                with Transaction().set_context(self.get_tax_context(vals)):
                    tax_list = tax_obj.compute(line.get('taxes', []),
                            line.get('unit_price', Decimal('0.0')),
                            line.get('quantity', 0.0))
                for tax in tax_list:
                    key, val = invoice_obj._compute_tax(tax,'out_invoice')
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
        if 'untaxed_amount' in names:
            res['untaxed_amount'] = self.get_untaxed_amount(sales)
        if 'tax_amount' in names:
            res['tax_amount'] = self.get_tax_amount(sales)
        if 'total_amount' in names:
            res['total_amount'] = self.get_total_amount(sales)
        if 'invoice_paid' in names:
            res['invoice_paid'] = self.get_invoice_paid(sales)
        if 'invoice_exception' in names:
            res['invoice_exception'] = self.get_invoice_exception(sales)
        if 'shipments' in names:
            res['shipments'] = self.get_shipments(sales)
        if 'moves' in names:
            res['moves'] = self.get_moves(sales)
        if 'shipment_done' in names:
            res['shipment_done'] = self.get_shipment_done(sales)
        if 'shipment_exception' in names:
            res['shipment_exception'] = self.get_shipment_exception(sales)
        return res

    def get_untaxed_amount(self, sales):
        '''
        Compute the untaxed amount for each sales

        :param sales: a BrowseRecordList of sales
        :return: a dictionary with sale id as key and
            untaxed amount as value
        '''
        currency_obj = self.pool.get('currency.currency')
        res = {}
        for sale in sales:
            res.setdefault(sale.id, Decimal('0.0'))
            for line in sale.lines:
                if line.type != 'line':
                    continue
                res[sale.id] += line.amount
            res[sale.id] = currency_obj.round(sale.currency, res[sale.id])
        return res

    def get_tax_amount(self, sales):
        '''
        Compute tax amount for each sales

        :param sales: a BrowseRecordList of sales
        :return: a dictionary with sale id as key and
            tax amount as value
        '''
        currency_obj = self.pool.get('currency.currency')
        tax_obj = self.pool.get('account.tax')
        invoice_obj = self.pool.get('account.invoice')

        res = {}
        for sale in sales:
            res.setdefault(sale.id, Decimal('0.0'))
            taxes = {}
            for line in sale.lines:
                if line.type != 'line':
                    continue
                # Don't round on each line to handle rounding error
                tax_list = ()
                with Transaction().set_context(self.get_tax_context(sale)):
                    tax_list = tax_obj.compute(
                            [t.id for t in line.taxes], line.unit_price,
                            line.quantity)
                for tax in tax_list:
                    key, val = invoice_obj._compute_tax(tax, 'out_invoice')
                    if not key in taxes:
                        taxes[key] = val['amount']
                    else:
                        taxes[key] += val['amount']
            for key in taxes:
                res[sale.id] += currency_obj.round(sale.currency, taxes[key])
            res[sale.id] = currency_obj.round(sale.currency, res[sale.id])
        return res

    def get_total_amount(self, sales):
        '''
        Return the total amount of each sales

        :param sales: a BrowseRecordList of sales
        :return: a dictionary with sale id as key and
            total amount as value
        '''
        currency_obj = self.pool.get('currency.currency')
        res = {}
        untaxed_amounts = self.get_untaxed_amount(sales)
        tax_amounts = self.get_tax_amount(sales)
        for sale in sales:
            res[sale.id] = currency_obj.round(sale.currency,
                    untaxed_amounts[sale.id] + tax_amounts[sale.id])
        return res

    def get_invoice_paid(self, sales):
        '''
        Return if all invoices have been paid for each sales

        :param sales: a BrowseRecordList of sales
        :return: a dictionary with sale id as key and
            a boolean as value
        '''
        res = {}
        for sale in sales:
            val = True
            skip_ids = set(x.id for x in sale.invoices_ignored)
            skip_ids.update(x.id for x in sale.invoices_recreated)
            for invoice in sale.invoices:
                if invoice.state != 'paid' \
                        and invoice.id not in skip_ids:
                    val = False
                    break
            res[sale.id] = val
        return res

    def get_invoice_exception(self, sales):
        '''
        Return if there is an invoice exception for each sales

        :param sales: a BrowseRecordList of sales
        :return: a dictionary with sale id as key and
            a boolean as value
        '''
        res = {}
        for sale in sales:
            val = False
            skip_ids = set(x.id for x in sale.invoices_ignored)
            skip_ids.update(x.id for x in sale.invoices_recreated)
            for invoice in sale.invoices:
                if invoice.state == 'cancel' \
                        and invoice.id not in skip_ids:
                    val = True
                    break
            res[sale.id] = val
        return res

    def get_shipments(self, sales):
        '''
        Return shipment_out ids for each sales

        :param sales: a BrowseRecordList of sales
        :return: a dictionary with sale id as key and
            a list of shipment_out id as value
        '''
        res = {}
        for sale in sales:
            res[sale.id] = []
            for line in sale.lines:
                for move in line.moves:
                    if move.shipment_out:
                        if move.shipment_out.id not in res[sale.id]:
                            res[sale.id].append(move.shipment_out.id)
        return res

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

    def get_shipment_done(self, sales):
        '''
        Return if all the shipments have been done for each sales

        :param sales: a BrowseRecordList of sales
        :return: a dictionary with sale id as key and
            a boolean as value
        '''
        res = {}
        for sale in sales:
            val = True
            for line in sale.lines:
                if not line.move_done:
                    val = False
                    break
            res[sale.id] = val
        return res

    def get_shipment_exception(self, sales):
        '''
        Return if there is a shipment exception for each sales

        :param sales: a BrowseRecordList of sales
        :return: a dictionary with sale id as key and
            a boolean as value
        '''
        res = {}
        for sale in sales:
            val = False
            for line in sale.lines:
                if line.move_exception:
                    val = True
                    break
            res[sale.id] = val
        return res

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
        default['reference'] = False
        default['invoice_state'] = 'none'
        default['invoices'] = False
        default['invoices_ignored'] = False
        default['shipment_state'] = 'none'
        return super(Sale, self).copy(ids, default=default)

    def check_for_quotation(self, sale_id):
        sale = self.browse(sale_id)
        if not sale.invoice_address or not sale.shipment_address:
            self.raise_user_error('addresses_required')
        return True

    def set_reference(self, sale_id):
        '''
        Fill the reference field with the sale sequence

        :param sale_id: the id of the sale

        :return: True if succeed
        '''
        sequence_obj = self.pool.get('ir.sequence')
        config_obj = self.pool.get('sale.configuration')

        sale = self.browse(sale_id)

        if sale.reference:
            return True

        config = config_obj.browse(1)
        reference = sequence_obj.get_id(config.sale_sequence.id)
        self.write(sale_id, {
            'reference': reference,
            })
        return True

    def _get_invoice_line_sale_line(self, sale):
        '''
        Return invoice line values for each sale lines

        :param sale: the BrowseRecord of the sale

        :return: a dictionary with invoiced sale line id as key
            and a list of invoice lines values as value
        '''
        line_obj = self.pool.get('sale.line')
        res = {}
        for line in sale.lines:
            val = line_obj.get_invoice_line(line)
            if val:
                res[line.id] = val
        return res

    def _get_invoice_sale(self, sale):
        '''
        Return invoice values for sale

        :param sale: the BrowseRecord of the sale

        :return: a dictionary with invoice fields as key and
            invoice values as value
        '''
        journal_obj = self.pool.get('account.journal')

        journal_id = journal_obj.search([
            ('type', '=', 'revenue'),
            ], limit=1)
        if journal_id:
            journal_id = journal_id[0]

        res = {
            'company': sale.company.id,
            'type': 'out_invoice',
            'reference': sale.reference,
            'journal': journal_id,
            'party': sale.party.id,
            'invoice_address': sale.invoice_address.id,
            'currency': sale.currency.id,
            'account': sale.party.account_receivable.id,
            'payment_term': sale.payment_term.id,
            }
        return res

    def create_invoice(self, sale_id):
        '''
        Create an invoice for the sale

        :param sale_id: the sale id

        :return: the created invoice id or None
        '''
        invoice_obj = self.pool.get('account.invoice')
        invoice_line_obj = self.pool.get('account.invoice.line')
        sale_line_obj = self.pool.get('sale.line')

        sale = self.browse(sale_id)

        if not sale.party.account_receivable:
            self.raise_user_error('missing_account_receivable',
                    error_args=(sale.party.rec_name,))

        invoice_lines = self._get_invoice_line_sale_line(sale)
        if not invoice_lines:
            return


        vals = self._get_invoice_sale(sale)
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

        self.write(sale_id, {
            'invoices': [('add', invoice_id)],
        })
        return invoice_id

    def _get_move_sale_line(self, sale):
        '''
        Return a dictionary of move values for each sale lines

        :param sale: the BrowseRecord of the sale

        :return: a dictionary with move as key and move values as value
        '''
        line_obj = self.pool.get('sale.line')
        res = {}
        for line in sale.lines:
            val = line_obj.get_move(line)
            if val:
                res[line.id] = val
        return res

    def create_shipment(self, sale_id):
        '''
        Create a shipment for the sale

        :param sale_id: the sale id

        :return: the created shipment id or None
        '''
        shipment_obj = self.pool.get('stock.shipment.out')
        move_obj = self.pool.get('stock.move')
        sale_line_obj = self.pool.get('sale.line')

        sale = self.browse(sale_id)

        moves = self._get_move_sale_line(sale)
        if not moves:
            return

        with Transaction().set_user(0, set_context=True):
            shipment_id = shipment_obj.create({
                'planned_date': sale.sale_date,
                'customer': sale.party.id,
                'delivery_address': sale.shipment_address.id,
                'reference': sale.reference,
                'warehouse': sale.warehouse.id,
            })

            for line_id in moves:
                vals = moves[line_id]
                vals['shipment_out'] = shipment_id
                move_id = move_obj.create(vals)
                sale_line_obj.write(line_id, {
                    'moves': [('add', move_id)],
                })
                shipment_obj.workflow_trigger_validate(shipment_id, 'waiting')
            return shipment_id

Sale()


class SaleInvoice(ModelSQL):
    'Sale - Invoice'
    _name = 'sale.sale-account.invoice'
    _table = 'sale_invoices_rel'
    _description = __doc__
    sale = fields.Many2One('sale.sale', 'Sale', ondelete='CASCADE', select=1,
            required=True)
    invoice = fields.Many2One('account.invoice', 'Invoice',
            ondelete='RESTRICT', select=1, required=True)

SaleInvoice()


class SaleIgnoredInvoice(ModelSQL):
    'Sale - Ignored Invoice'
    _name = 'sale.sale-ignored-account.invoice'
    _table = 'sale_invoice_ignored_rel'
    _description = __doc__
    sale = fields.Many2One('sale.sale', 'Sale', ondelete='CASCADE', select=1,
            required=True)
    invoice = fields.Many2One('account.invoice', 'Invoice',
            ondelete='RESTRICT', select=1, required=True)

SaleIgnoredInvoice()


class SaleRecreatedInvoice(ModelSQL):
    'Sale - Recreated Invoice'
    _name = 'sale.sale-recreated-account.invoice'
    _table = 'sale_invoice_recreated_rel'
    _description = __doc__
    sale = fields.Many2One('sale.sale', 'Sale', ondelete='CASCADE', select=1,
            required=True)
    invoice = fields.Many2One('account.invoice', 'Invoice',
            ondelete='RESTRICT', select=1, required=True)

SaleRecreatedInvoice()


class SaleLine(ModelSQL, ModelView):
    'Sale Line'
    _name = 'sale.line'
    _rec_name = 'description'
    _description = __doc__

    sale = fields.Many2One('sale.sale', 'Sale', ondelete='CASCADE', select=1)
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
                'readonly': Not(Bool(Eval('_parent_sale'))),
            }, on_change=['product', 'quantity', 'unit',
                '_parent_sale.currency', '_parent_sale.party'])
    unit = fields.Many2One('product.uom', 'Unit',
            states={
                'required': Bool(Eval('product')),
                'invisible': Not(Equal(Eval('type'), 'line')),
                'readonly': Not(Bool(Eval('_parent_sale'))),
            }, domain=[
                ('category', '=',
                    (Eval('product'), 'product.default_uom.category')),
            ],
            context={
                'category': (Eval('product'), 'product.default_uom.category'),
            },
            on_change=['product', 'quantity', 'unit', '_parent_sale.currency',
                '_parent_sale.party'])
    unit_digits = fields.Function(fields.Integer('Unit Digits',
        on_change_with=['unit']), 'get_unit_digits')
    product = fields.Many2One('product.product', 'Product',
            domain=[('salable', '=', True)],
            states={
                'invisible': Not(Equal(Eval('type'), 'line')),
                'readonly': Not(Bool(Eval('_parent_sale'))),
            }, on_change=['product', 'unit', 'quantity', 'description',
                '_parent_sale.party', '_parent_sale.currency'],
            context={
                'locations': If(Bool(Get(Eval('_parent_sale', {}),
                    'warehouse')),
                    [Get(Eval('_parent_sale', {}), 'warehouse')],
                    []),
                'stock_date_end': Get(Eval('_parent_sale', {}), 'sale_date'),
                'salable': True,
                'stock_skip_warehouse': True,
            })
    unit_price = fields.Numeric('Unit Price', digits=(16, 4),
            states={
                'invisible': Not(Equal(Eval('type'), 'line')),
                'required': Equal(Eval('type'), 'line'),
            })
    amount = fields.Function(fields.Numeric('Amount',
        digits=(16, Get(Eval('_parent_sale', {}), 'currency_digits', 2)),
        states={
            'invisible': Not(In(Eval('type'), ['line', 'subtotal'])),
            'readonly': Not(Bool(Eval('_parent_sale'))),
        }, on_change_with=['type', 'quantity', 'unit_price', 'unit',
            '_parent_sale.currency']), 'get_amount')
    description = fields.Text('Description', size=None, required=True)
    note = fields.Text('Note')
    taxes = fields.Many2Many('sale.line-account.tax', 'line', 'tax', 'Taxes',
            domain=[('parent', '=', False)], states={
                'invisible': Not(Equal(Eval('type'), 'line')),
            })
    invoice_lines = fields.Many2Many('sale.line-account.invoice.line',
            'sale_line', 'invoice_line', 'Invoice Lines', readonly=True)
    moves = fields.One2Many('stock.move', 'sale_line', 'Moves',
            readonly=True, select=1)
    moves_ignored = fields.Many2Many('sale.line-ignored-stock.move',
            'sale_line', 'move', 'Ignored Moves', readonly=True)
    moves_recreated = fields.Many2Many('sale.line-recreated-stock.move',
            'sale_line', 'move', 'Recreated Moves', readonly=True)
    move_done = fields.Function(fields.Boolean('Moves Done'), 'get_move_done')
    move_exception = fields.Function(fields.Boolean('Moves Exception'),
            'get_move_exception')

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

    def default_quantity(self):
        return 0.0

    def default_unit_price(self):
        return Decimal('0.0')

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
        if vals.get('unit'):
            context['uom'] = vals['unit']
        else:
            context['uom'] = product.sale_uom.id
        return context

    def on_change_product(self, vals):
        party_obj = self.pool.get('party.party')
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        tax_rule_obj = self.pool.get('account.tax.rule')

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
                self._get_context_sale_price(product,vals)):
            res['unit_price'] = product_obj.get_sale_price([product.id], 
                    vals.get('quantity', 0))[product.id]
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
            tax_ids = tax_rule_obj.apply(party.customer_tax_rule, False, 
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

    def on_change_quantity(self, vals):
        product_obj = self.pool.get('product.product')

        if not vals.get('product'):
            return {}
        res = {}

        product = product_obj.browse(vals['product'])

        with Transaction().set_context(
                self._get_context_sale_price(product, vals)):
            res['unit_price'] = product_obj.get_sale_price([vals['product']], 
                    vals.get('quantity', 0))[vals['product']]
        return res

    def on_change_unit(self, vals):
        return self.on_change_quantity(vals)

    def on_change_with_amount(self, vals):
        currency_obj = self.pool.get('currency.currency')
        if vals.get('type') == 'line':
            if isinstance(vals.get('_parent_sale.currency'), (int, long)):
                currency = currency_obj.browse(vals['_parent_sale.currency'])
            else:
                currency = vals['_parent_sale.currency']
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

    def get_invoice_line(self, line):
        '''
        Return invoice line values for sale line

        :param line: the BrowseRecord of the line

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

        if (line.sale.invoice_method == 'order'
                or not line.product
                or line.product.type == 'service'):
            quantity = line.quantity
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
            return None
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
        default['moves'] = False
        default['moves_ignored'] = False
        default['moves_recreated'] = False
        default['invoice_lines'] = False
        return super(SaleLine, self).copy(ids, default=default)

    def get_move(self, line):
        '''
        Return move values for the sale line

        :param line: the BrowseRecord of the line

        :return: a dictionary of values of move
        '''
        uom_obj = self.pool.get('product.uom')

        res = {}
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
        if not line.sale.party.customer_location:
            self.raise_user_error('customer_location_required')
        res['quantity'] = quantity
        res['uom'] = line.unit.id
        res['product'] = line.product.id
        res['from_location'] = line.sale.warehouse.output_location.id
        res['to_location'] = line.sale.party.customer_location.id
        res['state'] = 'draft'
        res['company'] = line.sale.company.id
        res['unit_price'] = line.unit_price
        res['currency'] = line.sale.currency.id
        res['planned_date'] = line.sale.sale_date
        return res

SaleLine()


class SaleLineTax(ModelSQL):
    'Sale Line - Tax'
    _name = 'sale.line-account.tax'
    _table = 'sale_line_account_tax'
    _description = __doc__
    line = fields.Many2One('sale.line', 'Sale Line', ondelete='CASCADE',
            select=1, required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
            select=1, required=True)

SaleLineTax()


class SaleLineInvoiceLine(ModelSQL):
    'Sale Line - Invoice Line'
    _name = 'sale.line-account.invoice.line'
    _table = 'sale_line_invoice_lines_rel'
    _description = __doc__
    sale_line = fields.Many2One('sale.line', 'Sale Line', ondelete='CASCADE',
            select=1, required=True)
    invoice_line = fields.Many2One('account.invoice.line', 'Invoice Line',
            ondelete='RESTRICT', select=1, required=True)

SaleLineInvoiceLine()


class SaleLineIgnoredMove(ModelSQL):
    'Sale Line - Ignored Move'
    _name = 'sale.line-ignored-stock.move'
    _table = 'sale_line_moves_ignored_rel'
    _description = __doc__
    sale_line = fields.Many2One('sale.line', 'Sale Line', ondelete='CASCADE',
            select=1, required=True)
    move = fields.Many2One('stock.move', 'Move', ondelete='RESTRICT',
            select=1, required=True)

SaleLineIgnoredMove()


class SaleLineRecreatedMove(ModelSQL):
    'Sale Line - Recreated Move'
    _name = 'sale.line-recreated-stock.move'
    _table = 'sale_line_moves_recreated_rel'
    _description = __doc__
    sale_line = fields.Many2One('sale.line', 'Sale Line', ondelete='CASCADE',
            select=1, required=True)
    move = fields.Many2One('stock.move', 'Move', ondelete='RESTRICT',
            select=1, required=True)

SaleLineRecreatedMove()


class SaleReport(CompanyReport):
    _name = 'sale.sale'

SaleReport()


class Template(ModelSQL, ModelView):
    _name = 'product.template'

    salable = fields.Boolean('Salable', states={
        'readonly': Not(Bool(Eval('active'))),
        })
    sale_uom = fields.Many2One('product.uom', 'Sale UOM', states={
        'readonly': Not(Bool(Eval('active'))),
        'invisible': Not(Bool(Eval('salable'))),
        'required': Bool(Eval('salable')),
        }, domain=[
            ('category', '=', (Eval('default_uom'), 'uom.category')),
        ],
        context={'category': (Eval('default_uom'), 'uom.category')},
        on_change_with=['default_uom', 'sale_uom', 'salable'])

    def __init__(self):
        super(Template, self).__init__()
        self.account_revenue = copy.copy(self.account_revenue)
        self.account_revenue.states = copy.copy(self.account_revenue.states)
        required = And(Not(Bool(Eval('account_category'))),
                Bool(Eval('salable')))
        if not self.account_revenue.states.get('required'):
            self.account_revenue.states['required'] = required
        else:
            self.account_revenue.states['required'] = \
                    Or(self.account_revenue.states['required'],
                            required)
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

    def on_change_with_sale_uom(self, vals):
        uom_obj = self.pool.get('product.uom')
        res = False

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
        uom_obj = self.pool.get('product.uom')
        user_obj = self.pool.get('res.user')
        currency_obj = self.pool.get('currency.currency')

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
                    res[product.id] = currency_obj.compute(
                            user2.company.currency, res[product.id], currency)
        return res

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
        sale_obj = self.pool.get('sale.sale')
        sale_line_obj = self.pool.get('sale.line')

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

            sale_obj.workflow_trigger_validate(sale_ids, 'shipment_update')
        return res

    def button_draft(self, ids):
        for shipment in self.browse(ids):
            for move in shipment.outgoing_moves:
                if move.state == 'cancel' and move.sale_line:
                    self.raise_user_error('reset_move')

        return super(ShipmentOut, self).button_draft(ids)

ShipmentOut()


class Move(ModelSQL, ModelView):
    _name = 'stock.move'

    sale_line = fields.Many2One('sale.line', 'Sale Line', select=1,
            states={
                'readonly': Not(Equal(Eval('state'), 'draft')),
            })
    sale = fields.Function(fields.Many2One('sale.sale', 'Sale', select=1),
            'get_sale', searcher='search_sale')
    sale_exception_state = fields.Function(fields.Selection([
        ('', ''),
        ('ignored', 'Ignored'),
        ('recreated', 'Recreated'),
        ], 'Exception State'), 'get_sale_exception_state')

    def get_sale(self, ids, name):
        sale_obj = self.pool.get('sale.sale')

        res = {}
        for move in self.browse(ids):
            res[move.id] = False
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
        sale_obj = self.pool.get('sale.sale')
        sale_line_obj = self.pool.get('sale.line')

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
                sale_obj.workflow_trigger_validate(list(sale_ids),
                        'shipment_update')
        return res

    def delete(self, ids):
        sale_obj = self.pool.get('sale.sale')
        sale_line_obj = self.pool.get('sale.line')

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
                sale_obj.workflow_trigger_validate(list(sale_ids),
                        'shipment_update')
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

    def button_draft(self, ids):
        sale_obj = self.pool.get('sale.sale')
        sale_ids = sale_obj.search([
            ('invoices', 'in', ids),
            ])

        if sale_ids:
            self.raise_user_error('reset_invoice_sale')

        return super(Invoice, self).button_draft(ids)

    def get_sale_exception_state(self, ids, name):
        sale_obj = self.pool.get('sale.sale')
        sale_ids = sale_obj.search([
            ('invoices', 'in', ids),
            ])

        sales = sale_obj.browse(sale_ids)

        recreated_ids = tuple(i.id for p in sales for i in p.invoices_recreated)
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
        act_window_id = model_data_obj.get_id('party', 'act_party_form')
        res = act_window_obj.read(act_window_id)
        Transaction().cursor.execute("SELECT DISTINCT(party) FROM sale_sale")
        customer_ids = [line[0] for line in Transaction().cursor.fetchall()]
        res['pyson_domain'] = PYSONEncoder().encode(
                [('id', 'in', customer_ids)])

        model_data_ids = model_data_obj.search([
            ('fs_id', '=', 'act_open_customer'),
            ('module', '=', 'sale'),
            ('inherit', '=', False),
            ], limit=1)
        model_data = model_data_obj.browse(model_data_ids[0])
        wizard = wizard_obj.browse(model_data.db_id)

        res['name'] = wizard.name
        return res

OpenCustomer()


class HandleShipmentExceptionAsk(ModelView):
    'Shipment Exception Ask'
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

    def default_recreate_moves(self):
        return self.default_domain_moves()

    def default_domain_moves(self):
        sale_line_obj = self.pool.get('sale.line')
        active_id = Transaction().context.get('active_id')
        if not active_id:
            return []

        line_ids = sale_line_obj.search([
            ('sale', '=', active_id),
            ])
        lines = sale_line_obj.browse(line_ids)

        domain_moves = []
        for line in lines:
            skip_ids = set(x.id for x in line.moves_ignored)
            skip_ids.update(x.id for x in line.moves_recreated)
            for move in line.moves:
                if move.state == 'cancel' and move.id not in skip_ids:
                    domain_moves.append(move.id)

        return domain_moves

HandleShipmentExceptionAsk()

class HandleShipmentException(Wizard):
    'Handle Shipment Exception'
    _name = 'sale.handle.shipment.exception'
    states = {
        'init': {
            'actions': [],
            'result': {
                'type': 'form',
                'object': 'sale.handle.shipment.exception.ask',
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
        sale_obj = self.pool.get('sale.sale')
        sale_line_obj = self.pool.get('sale.line')
        move_obj = self.pool.get('stock.move')
        shipment_obj = self.pool.get('stock.shipment.out')
        to_recreate = data['form']['recreate_moves'][0][1]
        domain_moves = data['form']['domain_moves'][0][1]

        sale = sale_obj.browse(data['id'])

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

            sale_line_obj.write(line.id,{
                'moves_ignored': [('add', moves_ignored)],
                'moves_recreated': [('add', moves_recreated)],
                })

        sale_obj.workflow_trigger_validate(data['id'], 'shipment_ok')

HandleShipmentException()


class HandleInvoiceExceptionAsk(ModelView):
    'Invoice Exception Ask'
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

    def default_recreate_invoices(self):
        return self.default_domain_invoices()

    def default_domain_invoices(self):
        sale_obj = self.pool.get('sale.sale')
        active_id = Transaction().context.get('active_id')
        if not active_id:
            return []

        sale = sale_obj.browse(active_id)
        skip_ids = set(x.id for x in sale.invoices_ignored)
        skip_ids.update(x.id for x in sale.invoices_recreated)
        domain_invoices = []
        for invoice in sale.invoices:
            if invoice.state == 'cancel' and invoice.id not in skip_ids:
                domain_invoices.append(invoice.id)

        return domain_invoices

HandleInvoiceExceptionAsk()


class HandleInvoiceException(Wizard):
    'Handle Invoice Exception'
    _name = 'sale.handle.invoice.exception'
    states = {
        'init': {
            'actions': [],
            'result': {
                'type': 'form',
                'object': 'sale.handle.invoice.exception.ask',
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
        sale_obj = self.pool.get('sale.sale')
        invoice_obj = self.pool.get('account.invoice')
        to_recreate = data['form']['recreate_invoices'][0][1]
        domain_invoices = data['form']['domain_invoices'][0][1]

        sale = sale_obj.browse(data['id'])

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

        sale_obj.write(sale.id,{
            'invoices_ignored': [('add', invoices_ignored)],
            'invoices_recreated': [('add', invoices_recreated)],
             })

        sale_obj.workflow_trigger_validate(data['id'], 'invoice_ok')

HandleInvoiceException()
