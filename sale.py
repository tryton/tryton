#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"Sale"

from trytond.osv import fields, OSV
import datetime
from decimal import Decimal
from trytond.netsvc import LocalService
from trytond.report import CompanyReport


class Sale(OSV):
    'Sale'
    _name = 'sale.sale'
    _rec_name = 'reference'
    _description = __doc__

    company = fields.Many2One('company.company', 'Company', required=True,
            states={
                'readonly': "state != 'draft' or bool(lines)",
            })
    reference = fields.Char('Reference', readonly=True, select=1)
    description = fields.Char('Description', states={
        'readonly': "state != 'draft'",
        })
    state = fields.Selection([
        ('draft', 'Draft'),
        ('quotation', 'Quotation'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancel', 'Cancel'),
    ], 'State', readonly=True, required=True)
    sale_date = fields.Date('Sale Date', required=True, states={
        'readonly': "state != 'draft'",
        })
    payment_term = fields.Many2One('account.invoice.payment_term',
            'Payment Term', required=True, states={
                'readonly': "state != 'draft'",
            })
    party = fields.Many2One('relationship.party', 'Party', change_default=True,
            required=True, states={
                'readonly': "state != 'draft'",
            }, on_change=['party', 'payment_term'])
    party_lang = fields.Function('get_function_fields', type='char',
            string='Party Language', on_change_with=['party'])
    contact_address = fields.Many2One('relationship.address', 'Contact Address',
            domain="[('party', '=', party)]", states={
                'readonly': "state != 'draft'",
            })
    invoice_address = fields.Many2One('relationship.address', 'Invoice Address',
            domain="[('party', '=', party)]", states={
                'readonly': "state != 'draft'",
            })
    packing_address = fields.Many2One('relationship.address', 'Packing Address',
            domain="[('party', '=', party)]", states={
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
        ('packing', 'On Packing Sent'),
    ], 'Invoice Method', required=True, states={
        'readonly': "state != 'draft'",
        })
    invoice_state = fields.Selection([
        ('none', 'None'),
        ('waiting', 'Waiting'),
        ('paid', 'Paid'),
        ('exception', 'Exception'),
    ], 'Invoice State', readonly=True, required=True)
    invoices = fields.Many2Many('account.invoice', 'sale_invoices_rel',
            'sale', 'invoice', 'Invoices', readonly=True)
    invoices_ignored = fields.Many2Many('account.invoice',
            'sale_invoice_ignored_rel', 'sale', 'invoice',
            'Invoices Ignored', readonly=True)
    invoice_paid = fields.Function('get_function_fields', type='boolean',
            string='Invoices Paid')
    invoice_exception = fields.Function('get_function_fields', type='boolean',
            string='Invoices Exception')
    packing_method = fields.Selection([
        ('manual', 'Manual'),
        ('order', 'On Order Confirmed'),
        ('invoice', 'On Invoice Paid'),
    ], 'Packing Method', required=True, states={
        'readonly': "state != 'draft'",
        })
    packing_state = fields.Selection([
        ('none', 'None'),
        ('waiting', 'Waiting'),
        ('sent', 'Sent'),
        ('exception', 'Exception'),
    ], 'Packing State', readonly=True, required=True)
    packings = fields.Function('get_function_fields', type='many2many',
            relation='stock.packing.out', string='Packings')
    moves = fields.Function('get_function_fields', type='many2many',
            relation='stock.move', string='Moves')
    packing_done = fields.Function('get_function_fields', type='boolean',
            string='Packing Done')
    packing_exception = fields.Function('get_function_fields', type='boolean',
            string='Packings Exception')

    def __init__(self):
        super(Sale, self).__init__()
        self._constraints += [
            ('check_method', 'wrong_method')
        ]
        self._error_messages.update({
            'wrong_method': 'Wrong combination of method!',
        })

    def default_payment_term(self, cursor, user, context=None):
        payment_term_obj = self.pool.get('account.invoice.payment_term')
        payment_term_ids = payment_term_obj.search(cursor, user,
                self.payment_term._domain, context=context)
        if len(payment_term_ids) == 1:
            return payment_term_obj.name_get(cursor, user, payment_term_ids,
                    context=context)[0]
        return False

    def default_warehouse(self, cursor, user, context=None):
        location_obj = self.pool.get('stock.location')
        location_ids = location_obj.search(cursor, user,
                self.warehouse._domain, context=context)
        if len(location_ids) == 1:
            return location_obj.name_get(cursor, user, location_ids,
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

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def default_sale_date(self, cursor, user, context=None):
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

    def default_invoice_method(self, cursor, user, context=None):
        return 'order'

    def default_invoice_state(self, cursor, user, context=None):
        return 'none'

    def default_packing_method(self, cursor, user, context=None):
        return 'order'

    def default_packing_state(self, cursor, user, context=None):
        return 'none'

    def on_change_party(self, cursor, user, ids, vals, context=None):
        party_obj = self.pool.get('relationship.party')
        address_obj = self.pool.get('relationship.address')
        payment_term_obj = self.pool.get('account.invoice.payment_term')
        res = {
            'invoice_address': False,
            'contact_address': False,
            'packing_address': False,
            'payment_term': False,
        }
        if vals.get('party'):
            party = party_obj.browse(cursor, user, vals['party'],
                    context=context)
            res['contact_address'] = party_obj.address_get(cursor, user,
                    party.id, type=None, context=context)
            res['invoice_address'] = party_obj.address_get(cursor, user,
                    party.id, type='invoice', context=context)
            res['packing_address'] = party_obj.address_get(cursor, user,
                    party.id, type='delivery', context=context)
            if party.supplier_payment_term:
                res['payment_term'] = party.supplier_payment_term.id

        if res['contact_address']:
            res['contact_address'] = address_obj.name_get(cursor, user,
                    res['contact_address'], context=context)[0]
        if res['invoice_address']:
            res['invoice_address'] = address_obj.name_get(cursor, user,
                    res['invoice_address'], context=context)[0]
        if res['packing_address']:
            res['packing_address'] = address_obj.name_get(cursor, user,
                    res['packing_address'], context=context)[0]
        if res['payment_term']:
            res['payment_term'] = payment_term_obj.name_get(cursor, user,
                    res['payment_term'], context=context)[0]
        else:
            res['payment_term'] = self.default_payment_term(cursor, user,
                    context=context)
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
        party_obj = self.pool.get('relationship.party')
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
        party_obj = self.pool.get('relationship.party')
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
            for line in vals['lines']:
                if line.get('type', 'line') != 'line':
                    continue
                res['untaxed_amount'] += line.get('amount', Decimal('0.0'))

                for tax in tax_obj.compute(cursor, user, line.get('taxes', []),
                        line.get('unit_price', Decimal('0.0')),
                        line.get('quantity', 0.0), context=context):
                    res['tax_amount'] += tax['amount']
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
        if 'packings' in names:
            res['packings'] = self.get_packings(cursor, user, sales,
                    context=context)
        if 'moves' in names:
            res['moves'] = self.get_moves(cursor, user, sales, context=context)
        if 'packing_done' in names:
            res['packing_done'] = self.get_packing_done(cursor, user, sales,
                    context=context)
        if 'packing_exception' in names:
            res['packing_exception'] = self.get_packing_exception(cursor, user,
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
        if context is None:
            context = {}
        res = {}
        for sale in sales:
            ctx = context.copy()
            ctx.update(self.get_tax_context(cursor, user, sale,
                context=context))
            res.setdefault(sale.id, Decimal('0.0'))
            for line in sale.lines:
                if line.type != 'line':
                    continue
                # Don't round on each line to handle rounding error
                for tax in tax_obj.compute(cursor, user,
                        [t.id for t in line.taxes], line.unit_price,
                        line.quantity, context=ctx):
                    res[sale.id] += tax['amount']
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
            ignored_ids = [x.id for x in sale.invoices_ignored]
            for invoice in sale.invoices:
                if invoice.state != 'paid' \
                        and invoice.id not in ignored_ids:
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
            ignored_ids = [x.id for x in sale.invoices_ignored]
            for invoice in sale.invoices:
                if invoice.state == 'cancel' \
                        and invoice.id not in ignored_ids:
                    val = True
                    break
            res[sale.id] = val
        return res

    def get_packings(self, cursor, user, sales, context=None):
        '''
        Return packing_out ids for each sales

        :param cursor: the database cursor
        :param user: the user id
        :param sales: a BrowseRecordList of sales
        :param context: the context
        :return: a dictionary with sale id as key and
            a list of packing_out id as value
        '''
        res = {}
        for sale in sales:
            res[sale.id] = []
            for line in sale.lines:
                for move in line.moves:
                    if move.packing_out:
                        if move.packing_out.id not in res[sale.id]:
                            res[sale.id].append(move.packing_out.id)
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

    def get_packing_done(self, cursor, user, sales, context=None):
        '''
        Return if all the packings have been done for each sales

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

    def get_packing_exception(self, cursor, user, sales, context=None):
        '''
        Return if there is a packing exception for each sales

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
            if sale.invoice_method == 'packing' \
                    and sale.packing_method in ('invoice', 'manual'):
                return False
            if sale.packing_method == 'invoice' \
                    and sale.invoice_method in ('packing', 'manual'):
                return False
        return True

    def name_get(self, cursor, user, ids, context=None):
        if not ids:
            return []
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = []
        for sale in self.browse(cursor, user, ids, context=context):
            res.append((sale.id, sale.reference or str(sale.id) \
                    + ' ' + sale.party.name))
        return res

    def name_search(self, cursor, user, name='', args=None, operator='ilike',
            context=None, limit=None):
        if args is None:
            args = []
        if name:
            ids = self.search(cursor, user,
                    [('reference', operator, name)] + args, limit=limit,
                    context=context)
        if not ids:
            ids = self.search(cursor, user, [('party', operator, name)] + args,
                    limit=limit, context=context)
        res = self.name_get(cursor, user, ids, context=context)
        return res

    def copy(self, cursor, user, sale_id, default=None, context=None):
        if default is None:
            default = {}
        default = default.copy()
        default['state'] = 'draft'
        default['reference'] = False
        default['invoice_state'] = 'none'
        default['invoices'] = False
        default['invoices_ignored'] = False
        default['packing_state'] = 'none'
        return super(Sale, self).copy(cursor, user, sale_id, default=default,
                context=context)

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

        reference = sequence_obj.get(cursor, user, 'sale.sale')
        self.write(cursor, user, sale_id, {
            'reference': reference,
            }, context=context)
        return True

    def _get_invoice_line_sale_line(self, cursor, user, sale, context=None):
        '''
        Return a dictionary of invoice line values for each sale lines

        :param cursor: the database cursor
        :param user: the user id
        :param sale: the BrowseRecord of the sale
        :param context: the context

        :return: a dictionary with invoice line as key
            and invoice lines values as value
        '''
        line_obj = self.pool.get('sale.line')
        res = {}
        for line in sale.lines:
            val = line_obj.get_invoice_line(cursor, user, line,
                    context=context)
            if val:
                res[line.id] = val
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
        journal_obj = self.pool.get('account.journal')
        invoice_line_obj = self.pool.get('account.invoice.line')
        sale_line_obj = self.pool.get('sale.line')

        sale = self.browse(cursor, user, sale_id, context=context)

        invoice_lines = self._get_invoice_line_sale_line(cursor, user, sale,
                context=context)
        if not invoice_lines:
            return

        journal_id = journal_obj.search(cursor, user, [
            ('type', '=', 'revenue'),
            ], limit=1, context=context)
        if journal_id:
            journal_id = journal_id[0]

        invoice_id = invoice_obj.create(cursor, user, {
            'company': sale.company.id,
            'type': 'out_invoice',
            'reference': sale.reference,
            'journal': journal_id,
            'party': sale.party.id,
            'contact_address': sale.contact_address.id,
            'invoice_address': sale.invoice_address.id,
            'currency': sale.currency.id,
            'account': sale.party.account_receivable.id,
            'payment_term': sale.payment_term.id,
        }, context=context)

        for line_id in invoice_lines:
            vals = invoice_lines[line_id]
            vals['invoice'] = invoice_id
            invoice_line_id = invoice_line_obj.create(cursor, user, vals,
                    context=context)
            sale_line_obj.write(cursor, user, line_id, {
                'invoice_lines': [('add', invoice_line_id)],
                }, context=context)

        invoice_obj.update_taxes(cursor, user, [invoice_id], context=context)

        self.write(cursor, user, sale_id, {
            'invoices': [('add', invoice_id)],
        }, context=context)
        return invoice_id

    def ignore_invoice_exception(self, cursor, user, sale_id, context=None):
        sale = self.browse(cursor, user, sale_id, context=context)
        invoice_ids = []
        for invoice in sale.invoices:
            if invoice.state == 'cancel':
                invoice_ids.append(invoice.id)
        if invoice_ids:
            self.write(cursor, user, sale_id, {
                'invoices_ignored': [('add', x) for x in invoice_ids],
            }, context=context)

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

    def create_packing(self, cursor, user, sale_id, context=None):
        '''
        Create a packing for the sale

        :param cursor: the database cursor
        :param user: the user id
        :param sale_id: the sale id
        :param context: the context

        :return: the created packing id or None
        '''
        packing_obj = self.pool.get('stock.packing.out')
        move_obj = self.pool.get('stock.move')
        sale_line_obj = self.pool.get('sale.line')
        workflow_service = LocalService('workflow')

        sale = self.browse(cursor, user, sale_id, context=context)

        moves = self._get_move_sale_line(cursor, user, sale, context=context)
        if not moves:
            return

        packing_id = packing_obj.create(cursor, user, {
            'planned_date': sale.sale_date,
            'customer': sale.party.id,
            'delivery_address': sale.packing_address.id,
            'reference': sale.reference,
            'warehouse': sale.warehouse.id,
            'customer_location': sale.party.customer_location.id,
        }, context=context)

        for line_id in moves:
            vals = moves[line_id]
            vals['packing_out'] = packing_id
            move_id = move_obj.create(cursor, user, vals, context=context)
            sale_line_obj.write(cursor, user, line_id, {
                'moves': [('add', move_id)],
                }, context=context)
        workflow_service.trg_validate(user, 'stock.packing.out', packing_id,
                'waiting', cursor)
        return packing_id

    def ignore_packing_exception(self, cursor, user, sale_id, context=None):
        line_obj = self.pool.get('sale.line')

        sale = self.browse(cursor, user, sale_id, context=context)
        for line in sale.lines:
            line_obj.ignore_move_exception(cursor, user, line, context=context)

Sale()


class SaleLine(OSV):
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
        ], 'Type', select=1, required=True)
    quantity = fields.Float('Quantity',
            digits="(16, unit_digits)",
            states={
                'invisible': "type != 'line'",
                'required': "type == 'line'",
            }, on_change=['product', 'quantity', 'unit',
                '_parent_sale.currency', '_parent_sale.party'])
    unit = fields.Many2One('product.uom', 'Unit',
            states={
                'required': "product",
                'invisible': "type != 'line'",
            }, domain="[('category', '=', " \
                    "(product, 'product.default_uom.category'))]",
            on_change=['product', 'quantity', 'unit', '_parent_sale.currency',
                '_parent_sale.party'])
    unit_digits = fields.Function('get_unit_digits', type='integer',
            string='Unit Digits', on_change_with=['unit'])
    product = fields.Many2One('product.product', 'Product',
            domain=[('salable', '=', True)],
            states={
                'invisible': "type != 'line'",
            }, on_change=['product', 'unit', 'quantity', 'description',
                '_parent_sale.party', '_parent_sale.currency'],
            context="{'locations': [_parent_sale.warehouse], " \
                    "'stock_date_end': _parent_sale.sale_date}")
    unit_price = fields.Numeric('Unit Price', digits=(16, 4),
            states={
                'invisible': "type != 'line'",
                'required': "type == 'line'",
            })
    amount = fields.Function('get_amount', type='numeric', string='Amount',
            digits="(16, _parent_sale.currency_digits)",
            states={
                'invisible': "type not in ('line', 'subtotal')",
            }, on_change_with=['type', 'quantity', 'unit_price',
                '_parent_sale.currency'])
    description = fields.Char('Description', size=None, required=True)
    comment = fields.Text('Comment',
            states={
                'invisible': "type != 'line'",
            })
    taxes = fields.Many2Many('account.tax', 'sale_line_account_tax',
            'line', 'tax', 'Taxes', domain=[('parent', '=', False)],
            states={
                'invisible': "type != 'line'",
            })
    invoice_lines = fields.Many2Many('account.invoice.line',
            'sale_line_invoice_lines_rel', 'sale_line', 'invoice_line',
            'Invoice Lines', readonly=True)
    moves = fields.One2Many('stock.move', 'sale_line', 'Moves',
            readonly=True, select=1)
    moves_ignored = fields.Many2Many('stock.move', 'sale_line_moves_ignored_rel',
            'sale_line', 'move', 'Moves Ignored', readonly=True)
    move_done = fields.Function('get_move_done', type='boolean',
            string='Moves Done')
    move_exception = fields.Function('get_move_exception', type='boolean',
            string='Moves Exception')

    def __init__(self):
        super(SaleLine, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))
        self._error_messages.update({
            'missing_account_revenue': 'It miss ' \
                    'an "account_revenue" default property!',
            'customer_location_required': 'The customer location is required!',
            })

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
            ignored_ids = [x.id for x in line.moves_ignored]
            quantity = line.quantity
            for move in line.moves:
                if move.state != 'done' \
                        and move.id not in ignored_ids:
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
            ignored_ids = [x.id for x in line.moves_ignored]
            for move in line.moves:
                if move.state == 'cancel' \
                        and move.id not in ignored_ids:
                    val = True
                    break
            res[line.id] = val
        return res

    def on_change_product(self, cursor, user, ids, vals, context=None):
        party_obj = self.pool.get('relationship.party')
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')

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

        ctx2 = context.copy()
        if vals.get('_parent_sale.currency'):
            ctx2['currency'] = vals['_parent_sale.currency']
        if vals.get('_parent_sale.party'):
            ctx2['customer'] = vals['_parent_sale.party']
        if vals.get('unit'):
            ctx2['uom'] = vals['unit']
        else:
            ctx2['uom'] = product.sale_uom.id
        res['unit_price'] = product_obj.get_sale_price(cursor, user,
                [product.id], vals.get('quantity', 0), context=ctx2)[product.id]
        res['taxes'] = []
        for tax in product.customer_taxes_used:
            if party:
                if 'customer_' + tax.group.code in party_obj._columns \
                        and party['customer_' + tax.group.code]:
                    res['taxes'].append(
                            party['customer_' + tax.group.code].id)
                    continue
            res['taxes'].append(tax.id)

        if not vals.get('description'):
            res['description'] = product_obj.name_get(cursor, user, product.id,
                    context=ctx)[0][1]

        category = product.sale_uom.category
        if not vals.get('unit') \
                or vals.get('unit') not in [x.id for x in category.uoms]:
            res['unit'] = uom_obj.name_get(cursor, user, product.sale_uom.id,
                    context=context)[0]
            res['unit_digits'] = product.sale_uom.digits
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
        if vals.get('_parent_sale.currency'):
            ctx2['currency'] = vals['_parent_sale.currency']
        if vals.get('_parent_sale.party'):
            ctx2['customer'] = vals['_parent_sale.party']
        if vals.get('unit'):
            ctx2['uom'] = vals['unit']
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

        :return: a dictionary of values of invoice line
        '''
        uom_obj = self.pool.get('product.uom')
        property_obj = self.pool.get('ir.property')

        res = {}
        res['sequence'] = line.sequence
        res['type'] = line.type
        res['description'] = line.description
        if line.type != 'line':
            return res
        if line.sale.invoice_method == 'order':
            res['quantity'] = line.quantity
        else:
            quantity = 0.0
            for move in line.moves:
                if move.state == 'done':
                    quantity += uom_obj.compute_qty(cursor, user, move.uom,
                            move.quantity, line.unit, context=context)
            for invoice_line in line.invoice_lines:
                quantity -= uom_obj.compute_qty(cursor, user,
                        invoice_line.unit, invoice_line.quantity, line.unit,
                        context=context)
            res['quantity'] = quantity
        if res['quantity'] <= 0.0:
            return None
        res['unit'] = line.unit.id
        res['product'] = line.product.id
        res['unit_price'] = line.unit_price
        res['taxes'] = [('set', [x.id for x in line.taxes])]
        if line.product:
            res['account'] = line.product.account_revenue_used.id
        else:
            for model in ('product.template', 'product.category'):
                res['account'] = property_obj.get(cursor, user,
                        'account_revenue', model, context=context)
                if res['account']:
                    break
            if not res['account']:
                self.raise_user_error(cursor, 'missing_account_revenue',
                        context=context)
        return res

    def copy(self, cursor, user, line_id, default=None, context=None):
        if default is None:
            default = {}
        default = default.copy()
        default['moves'] = False
        default['moves_ignored'] = False
        default['invoice_lines'] = False
        return super(SaleLine, self).copy(cursor, user, line_id,
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
        quantity = line.quantity
        for move in line.moves:
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

    def ignore_move_exception(self, cursor, user, line, context=None):
        move_ids = []
        for move in line.moves:
            if move.state == 'cancel':
                move_ids.append(move.id)
        if move_ids:
            self.write(cursor, user, line.id, {
                'moves_ignored': [('add', x) for x in move_ids],
            }, context=context)

SaleLine()


class SaleReport(CompanyReport):
    _name = 'sale.sale'

SaleReport()


class Template(OSV):
    _name = 'product.template'

    salable = fields.Boolean('Salable', states={
        'readonly': "active == False",
        })
    sale_uom = fields.Many2One('product.uom', 'Sale UOM', states={
        'readonly': "active == False",
        'invisible': "not salable",
        'required': "salable",
        }, domain="[('category', '=', " \
                "(default_uom, 'uom.category'))]",
        on_change_with=['default_uom', 'sale_uom'])

    def default_salable(self, cursor, user, context=None):
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
        if res:
            res = uom_obj.name_get(cursor, user, res, context=context)[0]
        return res

Template()


class Product(OSV):
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
            if currency:
                if user2.company.currency.id != currency.id:
                    res[product.id] = currency_obj.compute(cursor, user,
                            user2.company.currency, res[product.id],
                            currency, context=context)
        return res

Product()


class PackingOut(OSV):
    _name = 'stock.packing.out'

    def write(self, cursor, user, ids, vals, context=None):
        workflow_service = LocalService('workflow')
        sale_line_obj = self.pool.get('sale.line')

        res = super(PackingOut, self).write(cursor, user, ids, vals,
                context=context)

        if 'state' in vals and vals['state'] in ('done', 'cancel'):
            sale_ids = []
            move_ids = []
            if isinstance(ids, (int, long)):
                ids = [ids]
            for packing in self.browse(cursor, user, ids, context=context):
                move_ids.extend([x.id for x in packing.outgoing_moves])

            sale_line_ids = sale_line_obj.search(cursor, user, [
                ('moves', 'in', move_ids),
                ], context=context)
            if sale_line_ids:
                for sale_line in sale_line_obj.browse(cursor, user,
                        sale_line_ids, context=context):
                    if sale_line.sale.id not in sale_ids:
                        sale_ids.append(sale_line.sale.id)

            for sale_id in sale_ids:
                workflow_service.trg_validate(user, 'sale.sale', sale_id,
                        'packing_update', cursor)
        return res

PackingOut()


class Move(OSV):
    _name = 'stock.move'

    sale_line = fields.Many2One('sale.line', select=1,
            states={
                'readonly': "state != 'draft'",
            })
    sale = fields.Function('get_sale', type='many2one',
            relation='sale.sale', string='Sale',
            fnct_search='search_sale', select=1)

    def get_sale(self, cursor, user, ids, name, arg, context=None):
        sale_obj = self.pool.get('sale.sale')

        res = {}
        for move in self.browse(cursor, user, ids, context=context):
            res[move.id] = False
            if move.sale_line:
                res[move.id] = move.sale_line.sale.id

        sale_names = {}
        for sale_id , sale_name in sale_obj.name_get(cursor, user,
                [x for x in res.values() if x], context=context):
            sale_names[sale_id] = sale_name

        for i in res.keys():
            if res[i] and res[i] in sale_names:
                res[i] = (res[i], sale_names[res[i]])
            else:
                res[i] = False
        return res

    def search_sale(self, cursor, user, name, args, context=None):
        args2 = []
        i = 0
        while i < len(args):
            field = args[i][0]
            args2.append(('sale_line.' + field, args[i][1], args[i][2]))
            i += 1
        return args2

    def write(self, cursor, user, ids, vals, context=None):
        workflow_service = LocalService('workflow')
        sale_line_obj = self.pool.get('sale.line')

        res = super(Move, self).write(cursor, user, ids, vals,
                context=context)
        if 'state' in vals and vals['state'] in ('cancel',):
            sale_ids = []
            sale_line_ids = sale_line_obj.search(cursor, user, [
                ('moves', 'in', ids),
                ], context=context)
            if sale_line_ids:
                for sale_line in sale_line_obj.browse(cursor, user,
                        sale_line_ids, context=context):
                    if sale_line.sale.id not in sale_ids:
                        sale_ids.append(sale_line.sale.id)
            for sale_id in sale_ids:
                workflow_service.trg_validate(user, 'sale.sale',
                        sale_id, 'packing_update', cursor)
        return res

Move()


class Invoice(OSV):
    _name = 'account.invoice'

    def __init__(self):
        super(Invoice, self).__init__()
        self._error_messages.update({
            'delete_sale_invoice': 'You can not delete invoices ' \
                    'that comes from a sale!',
            })

    def delete(self, cursor, user, ids, context=None):
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        cursor.execute('SELECT id FROM sale_invoices_rel ' \
                'WHERE invoice IN (' + ','.join(['%s' for x in ids]) + ')',
                ids)
        if cursor.rowcount:
            self.raise_user_error(cursor, 'delete_sale_invoice',
                    context=context)
        return super(Invoice, self).delete(cursor, user, ids,
                context=context)

Invoice()
