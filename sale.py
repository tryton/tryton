#This file is part of Tryton.  The COPYRIGHT file at the top level
#of this repository contains the full copyright notices and license terms.
"Sale"
from trytond.model import ModelWorkflow, ModelView, ModelSQL, fields
from trytond.modules.company import CompanyReport
from trytond.wizard import Wizard
from trytond.backend import TableHandler
from decimal import Decimal
import copy


class Sale(ModelWorkflow, ModelSQL, ModelView):
    'Sale'
    _name = 'sale.sale'
    _rec_name = 'reference'
    _description = __doc__

    company = fields.Many2One('company.company', 'Company', required=True,
            states={
                'readonly': "state != 'draft' or bool(lines)",
            }, domain=["('id', 'company' in context and '=' or '!=', " \
                    "context.get('company', 0))"])
    reference = fields.Char('Reference', readonly=True, select=1)
    description = fields.Char('Description', states={
        'readonly': "state != 'draft'",
        })
    state = fields.Selection([
        ('draft', 'Draft'),
        ('quotation', 'Quotation'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancel', 'Canceled'),
    ], 'State', readonly=True, required=True)
    sale_date = fields.Date('Sale Date', required=True, states={
        'readonly': "state != 'draft'",
        })
    payment_term = fields.Many2One('account.invoice.payment_term',
            'Payment Term', required=True, states={
                'readonly': "state != 'draft'",
            })
    party = fields.Many2One('party.party', 'Party', change_default=True,
            required=True, states={
                'readonly': "state != 'draft'",
            }, on_change=['party', 'payment_term'])
    party_lang = fields.Function('get_function_fields', type='char',
            string='Party Language', on_change_with=['party'])
    invoice_address = fields.Many2One('party.address', 'Invoice Address',
            domain=["('party', '=', party)"], states={
                'readonly': "state != 'draft'",
            })
    shipment_address = fields.Many2One('party.address', 'Shipment Address',
            domain=["('party', '=', party)"], states={
                'readonly': "state != 'draft'",
            })
    warehouse = fields.Many2One('stock.location', 'Warehouse',
            domain=[('type', '=', 'warehouse')], required=True, states={
                'readonly': "state != 'draft'",
            })
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states={
            'readonly': "state != 'draft' or (bool(lines) and bool(currency))",
        })
    currency_digits = fields.Function('get_function_fields', type='integer',
            string='Currency Digits', on_change_with=['currency'])
    lines = fields.One2Many('sale.line', 'sale', 'Lines', states={
        'readonly': "state != 'draft'",
        }, on_change=['lines', 'currency', 'party'])
    comment = fields.Text('Comment')
    untaxed_amount = fields.Function('get_function_fields', type='numeric',
            digits="(16, currency_digits)", string='Untaxed')
    tax_amount = fields.Function('get_function_fields', type='numeric',
            digits="(16, currency_digits)", string='Tax')
    total_amount = fields.Function('get_function_fields', type='numeric',
            digits="(16, currency_digits)", string='Total')
    invoice_method = fields.Selection([
        ('manual', 'Manual'),
        ('order', 'On Order Confirmed'),
        ('shipment', 'On Shipment Sent'),
    ], 'Invoice Method', required=True, states={
        'readonly': "state != 'draft'",
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
    invoice_paid = fields.Function('get_function_fields', type='boolean',
            string='Invoices Paid')
    invoice_exception = fields.Function('get_function_fields', type='boolean',
            string='Invoices Exception')
    shipment_method = fields.Selection([
        ('manual', 'Manual'),
        ('order', 'On Order Confirmed'),
        ('invoice', 'On Invoice Paid'),
    ], 'Shipment Method', required=True, states={
        'readonly': "state != 'draft'",
        })
    shipment_state = fields.Selection([
        ('none', 'None'),
        ('waiting', 'Waiting'),
        ('sent', 'Sent'),
        ('exception', 'Exception'),
    ], 'Shipment State', readonly=True, required=True)
    shipments = fields.Function('get_function_fields', type='many2many',
            relation='stock.shipment.out', string='Shipments')
    moves = fields.Function('get_function_fields', type='many2many',
            relation='stock.move', string='Moves')
    shipment_done = fields.Function('get_function_fields', type='boolean',
            string='Shipment Done')
    shipment_exception = fields.Function('get_function_fields', type='boolean',
            string='Shipments Exception')

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
            'missing_account_receivable': 'It misses ' \
                    'an "Account Receivable" on the party "%s"!',
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
        table.column_rename('packing_method', 'shipment_method')
        table.column_rename('packing_address', 'shipment_address')

        super(Sale, self).init(cursor, module_name)

        # Migration from 1.2
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

    def default_sale_date(self, cursor, user, context=None):
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

    def default_shipment_method(self, cursor, user, context=None):
        return 'order'

    def default_shipment_state(self, cursor, user, context=None):
        return 'none'

    def on_change_party(self, cursor, user, ids, vals, context=None):
        party_obj = self.pool.get('party.party')
        address_obj = self.pool.get('party.address')
        payment_term_obj = self.pool.get('account.invoice.payment_term')
        res = {
            'invoice_address': False,
            'shipment_address': False,
            'payment_term': False,
        }
        if vals.get('party'):
            party = party_obj.browse(cursor, user, vals['party'],
                    context=context)
            res['invoice_address'] = party_obj.address_get(cursor, user,
                    party.id, type='invoice', context=context)
            res['shipment_address'] = party_obj.address_get(cursor, user,
                    party.id, type='delivery', context=context)
            if party.payment_term:
                res['payment_term'] = party.payment_term.id

        if res['invoice_address']:
            res['invoice_address.rec_name'] = address_obj.browse(cursor, user,
                    res['invoice_address'], context=context).rec_name
        if res['shipment_address']:
            res['shipment_address.rec_name'] = address_obj.browse(cursor, user,
                    res['shipment_address'], context=context).rec_name
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

    def get_currency_digits(self, cursor, user, sales, context=None):
        '''
        Return the number of digits of the currency of each sales

        :param cursor: the database cursor
        :param user: the user id
        :param sales: a BrowseRecordList of puchases
        :param context: the context
        :return: a dictionary with sale id as key and
            number of digits as value
        '''
        res = {}
        for sale in sales:
            res[sale.id] = sale.currency.digits
        return res

    def get_tax_context(self, cursor, user, sale, context=None):
        party_obj = self.pool.get('party.party')
        res = {}
        if isinstance(sale, dict):
            if sale.get('party'):
                party = party_obj.browse(cursor, user, sale['party'],
                        context=context)
                if party.lang:
                    res['language'] = party.lang.code
        else:
            if sale.party.lang:
                res['language'] = sale.party.lang.code
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

    def get_party_lang(self, cursor, user, sales, context=None):
        '''
        Return the code lang of the party for each sales

        :param cursor: the database cursor
        :param user: the user id
        :param sales: a BrowseRecordList of sales
        :param context: the context
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
                            'out_invoice', context=context)
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
        Function to compute function fields for sale ids

        :param cursor: the database cursor
        :param user: the user id
        :param ids: the ids of the sales
        :param names: the list of field name to compute
        :param args: optional argument
        :param context: the context
        :return: a dictionary with all field names as key and
            a dictionary as value with id as key
        '''
        res = {}
        sales = self.browse(cursor, user, ids, context=context)
        if 'currency_digits' in names:
            res['currency_digits'] = self.get_currency_digits(cursor, user,
                    sales, context=context)
        if 'party_lang' in names:
            res['party_lang'] = self.get_party_lang(cursor, user, sales,
                    context=context)
        if 'untaxed_amount' in names:
            res['untaxed_amount'] = self.get_untaxed_amount(cursor, user,
                    sales, context=context)
        if 'tax_amount' in names:
            res['tax_amount'] = self.get_tax_amount(cursor, user, sales,
                    context=context)
        if 'total_amount' in names:
            res['total_amount'] = self.get_total_amount(cursor, user, sales,
                    context=context)
        if 'invoice_paid' in names:
            res['invoice_paid'] = self.get_invoice_paid(cursor, user, sales,
                    context=context)
        if 'invoice_exception' in names:
            res['invoice_exception'] = self.get_invoice_exception(cursor, user,
                    sales, context=context)
        if 'shipments' in names:
            res['shipments'] = self.get_shipments(cursor, user, sales,
                    context=context)
        if 'moves' in names:
            res['moves'] = self.get_moves(cursor, user, sales, context=context)
        if 'shipment_done' in names:
            res['shipment_done'] = self.get_shipment_done(cursor, user, sales,
                    context=context)
        if 'shipment_exception' in names:
            res['shipment_exception'] = self.get_shipment_exception(cursor, user,
                    sales, context=context)
        return res

    def get_untaxed_amount(self, cursor, user, sales, context=None):
        '''
        Compute the untaxed amount for each sales

        :param cursor: the database cursor
        :param user: the user id
        :param sales: a BrowseRecordList of sales
        :param context: the context
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
            res[sale.id] = currency_obj.round(cursor, user, sale.currency,
                    res[sale.id])
        return res

    def get_tax_amount(self, cursor, user, sales, context=None):
        '''
        Compute tax amount for each sales

        :param cursor: the database cursor
        :param user: the user id
        :param sales: a BrowseRecordList of sales
        :param context: the context
        :return: a dictionary with sale id as key and
            tax amount as value
        '''
        currency_obj = self.pool.get('currency.currency')
        tax_obj = self.pool.get('account.tax')
        invoice_obj = self.pool.get('account.invoice')

        if context is None:
            context = {}
        res = {}
        for sale in sales:
            ctx = context.copy()
            ctx.update(self.get_tax_context(cursor, user, sale,
                context=context))
            res.setdefault(sale.id, Decimal('0.0'))
            taxes = {}
            for line in sale.lines:
                if line.type != 'line':
                    continue
                # Don't round on each line to handle rounding error
                for tax in tax_obj.compute(cursor, user,
                        [t.id for t in line.taxes], line.unit_price,
                        line.quantity, context=ctx):
                    key, val = invoice_obj._compute_tax(cursor, user, tax,
                            'out_invoice', context=context)
                    if not key in taxes:
                        taxes[key] = val['amount']
                    else:
                        taxes[key] += val['amount']
            for key in taxes:
                res[sale.id] += currency_obj.round(cursor, user,
                        sale.currency, taxes[key])
            res[sale.id] = currency_obj.round(cursor, user, sale.currency,
                    res[sale.id])
        return res

    def get_total_amount(self, cursor, user, sales, context=None):
        '''
        Return the total amount of each sales

        :param cursor: the database cursor
        :param user: the user id
        :param sales: a BrowseRecordList of sales
        :param context: the context
        :return: a dictionary with sale id as key and
            total amount as value
        '''
        currency_obj = self.pool.get('currency.currency')
        res = {}
        untaxed_amounts = self.get_untaxed_amount(cursor, user, sales,
                context=context)
        tax_amounts = self.get_tax_amount(cursor, user, sales,
                context=context)
        for sale in sales:
            res[sale.id] = currency_obj.round(cursor, user, sale.currency,
                    untaxed_amounts[sale.id] + tax_amounts[sale.id])
        return res

    def get_invoice_paid(self, cursor, user, sales, context=None):
        '''
        Return if all invoices have been paid for each sales

        :param cursor: the database cursor
        :param user: the user id
        :param sales: a BrowseRecordList of sales
        :param context: the context
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

    def get_invoice_exception(self, cursor, user, sales, context=None):
        '''
        Return if there is an invoice exception for each sales

        :param cursor: the database cursor
        :param user: the user id
        :param sales: a BrowseRecordList of sales
        :param context: the context
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

    def get_shipments(self, cursor, user, sales, context=None):
        '''
        Return shipment_out ids for each sales

        :param cursor: the database cursor
        :param user: the user id
        :param sales: a BrowseRecordList of sales
        :param context: the context
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

    def get_moves(self, cursor, user, sales, context=None):
        '''
        Return move ids for each sales

        :param cursor: the database cursor
        :param user: the user id
        :param sales: a BrowseRecordList of sales
        :param context: the context
        :return: a dictionary with sale id as key and
            a list of move ids as value
        '''
        res = {}
        for sale in sales:
            res[sale.id] = []
            for line in sale.lines:
                res[sale.id].extend([x.id for x in line.moves])
        return res

    def get_shipment_done(self, cursor, user, sales, context=None):
        '''
        Return if all the shipments have been done for each sales

        :param cursor: the database cursor
        :param user: the user id
        :param sales: a BrowseRecordList of sales
        :param context: the context
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

    def get_shipment_exception(self, cursor, user, sales, context=None):
        '''
        Return if there is a shipment exception for each sales

        :param cursor: the database cursor
        :param user: the user id
        :param sales: a BrowseRecordList of sales
        :param context: the context
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

    def check_method(self, cursor, user, ids):
        '''
        Check the methods.
        '''
        for sale in self.browse(cursor, user, ids):
            if sale.invoice_method == 'shipment' \
                    and sale.shipment_method in ('invoice', 'manual'):
                return False
            if sale.shipment_method == 'invoice' \
                    and sale.invoice_method in ('shipment', 'manual'):
                return False
        return True

    def get_rec_name(self, cursor, user, ids, name, arg, context=None):
        if not ids:
            return []
        res = {}
        for sale in self.browse(cursor, user, ids, context=context):
            res[sale.id] = sale.reference or str(sale.id) \
                    + ' - ' + sale.party.rec_name
        return res

    def search_rec_name(self, cursor, user, name, args, context=None):
        args2 = []
        i = 0
        while i < len(args):
            names = args[i][2].split(' - ', 1)
            args2.append(('reference', args[i][1], names[0]))
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
        return super(Sale, self).copy(cursor, user, ids, default=default,
                context=context)

    def check_for_quotation(self, cursor, user, sale_id, context=None):
        sale = self.browse(cursor, user, sale_id, context=context)
        if not sale.invoice_address or not sale.shipment_address:
            self.raise_user_error(cursor, 'addresses_required', context=context)
        return True

    def set_reference(self, cursor, user, sale_id, context=None):
        '''
        Fill the reference field with the sale sequence

        :param cursor: the database cursor
        :param user: the user id
        :param sale_id: the id of the sale
        :param context: the context

        :return: True if succeed
        '''
        sequence_obj = self.pool.get('ir.sequence')

        sale = self.browse(cursor, user, sale_id, context=context)

        if sale.reference:
            return True

        reference = sequence_obj.get(cursor, user, 'sale.sale',
                context=context)
        self.write(cursor, user, sale_id, {
            'reference': reference,
            }, context=context)
        return True

    def _get_invoice_line_sale_line(self, cursor, user, sale, context=None):
        '''
        Return invoice line values for each sale lines

        :param cursor: the database cursor
        :param user: the user id
        :param sale: the BrowseRecord of the sale
        :param context: the context

        :return: a dictionary with invoiced sale line id as key
            and a list of invoice lines values as value
        '''
        line_obj = self.pool.get('sale.line')
        res = {}
        for line in sale.lines:
            val = line_obj.get_invoice_line(cursor, user, line,
                    context=context)
            if val:
                res[line.id] = val
        return res

    def _get_invoice_sale(self, cursor, user, sale, context=None):
        '''
        Return invoice values for sale

        :param cursor: the database cursor
        :param user: the user id
        :param sale: the BrowseRecord of the sale
        :param context: the context

        :return: a dictionary with invoice fields as key and
            invoice values as value
        '''
        journal_obj = self.pool.get('account.journal')

        journal_id = journal_obj.search(cursor, user, [
            ('type', '=', 'revenue'),
            ], limit=1, context=context)
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

    def create_invoice(self, cursor, user, sale_id, context=None):
        '''
        Create an invoice for the sale

        :param cursor: the database cursor
        :param user: the user id
        :param sale_id: the sale id
        :param context: the context

        :return: the created invoice id or None
        '''
        invoice_obj = self.pool.get('account.invoice')
        invoice_line_obj = self.pool.get('account.invoice.line')
        sale_line_obj = self.pool.get('sale.line')

        if context is None:
            context = {}

        sale = self.browse(cursor, user, sale_id, context=context)

        if not sale.party.account_receivable:
            self.raise_user_error(cursor, 'missing_account_receivable',
                    error_args=(sale.party.rec_name,), context=context)

        invoice_lines = self._get_invoice_line_sale_line(cursor, user, sale,
                context=context)
        if not invoice_lines:
            return


        ctx = context.copy()
        ctx['user'] = user
        vals = self._get_invoice_sale(cursor, user, sale, context=context)
        invoice_id = invoice_obj.create(cursor, 0, vals, context=ctx)

        for line in sale.lines:
            if line.id not in invoice_lines:
                continue
            for vals in invoice_lines[line.id]:
                vals['invoice'] = invoice_id
                invoice_line_id = invoice_line_obj.create(cursor, 0, vals,
                        context=ctx)
                sale_line_obj.write(cursor, user, line.id, {
                    'invoice_lines': [('add', invoice_line_id)],
                    }, context=context)

        invoice_obj.update_taxes(cursor, 0, [invoice_id], context=ctx)

        self.write(cursor, user, sale_id, {
            'invoices': [('add', invoice_id)],
        }, context=context)
        return invoice_id

    def _get_move_sale_line(self, cursor, user, sale, context=None):
        '''
        Return a dictionary of move values for each sale lines

        :param cursor: the database cursor
        :param user: the user id
        :param sale: the BrowseRecord of the sale
        :param context: the context

        :return: a dictionary with move as key and move values as value
        '''
        line_obj = self.pool.get('sale.line')
        res = {}
        for line in sale.lines:
            val = line_obj.get_move(cursor, user, line, context=context)
            if val:
                res[line.id] = val
        return res

    def create_shipment(self, cursor, user, sale_id, context=None):
        '''
        Create a shipment for the sale

        :param cursor: the database cursor
        :param user: the user id
        :param sale_id: the sale id
        :param context: the context

        :return: the created shipment id or None
        '''
        shipment_obj = self.pool.get('stock.shipment.out')
        move_obj = self.pool.get('stock.move')
        sale_line_obj = self.pool.get('sale.line')

        if context is None:
            context = {}

        sale = self.browse(cursor, user, sale_id, context=context)

        moves = self._get_move_sale_line(cursor, user, sale, context=context)
        if not moves:
            return

        ctx = context.copy()
        ctx['user'] = user
        shipment_id = shipment_obj.create(cursor, 0, {
            'planned_date': sale.sale_date,
            'customer': sale.party.id,
            'delivery_address': sale.shipment_address.id,
            'reference': sale.reference,
            'warehouse': sale.warehouse.id,
        }, context=ctx)

        for line_id in moves:
            vals = moves[line_id]
            vals['shipment_out'] = shipment_id
            move_id = move_obj.create(cursor, 0, vals, context=ctx)
            sale_line_obj.write(cursor, 0, line_id, {
                'moves': [('add', move_id)],
                }, context=ctx)
        shipment_obj.workflow_trigger_validate(cursor, 0, shipment_id,
                'waiting', context=ctx)
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
            digits="(16, unit_digits)",
            states={
                'invisible': "type != 'line'",
                'required': "type == 'line'",
                'readonly': "not globals().get('_parent_sale')",
            }, on_change=['product', 'quantity', 'unit',
                '_parent_sale.currency', '_parent_sale.party'])
    unit = fields.Many2One('product.uom', 'Unit',
            states={
                'required': "product",
                'invisible': "type != 'line'",
                'readonly': "not globals().get('_parent_sale')",
            }, domain=["('category', '=', " \
                    "(product, 'product.default_uom.category'))"],
            context="{'category': (product, 'product.default_uom.category')}",
            on_change=['product', 'quantity', 'unit', '_parent_sale.currency',
                '_parent_sale.party'])
    unit_digits = fields.Function('get_unit_digits', type='integer',
            string='Unit Digits', on_change_with=['unit'])
    product = fields.Many2One('product.product', 'Product',
            domain=[('salable', '=', True)],
            states={
                'invisible': "type != 'line'",
                'readonly': "not globals().get('_parent_sale')",
            }, on_change=['product', 'unit', 'quantity', 'description',
                '_parent_sale.party', '_parent_sale.currency'],
            context="{'locations': " \
                        "_parent_sale.warehouse and [_parent_sale.warehouse] " \
                        "or False, " \
                    "'stock_date_end': _parent_sale.sale_date, " \
                    "'salable': True, " \
                    "'stock_skip_warehouse': True}")
    unit_price = fields.Numeric('Unit Price', digits=(16, 4),
            states={
                'invisible': "type != 'line'",
                'required': "type == 'line'",
            })
    amount = fields.Function('get_amount', type='numeric', string='Amount',
            digits="(16, _parent_sale.currency_digits)",
            states={
                'invisible': "type not in ('line', 'subtotal')",
                'readonly': "not globals().get('_parent_sale')",
            }, on_change_with=['type', 'quantity', 'unit_price', 'unit',
                '_parent_sale.currency'])
    description = fields.Text('Description', size=None, required=True)
    note = fields.Text('Note')
    taxes = fields.Many2Many('sale.line-account.tax', 'line', 'tax', 'Taxes',
            domain=[('parent', '=', False)], states={
                'invisible': "type != 'line'",
            })
    invoice_lines = fields.Many2Many('sale.line-account.invoice.line',
            'sale_line', 'invoice_line', 'Invoice Lines', readonly=True)
    moves = fields.One2Many('stock.move', 'sale_line', 'Moves',
            readonly=True, select=1)
    moves_ignored = fields.Many2Many('sale.line-ignored-stock.move',
            'sale_line', 'move', 'Ignored Moves', readonly=True)
    moves_recreated = fields.Many2Many('sale.line-recreated-stock.move',
            'sale_line', 'move', 'Recreated Moves', readonly=True)
    move_done = fields.Function('get_move_done', type='boolean',
            string='Moves Done')
    move_exception = fields.Function('get_move_exception', type='boolean',
            string='Moves Exception')

    def __init__(self):
        super(SaleLine, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))
        self._error_messages.update({
            'customer_location_required': 'The customer location is required!',
            'missing_account_revenue': 'It misses ' \
                    'an "Account Revenue" on product "%s"!',
            'missing_account_revenue_property': 'It misses ' \
                    'an "account Revenue" default property!',
            })

    def init(self, cursor, module_name):
        super(SaleLine, self).init(cursor, module_name)
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
            skip_ids = set(x.id for x in line.moves_ignored)
            skip_ids.update(x.id for x in line.moves_recreated)
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
            skip_ids = set(x.id for x in line.moves_ignored)
            skip_ids.update(x.id for x in line.moves_recreated)
            for move in line.moves:
                if move.state == 'cancel' \
                        and move.id not in skip_ids:
                    val = True
                    break
            res[line.id] = val
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

    def _get_context_sale_price(self, cursor, user, product, vals,
            context=None):
        if context is None:
            context = {}
        ctx2 = context.copy()
        if vals.get('_parent_sale.currency'):
            ctx2['currency'] = vals['_parent_sale.currency']
        if vals.get('_parent_sale.party'):
            ctx2['customer'] = vals['_parent_sale.party']
        if vals.get('unit'):
            ctx2['uom'] = vals['unit']
        else:
            ctx2['uom'] = product.sale_uom.id
        return ctx2

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
        if vals.get('_parent_sale.party'):
            party = party_obj.browse(cursor, user, vals['_parent_sale.party'],
                    context=context)
            if party.lang:
                ctx['language'] = party.lang.code

        product = product_obj.browse(cursor, user, vals['product'],
                context=context)

        ctx2 = self._get_context_sale_price(cursor, user, product, vals,
                context=context)
        res['unit_price'] = product_obj.get_sale_price(cursor, user,
                [product.id], vals.get('quantity', 0), context=ctx2)[product.id]
        res['taxes'] = []
        pattern = self._get_tax_rule_pattern(cursor, user, party,
                vals, context=context)
        for tax in product.customer_taxes_used:
            if party and party.customer_tax_rule:
                tax_ids = tax_rule_obj.apply(cursor, user,
                        party.customer_tax_rule, tax, pattern,
                        context=context)
                if tax_ids:
                    res['taxes'].extend(tax_ids)
                continue
            res['taxes'].append(tax.id)
        if party and party.customer_tax_rule:
            tax_ids = tax_rule_obj.apply(cursor, user,
                    party.customer_tax_rule, False, pattern,
                    context=context)
            if tax_ids:
                res['taxes'].extend(tax_ids)

        if not vals.get('description'):
            res['description'] = product_obj.browse(cursor, user, product.id,
                    context=ctx).rec_name

        category = product.sale_uom.category
        if not vals.get('unit') \
                or vals.get('unit') not in [x.id for x in category.uoms]:
            res['unit'] = product.sale_uom.id
            res['unit.rec_name'] = product.sale_uom.rec_name
            res['unit_digits'] = product.sale_uom.digits

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

        ctx2 = self._get_context_sale_price(cursor, user, product, vals,
                context=context)
        res['unit_price'] = product_obj.get_sale_price(cursor, user,
                [vals['product']], vals.get('quantity', 0),
                context=ctx2)[vals['product']]
        return res

    def on_change_unit(self, cursor, user, ids, vals, context=None):
        return self.on_change_quantity(cursor, user, ids, vals, context=context)

    def on_change_with_amount(self, cursor, user, ids, vals, context=None):
        currency_obj = self.pool.get('currency.currency')
        if vals.get('type') == 'line':
            if isinstance(vals.get('_parent_sale.currency'), (int, long)):
                currency = currency_obj.browse(cursor, user,
                        vals['_parent_sale.currency'], context=context)
            else:
                currency = vals['_parent_sale.currency']
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
                        line.sale.currency,
                        Decimal(str(line.quantity)) * line.unit_price)
            elif line.type == 'subtotal':
                res[line.id] = Decimal('0.0')
                for line2 in line.sale.lines:
                    if line2.type == 'line':
                        res[line.id] += currency_obj.round(cursor, user,
                                line2.sale.currency,
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
        Return invoice line values for sale line

        :param cursor: the database cursor
        :param user: the user id
        :param line: the BrowseRecord of the line
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

        if (line.sale.invoice_method == 'order'
                or not line.product
                or line.product.type == 'service'):
            quantity = line.quantity
        else:
            quantity = 0.0
            for move in line.moves:
                if move.state == 'done':
                    quantity += uom_obj.compute_qty(cursor, user, move.uom,
                            move.quantity, line.unit, context=context)

        ignored_ids = set(
            l.id for i in line.sale.invoices_ignored for l in i.lines)
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
            res['account'] = line.product.account_revenue_used.id
            if not res['account']:
                self.raise_user_error(cursor, 'missing_account_revenue',
                        error_args=(line.product.rec_name,), context=context)
        else:
            for model in ('product.template', 'product.category'):
                res['account'] = property_obj.get(cursor, user,
                        'account_revenue', model, context=context)
                if res['account']:
                    break
            if not res['account']:
                self.raise_user_error(cursor,
                        'missing_account_revenue_property', context=context)
        return [res]

    def copy(self, cursor, user, ids, default=None, context=None):
        if default is None:
            default = {}
        default = default.copy()
        default['moves'] = False
        default['moves_ignored'] = False
        default['moves_recreated'] = False
        default['invoice_lines'] = False
        return super(SaleLine, self).copy(cursor, user, ids,
                default=default, context=context)

    def get_move(self, cursor, user, line, context=None):
        '''
        Return move values for the sale line

        :param cursor: the database cursor
        :param user: the user id
        :param line: the BrowseRecord of the line
        :param context: the context

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
                quantity -= uom_obj.compute_qty(cursor, user, move.uom,
                        move.quantity, line.unit, context=context)
        if quantity <= 0.0:
            return
        if not line.sale.party.customer_location:
            self.raise_user_error(cursor, 'customer_location_required',
                    context=context)
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
        'readonly': "active == False",
        })
    sale_uom = fields.Many2One('product.uom', 'Sale UOM', states={
        'readonly': "active == False",
        'invisible': "not salable",
        'required': "salable",
        }, domain=["('category', '=', (default_uom, 'uom.category'))"],
        context="{'category': (default_uom, 'uom.category')}",
        on_change_with=['default_uom', 'sale_uom', 'salable'])

    def __init__(self):
        super(Template, self).__init__()
        if 'not bool(account_category) and bool(salable)' not in \
                self.account_revenue.states.get('required', ''):
            self.account_revenue = copy.copy(self.account_revenue)
            self.account_revenue.states = copy.copy(self.account_revenue.states)
            if not self.account_revenue.states.get('required'):
                self.account_revenue.states['required'] = \
                        "not bool(account_category) and bool(salable)"
            else:
                self.account_revenue.states['required'] = '(' + \
                        self.account_revenue.states['required'] + ') ' \
                        'or (not bool(account_category) and bool(salable))'
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

    def default_salable(self, cursor, user, context=None):
        if context is None:
            context = {}
        if context.get('salable'):
            return True
        return False

    def on_change_with_sale_uom(self, cursor, user, ids, vals, context=None):
        uom_obj = self.pool.get('product.uom')
        res = False

        if vals.get('default_uom'):
            default_uom = uom_obj.browse(cursor, user, vals['default_uom'],
                    context=context)
            if vals.get('sale_uom'):
                sale_uom = uom_obj.browse(cursor, user, vals['sale_uom'],
                        context=context)
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

    def on_change_with_sale_uom(self, cursor, user, ids, vals, context=None):
        template_obj = self.pool.get('product.template')
        return template_obj.on_change_with_sale_uom(cursor, user, ids, vals,
                context=context)

    def get_sale_price(self, cursor, user, ids, quantity=0, context=None):
        '''
        Return the sale price for product ids.

        :param cursor: the database cursor
        :param user: the user id
        :param ids: the product ids
        :param quantity: the quantity of the products
        :param context: the context that can have as keys:
            uom: the unit of measure
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
            res[product.id] = product.list_price
            if uom:
                res[product.id] = uom_obj.compute_price(cursor, user,
                        product.default_uom, res[product.id], uom,
                        context=context)
            if currency and user2.company:
                if user2.company.currency.id != currency.id:
                    res[product.id] = currency_obj.compute(cursor, user,
                            user2.company.currency, res[product.id],
                            currency, context=context)
        return res

Product()


class ShipmentOut(ModelSQL, ModelView):
    _name = 'stock.shipment.out'

    def __init__(self):
        super(ShipmentOut, self).__init__()
        self._error_messages.update({
                'reset_move': 'You cannot reset to draft a move generated '\
                    'by a sale.',
            })

    def write(self, cursor, user, ids, vals, context=None):
        sale_obj = self.pool.get('sale.sale')
        sale_line_obj = self.pool.get('sale.line')

        res = super(ShipmentOut, self).write(cursor, user, ids, vals,
                context=context)

        if 'state' in vals and vals['state'] in ('done', 'cancel'):
            sale_ids = []
            move_ids = []
            if isinstance(ids, (int, long)):
                ids = [ids]
            for shipment in self.browse(cursor, user, ids, context=context):
                move_ids.extend([x.id for x in shipment.outgoing_moves])

            sale_line_ids = sale_line_obj.search(cursor, user, [
                ('moves', 'in', move_ids),
                ], context=context)
            if sale_line_ids:
                for sale_line in sale_line_obj.browse(cursor, user,
                        sale_line_ids, context=context):
                    if sale_line.sale.id not in sale_ids:
                        sale_ids.append(sale_line.sale.id)

            sale_obj.workflow_trigger_validate(cursor, user, sale_ids,
                    'shipment_update', context=context)
        return res

    def button_draft(self, cursor, user, ids, context=None):
        for shipment in self.browse(cursor, user, ids, context=context):
            for move in shipment.outgoing_moves:
                if move.state == 'cancel' and move.sale_line:
                    self.raise_user_error(cursor, 'reset_move')

        return super(ShipmentOut, self).button_draft(
            cursor, user, ids, context=context)

ShipmentOut()


class Move(ModelSQL, ModelView):
    _name = 'stock.move'

    sale_line = fields.Many2One('sale.line', select=1,
            states={
                'readonly': "state != 'draft'",
            })
    sale = fields.Function('get_sale', type='many2one',
            relation='sale.sale', string='Sale',
            fnct_search='search_sale', select=1)
    sale_exception_state = fields.Function('get_sale_exception_state',
            type='selection',
            selection=[('', ''),
                       ('ignored', 'Ignored'),
                       ('recreated', 'Recreated')],
            string='Exception State')

    def get_sale(self, cursor, user, ids, name, arg, context=None):
        sale_obj = self.pool.get('sale.sale')

        res = {}
        for move in self.browse(cursor, user, ids, context=context):
            res[move.id] = False
            if move.sale_line:
                res[move.id] = move.sale_line.sale.id
        return res

    def search_sale(self, cursor, user, name, args, context=None):
        args2 = []
        i = 0
        while i < len(args):
            field = args[i][0]
            args2.append(('sale_line.' + field, args[i][1], args[i][2]))
            i += 1
        return args2

    def get_sale_exception_state(self, cursor, user, ids, name, arg,
                                 context=None):
        res = {}.fromkeys(ids, '')
        for move in self.browse(cursor, user, ids, context=context):
            if not move.sale_line:
                continue
            if move.id in (x.id for x in move.sale_line.moves_recreated):
                res[move.id] = 'recreated'
            if move.id in (x.id for x in move.sale_line.moves_ignored):
                res[move.id] = 'ignored'
        return res

    def write(self, cursor, user, ids, vals, context=None):
        sale_obj = self.pool.get('sale.sale')
        sale_line_obj = self.pool.get('sale.line')

        res = super(Move, self).write(cursor, user, ids, vals,
                context=context)
        if 'state' in vals and vals['state'] in ('cancel',):
            if isinstance(ids, (int, long)):
                ids = [ids]
            sale_ids = set()
            sale_line_ids = sale_line_obj.search(cursor, user, [
                ('moves', 'in', ids),
                ], context=context)
            if sale_line_ids:
                for sale_line in sale_line_obj.browse(cursor, user,
                        sale_line_ids, context=context):
                    sale_ids.add(sale_line.sale.id)
            if sale_ids:
                sale_obj.workflow_trigger_validate(cursor, user, list(sale_ids),
                        'shipment_update', context=context)
        return res

    def delete(self, cursor, user, ids, context=None):
        sale_obj = self.pool.get('sale.sale')
        sale_line_obj = self.pool.get('sale.line')

        if isinstance(ids, (int, long)):
            ids = [ids]

        sale_ids = set()
        sale_line_ids = sale_line_obj.search(cursor, user, [
            ('moves', 'in', ids),
            ], context=context)

        res = super(Move, self).delete(cursor, user, ids, context=context)

        if sale_line_ids:
            for sale_line in sale_line_obj.browse(cursor, user,
                    sale_line_ids, context=context):
                sale_ids.add(sale_line.sale.id)
            if sale_ids:
                sale_obj.workflow_trigger_validate(cursor, user, list(sale_ids),
                        'shipment_update', context=context)
        return res

Move()


class Invoice(ModelSQL, ModelView):
    _name = 'account.invoice'

    sale_exception_state = fields.Function('get_sale_exception_state',
            type='selection',
            selection=[('', ''),
                       ('ignored', 'Ignored'),
                       ('recreated', 'Recreated')],
            string='Exception State')

    def __init__(self):
        super(Invoice, self).__init__()
        self._error_messages.update({
            'delete_sale_invoice': 'You can not delete invoices ' \
                    'that come from a sale!',
            'reset_invoice_sale': 'You cannot reset to draft ' \
                    'an invoice generated by a sale.',
            })

    def button_draft(self, cursor, user, ids, context=None):
        sale_obj = self.pool.get('sale.sale')
        sale_ids = sale_obj.search(
            cursor, user, [('invoices', 'in', ids)], context=context)

        if sale_ids:
            self.raise_user_error(cursor, 'reset_invoice_sale')

        return super(Invoice, self).button_draft(
            cursor, user, ids, context=context)

    def get_sale_exception_state(self, cursor, user, ids, name, arg,
                                 context=None):
        sale_obj = self.pool.get('sale.sale')
        sale_ids = sale_obj.search(
            cursor, user, [('invoices', 'in', ids)], context=context)

        sales = sale_obj.browse(
            cursor, user, sale_ids, context=context)

        recreated_ids = tuple(i.id for p in sales for i in p.invoices_recreated)
        ignored_ids = tuple(i.id for p in sales for i in p.invoices_ignored)

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
        cursor.execute('SELECT id FROM sale_invoices_rel ' \
                'WHERE invoice IN (' + ','.join(('%s',) * len(ids)) + ')',
                ids)
        if cursor.fetchone():
            self.raise_user_error(cursor, 'delete_sale_invoice',
                    context=context)
        return super(Invoice, self).delete(cursor, user, ids,
                context=context)

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
        cursor.execute("SELECT DISTINCT(party) FROM sale_sale")
        customer_ids = [line[0] for line in cursor.fetchall()]
        res['domain'] = str([('id', 'in', customer_ids)])

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_open_customer'),
            ('module', '=', 'sale'),
            ('inherit', '=', False),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        wizard = wizard_obj.browse(cursor, user, model_data.db_id,
                context=context)

        res['name'] = wizard.name
        return res

OpenCustomer()


class HandleShipmentExceptionAsk(ModelView):
    'Shipment Exception Ask'
    _name = 'sale.handle.shipment.exception.ask'
    _description = __doc__

    recreate_moves = fields.Many2Many(
        'stock.move', None, None, 'Recreate Moves',
        domain=["('id', 'in', domain_moves)"], depends=['domain_moves'])
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
        sale_line_obj = self.pool.get('sale.line')
        active_id = context and context.get('active_id')
        if not active_id:
            return []

        line_ids = sale_line_obj.search(
            cursor, user, [('sale', '=', active_id)],
            context=context)
        lines = sale_line_obj.browse(cursor, user, line_ids, context=context)

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

    def _handle_moves(self, cursor, user, data, context=None):
        sale_obj = self.pool.get('sale.sale')
        sale_line_obj = self.pool.get('sale.line')
        move_obj = self.pool.get('stock.move')
        shipment_obj = self.pool.get('stock.shipment.out')
        to_recreate = data['form']['recreate_moves'][0][1]
        domain_moves = data['form']['domain_moves'][0][1]

        sale = sale_obj.browse(cursor, user, data['id'], context=context)

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

            sale_line_obj.write(
                cursor, user, line.id,
                {'moves_ignored': [('add', moves_ignored)],
                 'moves_recreated': [('add', moves_recreated)]},
                context=context)

        sale_obj.workflow_trigger_validate(cursor, user, data['id'],
                'shipment_ok', context=context)

HandleShipmentException()


class HandleInvoiceExceptionAsk(ModelView):
    'Invoice Exception Ask'
    _name = 'sale.handle.invoice.exception.ask'
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
        sale_obj = self.pool.get('sale.sale')
        active_id = context and context.get('active_id')
        if not active_id:
            return []

        sale = sale_obj.browse(
            cursor, user, active_id, context=context)
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

    def _handle_invoices(self, cursor, user, data, context=None):
        sale_obj = self.pool.get('sale.sale')
        invoice_obj = self.pool.get('account.invoice')
        to_recreate = data['form']['recreate_invoices'][0][1]
        domain_invoices = data['form']['domain_invoices'][0][1]

        sale = sale_obj.browse(cursor, user, data['id'], context=context)

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

        sale_obj.write(
            cursor, user, sale.id,
            {'invoices_ignored': [('add', invoices_ignored)],
             'invoices_recreated': [('add', invoices_recreated)],
             },
            context=context)

        sale_obj.workflow_trigger_validate(cursor, user, data['id'],
                'invoice_ok', context=context)

HandleInvoiceException()
