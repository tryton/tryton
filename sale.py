#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
import datetime
from itertools import groupby, chain
from functools import partial
from trytond.model import Workflow, ModelView, ModelSQL, fields
from trytond.modules.company import CompanyReport
from trytond.wizard import Wizard, StateAction, StateView, StateTransition, \
    Button
from trytond.backend import TableHandler
from trytond.pyson import If, Eval, Bool, PYSONEncoder, Id
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

__all__ = ['Sale', 'SaleInvoice', 'SaleIgnoredInvoice', 'SaleRecreatedInvoice',
    'SaleLine', 'SaleLineTax', 'SaleLineIgnoredMove',
    'SaleLineRecreatedMove', 'SaleReport', 'Template', 'Product',
    'ShipmentOut', 'ShipmentOutReturn', 'Move', 'OpenCustomer',
    'HandleShipmentExceptionAsk', 'HandleShipmentException',
    'HandleInvoiceExceptionAsk', 'HandleInvoiceException',
    'ReturnSale']
__metaclass__ = PoolMeta


class Sale(Workflow, ModelSQL, ModelView):
    'Sale'
    __name__ = 'sale.sale'
    _rec_name = 'reference'
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
            on_change_with=['party']), 'on_change_with_party_lang')
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
            on_change_with=['currency']), 'on_change_with_currency_digits')
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
        'get_moves')

    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()
        cls._order.insert(0, ('sale_date', 'DESC'))
        cls._order.insert(1, ('id', 'DESC'))
        cls._error_messages.update({
                'invalid_method': ('Invalid combination of shipment and '
                    'invoicing methods on sale "%s".'),
                'addresses_required': ('Invoice and Shipment addresses must be '
                    'defined for the quotation of sale "%s".'),
                'warehouse_required': ('Warehouse must be defined for the '
                    'quotation of sale "%s".'),
                'missing_account_receivable': ('It misses '
                        'an "Account Receivable" on the party "%s".'),
                'delete_cancel': ('Sale "%s" must be cancelled before '
                    'deletion.'),
                })
        cls._transitions |= set((
                ('draft', 'quotation'),
                ('quotation', 'confirmed'),
                ('confirmed', 'processing'),
                ('processing', 'processing'),
                ('draft', 'cancel'),
                ('quotation', 'cancel'),
                ('quotation', 'draft'),
                ('cancel', 'draft'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': ~Eval('state').in_(['draft', 'quotation']),
                    },
                'draft': {
                    'invisible': ~Eval('state').in_(['cancel', 'quotation']),
                    'icon': If(Eval('state') == 'cancel', 'tryton-clear',
                        'tryton-go-previous'),
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
                'handle_invoice_exception': {
                    'invisible': ((Eval('invoice_state') != 'exception')
                        | (Eval('state') == 'cancel')),
                    'readonly': ~Eval('groups', []).contains(
                        Id('sale', 'group_sale')),
                    },
                'handle_shipment_exception': {
                    'invisible': ((Eval('shipment_state') != 'exception')
                        | (Eval('state') == 'cancel')),
                    'readonly': ~Eval('groups', []).contains(
                        Id('sale', 'group_sale')),
                    },
                })
        # The states where amounts are cached
        cls._states_cached = ['confirmed', 'processing', 'done', 'cancel']

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        sale_line_invoice_line_table = 'sale_line_invoice_lines_rel'
        Move = pool.get('stock.move')
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
        table = TableHandler(cursor, cls, module_name)
        table.column_rename('packing_state', 'shipment_state')
        table.column_rename('packing_method', 'shipment_method')
        table.column_rename('packing_address', 'shipment_address')

        super(Sale, cls).__register__(module_name)

        # Migration from 1.2
        cursor.execute("UPDATE " + cls._table + " "
                "SET invoice_method = 'shipment' "
                "WHERE invoice_method = 'packing'")

        table = TableHandler(cursor, cls, module_name)
        # Migration from 2.2
        table.not_null_action('sale_date', 'remove')

        # state confirmed splitted into confirmed and processing
        if (TableHandler.table_exist(cursor, SaleLine._table)
                and TableHandler.table_exist(cursor,
                    sale_line_invoice_line_table)
                and TableHandler.table_exist(cursor, Move._table)):
            # Wrap subquery inside an other inner subquery because MySQL syntax
            # doesn't allow update a table and select from the same table in a
            # subquery.
            cursor.execute('UPDATE "%s" '
                "SET state = 'processing' "
                'WHERE id IN ('
                    'SELECT id '
                    'FROM ('
                        'SELECT s.id '
                        'FROM "%s" AS s '
                        'INNER JOIN "%s" AS l ON l.sale = s.id '
                        'LEFT JOIN "%s" AS li ON li.sale_line = l.id '
                        'LEFT JOIN "%s" AS m ON m.origin = \'%s,\' || l.id '
                        "WHERE s.state = 'confirmed' "
                            'AND (li.id IS NOT NULL '
                                'OR m.id IS NOT NULL)) AS foo)'
                % (cls._table, cls._table, SaleLine._table,
                    sale_line_invoice_line_table, Move._table,
                    SaleLine.__name__))

        # Add index on create_date
        table = TableHandler(cursor, cls, module_name)
        table.index_action('create_date', action='add')

    @classmethod
    def default_payment_term(cls):
        PaymentTerm = Pool().get('account.invoice.payment_term')
        payment_terms = PaymentTerm.search(cls.payment_term.domain)
        if len(payment_terms) == 1:
            return payment_terms[0].id

    @classmethod
    def default_warehouse(cls):
        Location = Pool().get('stock.location')
        locations = Location.search(cls.warehouse.domain)
        if len(locations) == 1:
            return locations[0].id

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            return Company(company).currency.id

    @staticmethod
    def default_currency_digits():
        Company = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            return Company(company).currency.digits
        return 2

    @staticmethod
    def default_invoice_method():
        Config = Pool().get('sale.configuration')
        config = Config(1)
        return config.sale_invoice_method

    @staticmethod
    def default_invoice_state():
        return 'none'

    @staticmethod
    def default_shipment_method():
        Config = Pool().get('sale.configuration')
        config = Config(1)
        return config.sale_shipment_method

    @staticmethod
    def default_shipment_state():
        return 'none'

    def on_change_party(self):
        invoice_address = None
        shipment_address = None
        payment_term = None
        if self.party:
            invoice_address = self.party.address_get(type='invoice')
            shipment_address = self.party.address_get(type='delivery')
            if self.party.customer_payment_term:
                payment_term = self.party.customer_payment_term

        changes = {}
        if invoice_address:
            changes['invoice_address'] = invoice_address.id
            changes['invoice_address.rec_name'] = invoice_address.rec_name
        else:
            changes['invoice_address'] = None
        if shipment_address:
            changes['shipment_address'] = shipment_address.id
            changes['shipment_address.rec_name'] = shipment_address.rec_name
        else:
            changes['shipment_address'] = None
        if payment_term:
            changes['payment_term'] = payment_term.id
            changes['payment_term.rec_name'] = payment_term.rec_name
        else:
            changes['payment_term'] = self.default_payment_term()
        return changes

    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2

    def get_tax_context(self):
        res = {}
        if self.party and self.party.lang:
            res['language'] = self.party.lang.code
        return res

    def on_change_with_party_lang(self, name=None):
        Config = Pool().get('ir.configuration')
        if self.party and self.party.lang:
            return self.party.lang.code
        return Config.get_language()

    def on_change_lines(self):
        pool = Pool()
        Tax = pool.get('account.tax')
        Invoice = pool.get('account.invoice')

        res = {
            'untaxed_amount': Decimal('0.0'),
            'tax_amount': Decimal('0.0'),
            'total_amount': Decimal('0.0'),
            }

        if self.lines:
            taxes = {}
            for line in self.lines:
                if getattr(line, 'type', 'line') != 'line':
                    continue
                res['untaxed_amount'] += line.amount or Decimal(0)
                tax_list = ()
                with Transaction().set_context(self.get_tax_context()):
                    tax_list = Tax.compute(getattr(line, 'taxes', []),
                        line.unit_price or Decimal('0.0'),
                        line.quantity or 0.0)
                for tax in tax_list:
                    key, val = Invoice._compute_tax(tax, 'out_invoice')
                    if not key in taxes:
                        taxes[key] = val['amount']
                    else:
                        taxes[key] += val['amount']
            if self.currency:
                for key in taxes:
                    res['tax_amount'] += self.currency.round(taxes[key])
        if self.currency:
            res['untaxed_amount'] = self.currency.round(res['untaxed_amount'])
            res['tax_amount'] = self.currency.round(res['tax_amount'])
        res['total_amount'] = res['untaxed_amount'] + res['tax_amount']
        if self.currency:
            res['total_amount'] = self.currency.round(res['total_amount'])
        return res

    def get_untaxed_amount(self, name):
        if (self.state in self._states_cached
                and self.untaxed_amount_cache is not None):
            return self.untaxed_amount_cache
        amount = sum((l.amount for l in self.lines if l.type == 'line'),
            Decimal(0))
        return self.currency.round(amount)

    def get_tax_amount(self, name):
        pool = Pool()
        Tax = pool.get('account.tax')
        Invoice = pool.get('account.invoice')

        if (self.state in self._states_cached
                and self.tax_amount_cache is not None):
            return self.tax_amount_cache
        context = self.get_tax_context()
        taxes = {}
        for line in self.lines:
            if line.type != 'line':
                continue
            with Transaction().set_context(context):
                tax_list = Tax.compute(line.taxes, line.unit_price,
                    line.quantity)
            # Don't round on each line to handle rounding error
            for tax in tax_list:
                key, val = Invoice._compute_tax(tax, 'out_invoice')
                if not key in taxes:
                    taxes[key] = val['amount']
                else:
                    taxes[key] += val['amount']
        amount = sum((self.currency.round(taxes[key]) for key in taxes),
            Decimal(0))
        return self.currency.round(amount)

    def get_total_amount(self, name):
        if (self.state in self._states_cached
                and self.total_amount_cache is not None):
            return self.total_amount_cache
        return self.currency.round(self.untaxed_amount + self.tax_amount)

    def get_invoice_state(self):
        '''
        Return the invoice state for the sale.
        '''
        skip_ids = set(x.id for x in self.invoices_ignored)
        skip_ids.update(x.id for x in self.invoices_recreated)
        invoices = [i for i in self.invoices if i.id not in skip_ids]
        if invoices:
            if any(i.state == 'cancel' for i in invoices):
                return 'exception'
            elif all(i.state == 'paid' for i in invoices):
                return 'paid'
            else:
                return 'waiting'
        return 'none'

    def set_invoice_state(self):
        '''
        Set the invoice state.
        '''
        state = self.get_invoice_state()
        if self.invoice_state != state:
            self.write([self], {
                    'invoice_state': state,
                    })

    def get_shipments_returns(model_name):
        "Computes the returns or shipments"
        def method(self, name):
            Model = Pool().get(model_name)
            shipments = set()
            for line in self.lines:
                for move in line.moves:
                    if isinstance(move.shipment, Model):
                        shipments.add(move.shipment.id)
            return list(shipments)
        return method

    get_shipments = get_shipments_returns('stock.shipment.out')
    get_shipment_returns = get_shipments_returns('stock.shipment.out.return')

    def get_moves(self, name):
        return [m.id for l in self.lines for m in l.moves]

    def get_shipment_state(self):
        '''
        Return the shipment state for the sale.
        '''
        if self.moves:
            if any(l.move_exception for l in self.lines):
                return 'exception'
            elif all(l.move_done for l in self.lines):
                return 'sent'
            else:
                return 'waiting'
        return 'none'

    def set_shipment_state(self):
        '''
        Set the shipment state.
        '''
        state = self.get_shipment_state()
        if self.shipment_state != state:
            self.write([self], {
                    'shipment_state': state,
                    })

    @classmethod
    def validate(cls, sales):
        super(Sale, cls).validate(sales)
        for sale in sales:
            sale.check_method()

    def check_method(self):
        '''
        Check the methods.
        '''
        if (self.invoice_method == 'shipment'
                and self.shipment_method in ('invoice', 'manual')):
            self.raise_user_error('invalid_method', (self.rec_name,))
        if (self.shipment_method == 'invoice'
                and self.invoice_method in ('shipment', 'manual')):
            self.raise_user_error('invalid_method', (self.rec_name,))

    def get_rec_name(self, name):
        return (self.reference or str(self.id)
            + ' - ' + self.party.rec_name)

    @classmethod
    def search_rec_name(cls, name, clause):
        names = clause[2].split(' - ', 1)
        res = [('reference', clause[1], names[0])]
        if len(names) != 1 and names[1]:
            res.append(('party', clause[1], names[1]))
        return res

    @classmethod
    def copy(cls, sales, default=None):
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
        return super(Sale, cls).copy(sales, default=default)

    def check_for_quotation(self):
        if not self.invoice_address or not self.shipment_address:
            self.raise_user_error('addresses_required', (self.rec_name,))
        for line in self.lines:
            if line.quantity >= 0:
                location = line.from_location
            else:
                location = line.to_location
            if ((not location or not line.warehouse)
                    and line.product
                    and line.product.type in ('goods', 'assets')):
                self.raise_user_error('warehouse_required',
                    (self.rec_name,))

    @classmethod
    def set_reference(cls, sales):
        '''
        Fill the reference field with the sale sequence
        '''
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Config = pool.get('sale.configuration')

        config = Config(1)
        for sale in sales:
            if sale.reference:
                continue
            reference = Sequence.get_id(config.sale_sequence.id)
            cls.write([sale], {
                    'reference': reference,
                    })

    @classmethod
    def set_sale_date(cls, sales):
        Date = Pool().get('ir.date')
        for sale in sales:
            if not sale.sale_date:
                cls.write([sale], {
                        'sale_date': Date.today(),
                        })

    @classmethod
    def store_cache(cls, sales):
        for sale in sales:
            cls.write([sale], {
                    'untaxed_amount_cache': sale.untaxed_amount,
                    'tax_amount_cache': sale.tax_amount,
                    'total_amount_cache': sale.total_amount,
                    })

    def _get_invoice_line_sale_line(self, invoice_type):
        '''
        Return invoice line for each sale lines according to invoice_type
        '''
        res = {}
        for line in self.lines:
            val = line.get_invoice_line(invoice_type)
            if val:
                res[line.id] = val
        return res

    def _get_invoice_sale(self, invoice_type):
        '''
        Return invoice of type invoice_type
        '''
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Journal = pool.get('account.journal')

        journals = Journal.search([
                ('type', '=', 'revenue'),
                ], limit=1)
        if journals:
            journal, = journals
        else:
            journal = None

        with Transaction().set_user(0, set_context=True):
            return Invoice(
                company=self.company,
                type=invoice_type,
                reference=self.reference,
                journal=journal,
                party=self.party,
                invoice_address=self.invoice_address,
                currency=self.currency,
                account=self.party.account_receivable,
                payment_term=self.payment_term,
                )

    def create_invoice(self, invoice_type):
        '''
        Create and return an invoice of type invoice_type
        '''
        pool = Pool()
        Invoice = pool.get('account.invoice')
        if self.invoice_method == 'manual':
            return

        if not self.party.account_receivable:
            self.raise_user_error('missing_account_receivable',
                (self.party.rec_name,))

        invoice_lines = self._get_invoice_line_sale_line(invoice_type)
        if not invoice_lines:
            return

        invoice = self._get_invoice_sale(invoice_type)
        invoice.lines = list(chain.from_iterable(invoice_lines.itervalues()))
        invoice.save()

        with Transaction().set_user(0, set_context=True):
            Invoice.update_taxes([invoice])

        self.write([self], {
                'invoices': [('add', [invoice.id])],
                })
        return invoice

    def _get_move_sale_line(self, shipment_type):
        '''
        Return move for each sale lines of the right shipment_type
        '''
        res = {}
        for line in self.lines:
            val = line.get_move(shipment_type)
            if val:
                res[line.id] = val
        return res

    def _group_shipment_key(self, moves, move):
        '''
        The key to group moves by shipments

        move is a tuple of line id and a move
        '''
        SaleLine = Pool().get('sale.line')
        line_id, move = move
        line = SaleLine(line_id)

        planned_date = max(m.planned_date for m in moves)
        return (
            ('planned_date', planned_date),
            ('warehouse', line.warehouse.id),
            )

    _group_return_key = _group_shipment_key

    def create_shipment(self, shipment_type):
        '''
        Create and return shipments of type shipment_type
        '''
        pool = Pool()

        if self.shipment_method == 'manual':
            return

        moves = self._get_move_sale_line(shipment_type)
        if not moves:
            return
        if shipment_type == 'out':
            keyfunc = partial(self._group_shipment_key, moves.values())
            Shipment = pool.get('stock.shipment.out')
        elif shipment_type == 'return':
            keyfunc = partial(self._group_return_key, moves.values())
            Shipment = pool.get('stock.shipment.out.return')
        moves = moves.items()
        moves = sorted(moves, key=keyfunc)

        shipments = []
        for key, grouped_moves in groupby(moves, key=keyfunc):
            values = {
                'customer': self.party.id,
                'delivery_address': self.shipment_address.id,
                'reference': self.reference,
                'company': self.company.id,
                }
            values.update(dict(key))
            with Transaction().set_user(0, set_context=True):
                shipment = Shipment(**values)
                shipment.moves = [x[1] for x in grouped_moves]
                shipment.save()
                shipments.append(shipment)
        if shipment_type == 'out':
            with Transaction().set_user(0, set_context=True):
                Shipment.wait(shipments)
        return shipments

    def is_done(self):
        return ((self.invoice_state == 'paid'
                or self.invoice_method == 'manual')
            and (self.shipment_state == 'sent'
                or self.shipment_method == 'manual'))

    @classmethod
    def delete(cls, sales):
        # Cancel before delete
        cls.cancel(sales)
        for sale in sales:
            if sale.state != 'cancel':
                cls.raise_user_error('delete_cancel', (sale.rec_name,))
        super(Sale, cls).delete(sales)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, sales):
        cls.store_cache(sales)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, sales):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('quotation')
    def quote(cls, sales):
        for sale in sales:
            sale.check_for_quotation()
        cls.set_reference(sales)

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(cls, sales):
        cls.set_sale_date(sales)
        cls.store_cache(sales)

    @classmethod
    @ModelView.button_action('sale.wizard_invoice_handle_exception')
    def handle_invoice_exception(cls, sales):
        pass

    @classmethod
    @ModelView.button_action('sale.wizard_shipment_handle_exception')
    def handle_shipment_exception(cls, sales):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('processing')
    def process(cls, sales):
        done = []
        for sale in sales:
            if sale.state in ('done', 'cancel'):
                continue
            sale.create_invoice('out_invoice')
            sale.create_invoice('out_credit_note')
            sale.set_invoice_state()
            sale.create_shipment('out')
            sale.create_shipment('return')
            sale.set_shipment_state()
            if sale.is_done():
                done.append(sale)
        if done:
            cls.write(done, {
                    'state': 'done',
                    })


class SaleInvoice(ModelSQL):
    'Sale - Invoice'
    __name__ = 'sale.sale-account.invoice'
    _table = 'sale_invoices_rel'
    sale = fields.Many2One('sale.sale', 'Sale', ondelete='CASCADE',
        select=True, required=True)
    invoice = fields.Many2One('account.invoice', 'Invoice',
            ondelete='RESTRICT', select=True, required=True)


class SaleIgnoredInvoice(ModelSQL):
    'Sale - Ignored Invoice'
    __name__ = 'sale.sale-ignored-account.invoice'
    _table = 'sale_invoice_ignored_rel'
    sale = fields.Many2One('sale.sale', 'Sale', ondelete='CASCADE',
        select=True, required=True)
    invoice = fields.Many2One('account.invoice', 'Invoice',
            ondelete='RESTRICT', select=True, required=True)


class SaleRecreatedInvoice(ModelSQL):
    'Sale - Recreated Invoice'
    __name__ = 'sale.sale-recreated-account.invoice'
    _table = 'sale_invoice_recreated_rel'
    sale = fields.Many2One('sale.sale', 'Sale', ondelete='CASCADE',
        select=True, required=True)
    invoice = fields.Many2One('account.invoice', 'Invoice',
            ondelete='RESTRICT', select=True, required=True)


class SaleLine(ModelSQL, ModelView):
    'Sale Line'
    __name__ = 'sale.line'
    _rec_name = 'description'
    sale = fields.Many2One('sale.sale', 'Sale', ondelete='CASCADE',
        select=True)
    sequence = fields.Integer('Sequence',
        order_field='(%(table)s.sequence IS NULL) %(order)s, '
        '%(table)s.sequence %(order)s')
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
            '_parent_sale.currency', '_parent_sale.party',
            '_parent_sale.sale_date'],
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
        on_change_with=['unit']), 'on_change_with_unit_digits')
    product = fields.Many2One('product.product', 'Product',
        domain=[('salable', '=', True)],
        states={
            'invisible': Eval('type') != 'line',
            'readonly': ~Eval('_parent_sale', {}),
            },
        on_change=['product', 'unit', 'quantity', 'description',
            '_parent_sale.party', '_parent_sale.currency',
            '_parent_sale.sale_date'],
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
        'on_change_with_product_uom_category')
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
        domain=[('parent', '=', None), ['OR',
                ('group', '=', None),
                ('group.kind', 'in', ['sale', 'both'])],
            ],
        states={
            'invisible': Eval('type') != 'line',
            }, depends=['type'])
    invoice_lines = fields.One2Many('account.invoice.line', 'origin',
        'Invoice Lines', readonly=True)
    moves = fields.One2Many('stock.move', 'origin', 'Moves', readonly=True)
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
        'on_change_with_delivery_date')

    @classmethod
    def __setup__(cls):
        super(SaleLine, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))
        cls._error_messages.update({
                'customer_location_required': ('Sale "%(sale)s" is missing the '
                    'customer location in line "%(line)s".'),
                'missing_account_revenue': ('Product "%(product)s" of sale '
                    '%(sale)s misses a revenue account.'),
                'missing_account_revenue_property': ('Sale "%(sale)s" '
                    'misses an "account revenue" default property.'),
                })

    @classmethod
    def __register__(cls, module_name):
        super(SaleLine, cls).__register__(module_name)
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

        # Migration from 1.0 comment change into note
        if table.column_exist('comment'):
            cursor.execute('UPDATE "' + cls._table + '" SET note = comment')
            table.drop_column('comment', exception=True)

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')

    @staticmethod
    def default_type():
        return 'line'

    @staticmethod
    def default_unit_digits():
        return 2

    def on_change_with_unit_digits(self, name=None):
        if self.unit:
            return self.unit.digits
        return 2

    def get_move_done(self, name):
        Uom = Pool().get('product.uom')
        done = True
        if not self.product:
            return True
        if self.product.type == 'service':
            return True
        skip_ids = set(x.id for x in self.moves_ignored)
        skip_ids.update(x.id for x in self.moves_recreated)
        quantity = self.quantity
        for move in self.moves:
            if move.state != 'done' \
                    and move.id not in skip_ids:
                done = False
                break
            quantity -= Uom.compute_qty(move.uom, move.quantity, self.unit)
        if done:
            if quantity > 0.0:
                done = False
        return done

    def get_move_exception(self, name):
        skip_ids = set(x.id for x in self.moves_ignored)
        skip_ids.update(x.id for x in self.moves_recreated)
        for move in self.moves:
            if move.state == 'cancel' \
                    and move.id not in skip_ids:
                return True
        return False

    def _get_tax_rule_pattern(self):
        '''
        Get tax rule pattern
        '''
        return {}

    def _get_context_sale_price(self):
        context = {}
        if getattr(self, 'sale', None):
            if getattr(self.sale, 'currency', None):
                context['currency'] = self.sale.currency.id
            if getattr(self.sale, 'party', None):
                context['customer'] = self.sale.party.id
            if getattr(self.sale, 'sale_date', None):
                context['sale_date'] = self.sale.sale_date
        if self.unit:
            context['uom'] = self.unit.id
        else:
            context['uom'] = self.product.sale_uom.id
        return context

    def on_change_product(self):
        Product = Pool().get('product.product')

        if not self.product:
            return {}
        res = {}

        party = None
        party_context = {}
        if self.sale and self.sale.party:
            party = self.sale.party
            if party.lang:
                party_context['language'] = party.lang.code

        category = self.product.sale_uom.category
        if not self.unit or self.unit not in category.uoms:
            res['unit'] = self.product.sale_uom.id
            self.unit = self.product.sale_uom
            res['unit.rec_name'] = self.product.sale_uom.rec_name
            res['unit_digits'] = self.product.sale_uom.digits

        with Transaction().set_context(self._get_context_sale_price()):
            res['unit_price'] = Product.get_sale_price([self.product],
                    self.quantity or 0)[self.product.id]
            if res['unit_price']:
                res['unit_price'] = res['unit_price'].quantize(
                    Decimal(1) / 10 ** self.__class__.unit_price.digits[1])
        res['taxes'] = []
        pattern = self._get_tax_rule_pattern()
        for tax in self.product.customer_taxes_used:
            if party and party.customer_tax_rule:
                tax_ids = party.customer_tax_rule.apply(tax, pattern)
                if tax_ids:
                    res['taxes'].extend(tax_ids)
                continue
            res['taxes'].append(tax.id)
        if party and party.customer_tax_rule:
            tax_ids = party.customer_tax_rule.apply(None, pattern)
            if tax_ids:
                res['taxes'].extend(tax_ids)

        if not self.description:
            with Transaction().set_context(party_context):
                res['description'] = Product(self.product.id).rec_name

        self.unit_price = res['unit_price']
        self.type = 'line'
        res['amount'] = self.on_change_with_amount()
        return res

    def on_change_with_product_uom_category(self, name=None):
        if self.product:
            return self.product.default_uom_category.id

    def on_change_quantity(self):
        Product = Pool().get('product.product')

        if not self.product:
            return {}
        res = {}

        with Transaction().set_context(
                self._get_context_sale_price()):
            res['unit_price'] = Product.get_sale_price([self.product],
                self.quantity or 0)[self.product.id]
            if res['unit_price']:
                res['unit_price'] = res['unit_price'].quantize(
                    Decimal(1) / 10 ** self.__class__.unit_price.digits[1])
        return res

    def on_change_unit(self):
        return self.on_change_quantity()

    def on_change_with_amount(self):
        if self.type == 'line':
            currency = self.sale.currency if self.sale else None
            amount = Decimal(str(self.quantity or '0.0')) * \
                (self.unit_price or Decimal('0.0'))
            if currency:
                return currency.round(amount)
            return amount
        return Decimal('0.0')

    def get_amount(self, name):
        if self.type == 'line':
            return self.sale.currency.round(
                Decimal(str(self.quantity)) * self.unit_price)
        elif self.type == 'subtotal':
            amount = Decimal('0.0')
            for line2 in self.sale.lines:
                if line2.type == 'line':
                    amount += line2.sale.currency.round(
                        Decimal(str(line2.quantity)) * line2.unit_price)
                elif line2.type == 'subtotal':
                    if self == line2:
                        break
                    amount = Decimal('0.0')
            return amount
        return Decimal('0.0')

    def get_warehouse(self, name):
        return self.sale.warehouse.id if self.sale.warehouse else None

    def get_from_location(self, name):
        if self.quantity >= 0:
            if self.warehouse:
                return self.warehouse.output_location.id
        else:
            return self.sale.party.customer_location.id

    def get_to_location(self, name):
        if self.quantity >= 0:
            return self.sale.party.customer_location.id
        else:
            if self.warehouse:
                return self.warehouse.input_location.id

    def on_change_with_delivery_date(self, name=None):
        if self.product:
            date = self.sale.sale_date if self.sale else None
            return self.product.compute_delivery_date(date=date)

    def get_invoice_line(self, invoice_type):
        '''
        Return a list of invoice lines for sale line according to invoice_type
        '''
        pool = Pool()
        Uom = pool.get('product.uom')
        Property = pool.get('ir.property')
        InvoiceLine = pool.get('account.invoice.line')

        with Transaction().set_user(0, set_context=True):
            invoice_line = InvoiceLine()
        invoice_line.type = self.type
        invoice_line.description = self.description
        invoice_line.note = self.note
        if self.type != 'line':
            if (self.sale.invoice_method == 'order'
                    and ((all(l.quantity >= 0 for l in self.sale.lines
                                if l.type == 'line')
                            and invoice_type == 'out_invoice')
                        or (all(l.quantity <= 0 for l in self.sale.lines
                                if l.type == 'line')
                            and invoice_type == 'out_credit_note'))):
                return [invoice_line]
            else:
                return []

        if (invoice_type == 'out_invoice') != (self.quantity >= 0):
            return []

        if (self.sale.invoice_method == 'order'
                or not self.product
                or self.product.type == 'service'):
            quantity = abs(self.quantity)
        else:
            quantity = 0.0
            for move in self.moves:
                if move.state == 'done':
                    quantity += Uom.compute_qty(move.uom, move.quantity,
                        self.unit)

        skip_ids = set(l.id for i in self.sale.invoices_recreated
            for l in i.lines)
        for old_invoice_line in self.invoice_lines:
            if old_invoice_line.type != 'line':
                continue
            if old_invoice_line.id not in skip_ids:
                quantity -= Uom.compute_qty(old_invoice_line.unit,
                    old_invoice_line.quantity, self.unit)
        invoice_line.quantity = quantity

        if invoice_line.quantity <= 0.0:
            return []
        invoice_line.unit = self.unit
        invoice_line.product = self.product
        invoice_line.unit_price = self.unit_price
        invoice_line.taxes = self.taxes
        if self.product:
            invoice_line.account = self.product.account_revenue_used
            if not invoice_line.account:
                self.raise_user_error('missing_account_revenue', {
                        'sale': self.sale.rec_name,
                        'product': self.product.rec_name,
                        })
        else:
            for model in ('product.template', 'product.category'):
                invoice_line.account = Property.get('account_revenue', model)
                if invoice_line.account:
                    break
            if not invoice_line.account:
                self.raise_user_error('missing_account_revenue_property',
                    (self.sale.rec_name,))
        invoice_line.origin = self
        return [invoice_line]

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['moves'] = None
        default['moves_ignored'] = None
        default['moves_recreated'] = None
        default['invoice_lines'] = None
        return super(SaleLine, cls).copy(lines, default=default)

    def get_move(self, shipment_type):
        '''
        Return moves for the sale line according ot shipment_type
        '''
        pool = Pool()
        Uom = pool.get('product.uom')
        Move = pool.get('stock.move')

        if self.type != 'line':
            return
        if not self.product:
            return
        if self.product.type == 'service':
            return
        if (shipment_type == 'out') != (self.quantity >= 0):
            return

        if self.sale.shipment_method == 'order':
            quantity = abs(self.quantity)
        else:
            quantity = 0.0
            for invoice_line in self.invoice_lines:
                if invoice_line.invoice.state in ('posted', 'paid'):
                    quantity += Uom.compute_qty(invoice_line.unit,
                        invoice_line.quantity, self.unit)

        skip_ids = set(x.id for x in self.moves_recreated)
        for move in self.moves:
            if move.id not in skip_ids:
                quantity -= Uom.compute_qty(move.uom, move.quantity,
                    self.unit)
        if quantity <= 0.0:
            return
        if not self.sale.party.customer_location:
            self.raise_user_error('customer_location_required', {
                    'sale': self.sale.rec_name,
                    'line': self.rec_name,
                    })
        with Transaction().set_user(0, set_context=True):
            move = Move()
        move.quantity = quantity
        move.uom = self.unit
        move.product = self.product
        move.from_location = self.from_location
        move.to_location = self.to_location
        move.state = 'draft'
        move.company = self.sale.company
        move.unit_price = self.unit_price
        move.currency = self.sale.currency
        move.planned_date = self.delivery_date
        move.origin = self
        return move


class SaleLineTax(ModelSQL):
    'Sale Line - Tax'
    __name__ = 'sale.line-account.tax'
    _table = 'sale_line_account_tax'
    line = fields.Many2One('sale.line', 'Sale Line', ondelete='CASCADE',
            select=True, required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
            select=True, required=True)


class SaleLineIgnoredMove(ModelSQL):
    'Sale Line - Ignored Move'
    __name__ = 'sale.line-ignored-stock.move'
    _table = 'sale_line_moves_ignored_rel'
    sale_line = fields.Many2One('sale.line', 'Sale Line', ondelete='CASCADE',
            select=True, required=True)
    move = fields.Many2One('stock.move', 'Move', ondelete='RESTRICT',
            select=True, required=True)


class SaleLineRecreatedMove(ModelSQL):
    'Sale Line - Recreated Move'
    __name__ = 'sale.line-recreated-stock.move'
    _table = 'sale_line_moves_recreated_rel'
    sale_line = fields.Many2One('sale.line', 'Sale Line', ondelete='CASCADE',
            select=True, required=True)
    move = fields.Many2One('stock.move', 'Move', ondelete='RESTRICT',
            select=True, required=True)


class SaleReport(CompanyReport):
    __name__ = 'sale.sale'


class Template:
    __name__ = 'product.template'
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

    @classmethod
    def __setup__(cls):
        super(Template, cls).__setup__()
        required = ~Eval('account_category', False) & Eval('salable', False)
        if not cls.account_revenue.states.get('required'):
            cls.account_revenue.states['required'] = required
        else:
            cls.account_revenue.states['required'] = (
                    cls.account_revenue.states['required'] | required)
        if 'account_category' not in cls.account_revenue.depends:
            cls.account_revenue.depends.append('account_category')
        if 'salable' not in cls.account_revenue.depends:
            cls.account_revenue.depends.append('salable')

    @staticmethod
    def default_salable():
        return True if Transaction().context.get('salable') else False

    @staticmethod
    def default_delivery_time():
        return 0

    def on_change_with_sale_uom(self):
        if self.default_uom:
            if self.sale_uom:
                if self.default_uom.category == self.sale_uom.category:
                    return self.sale_uom.id
                else:
                    return self.default_uom.id
            else:
                return self.default_uom.id


class Product:
    __name__ = 'product.product'

    @staticmethod
    def get_sale_price(products, quantity=0):
        '''
        Return the sale price for products and quantity.
        It uses if exists from the context:
            uom: the unit of measure
            currency: the currency id for the returned price
        '''
        pool = Pool()
        Uom = pool.get('product.uom')
        User = pool.get('res.user')
        Currency = pool.get('currency.currency')
        Date = pool.get('ir.date')

        today = Date.today()
        prices = {}

        uom = None
        if Transaction().context.get('uom'):
            uom = Uom(Transaction().context.get('uom'))

        currency = None
        if Transaction().context.get('currency'):
            currency = Currency(Transaction().context.get('currency'))

        user = User(Transaction().user)

        for product in products:
            prices[product.id] = product.list_price
            if uom:
                prices[product.id] = Uom.compute_price(
                    product.default_uom, prices[product.id], uom)
            if currency and user.company:
                if user.company.currency != currency:
                    date = Transaction().context.get('sale_date') or today
                    with Transaction().set_context(date=date):
                        prices[product.id] = Currency.compute(
                            user.company.currency, prices[product.id],
                            currency, round=False)
        return prices

    def compute_delivery_date(self, date=None):
        '''
        Compute the delivery date a the given date
        '''
        Date = Pool().get('ir.date')

        if not date:
            date = Date.today()
        return date + datetime.timedelta(self.delivery_time)


class ShipmentOut:
    __name__ = 'stock.shipment.out'

    @classmethod
    def __setup__(cls):
        super(ShipmentOut, cls).__setup__()
        cls._error_messages.update({
                'reset_move': 'You cannot reset to draft a move generated '
                    'by a sale.',
            })

    @classmethod
    def write(cls, shipments, vals):
        pool = Pool()
        Sale = pool.get('sale.sale')
        SaleLine = pool.get('sale.line')

        super(ShipmentOut, cls).write(shipments, vals)

        if 'state' in vals and vals['state'] in ('done', 'cancel'):
            sales = []
            move_ids = []
            for shipment in shipments:
                move_ids.extend([x.id for x in shipment.outgoing_moves])

            with Transaction().set_user(0, set_context=True):
                sale_lines = SaleLine.search([
                        ('moves', 'in', move_ids),
                        ])
                if sale_lines:
                    sales = list(set(l.sale for l in sale_lines))
                    Sale.process(sales)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, shipments):
        SaleLine = Pool().get('sale.line')
        for shipment in shipments:
            for move in shipment.outgoing_moves:
                if (move.state == 'cancel'
                        and isinstance(move.origin, SaleLine)):
                    cls.raise_user_error('reset_move')

        return super(ShipmentOut, cls).draft(shipments)


class ShipmentOutReturn:
    __name__ = 'stock.shipment.out.return'

    @classmethod
    def __setup__(cls):
        super(ShipmentOutReturn, cls).__setup__()
        cls._error_messages.update({
                'reset_move': 'You cannot reset to draft a move generated '
                    'by a sale.',
            })

    @classmethod
    def write(cls, shipments, vals):
        pool = Pool()
        Sale = pool.get('sale.sale')
        SaleLine = pool.get('sale.line')

        super(ShipmentOutReturn, cls).write(shipments, vals)

        if 'state' in vals and vals['state'] == 'received':
            sales = []
            move_ids = []
            for shipment in shipments:
                move_ids.extend([x.id for x in shipment.incoming_moves])

            with Transaction().set_user(0, set_context=True):
                sale_lines = SaleLine.search([
                        ('moves', 'in', move_ids),
                        ])
                if sale_lines:
                    for sale_line in sale_lines:
                        if sale_line.sale not in sales:
                            sales.append(sale_line.sale)

                    sales = Sale.browse([s.id for s in sales])
                    Sale.process(sales)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, shipments):
        SaleLine = Pool().get('sale.line')
        for shipment in shipments:
            for move in shipment.incoming_moves:
                if (move.state == 'cancel'
                        and isinstance(move.origin, SaleLine)):
                    cls.raise_user_error('reset_move')

        return super(ShipmentOutReturn, cls).draft(shipments)


class Move:
    __name__ = 'stock.move'
    sale = fields.Function(fields.Many2One('sale.sale', 'Sale', select=True),
        'get_sale', searcher='search_sale')
    sale_exception_state = fields.Function(fields.Selection([
        ('', ''),
        ('ignored', 'Ignored'),
        ('recreated', 'Recreated'),
        ], 'Exception State'), 'get_sale_exception_state')

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor

        super(Move, cls).__register__(module_name)

        table = TableHandler(cursor, cls, module_name)

        # Migration from 2.6: remove sale_line
        if table.column_exist('sale_line'):
            cursor.execute('UPDATE "' + cls._table + '" '
                'SET origin = \'sale.line,\' || sale_line '
                'WHERE sale_line IS NOT NULL')
            table.drop_column('sale_line')

    @classmethod
    def _get_origin(cls):
        models = super(Move, cls)._get_origin()
        models.append('sale.line')
        return models

    def get_sale(self, name):
        SaleLine = Pool().get('sale.line')
        if isinstance(self.origin, SaleLine):
            return self.origin.sale.id

    @classmethod
    def search_sale(cls, name, clause):
        return [('origin.' + name,) + tuple(clause[1:]) + ('sale.line',)]

    def get_sale_exception_state(self, name):
        SaleLine = Pool().get('sale.line')
        if not isinstance(self.origin, SaleLine):
            return ''
        if self in self.origin.moves_recreated:
            return 'recreated'
        if self in self.origin.moves_ignored:
            return 'ignored'
        return ''

    @classmethod
    def write(cls, moves, vals):
        pool = Pool()
        Sale = pool.get('sale.sale')
        SaleLine = pool.get('sale.line')

        super(Move, cls).write(moves, vals)
        if 'state' in vals and vals['state'] in ('cancel',):
            with Transaction().set_user(0, set_context=True):
                sale_lines = SaleLine.search([
                        ('moves', 'in', [m.id for m in moves]),
                        ])
                if sale_lines:
                    sales = list(set(l.sale for l in sale_lines))
                    Sale.process(sales)

    @classmethod
    def delete(cls, moves):
        pool = Pool()
        Sale = pool.get('sale.sale')
        SaleLine = pool.get('sale.line')

        with Transaction().set_user(0, set_context=True):
            sale_lines = SaleLine.search([
                    ('moves', 'in', [m.id for m in moves]),
                    ])

        super(Move, cls).delete(moves)

        if sale_lines:
            sales = list(set(l.sale for l in sale_lines))
            with Transaction().set_user(0, set_context=True):
                Sale.process(sales)


class OpenCustomer(Wizard):
    'Open Customers'
    __name__ = 'sale.open_customer'
    start_state = 'open_'
    open_ = StateAction('party.act_party_form')

    def do_open_(self, action):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Wizard = pool.get('ir.action.wizard')
        cursor = Transaction().cursor
        cursor.execute("SELECT DISTINCT(party) FROM sale_sale")
        customer_ids = [line[0] for line in Transaction().cursor.fetchall()]
        action['pyson_domain'] = PYSONEncoder().encode(
            [('id', 'in', customer_ids)])

        model_data, = ModelData.search([
                ('fs_id', '=', 'act_open_customer'),
                ('module', '=', 'sale'),
                ], limit=1)
        wizard = Wizard(model_data.db_id)

        action['name'] = wizard.name
        return action, {}

    def transition_open_(self):
        return 'end'


class HandleShipmentExceptionAsk(ModelView):
    'Handle Shipment Exception'
    __name__ = 'sale.handle.shipment.exception.ask'
    recreate_moves = fields.Many2Many(
        'stock.move', None, None, 'Recreate Moves',
        domain=[('id', 'in', Eval('domain_moves'))], depends=['domain_moves'])
    domain_moves = fields.Many2Many(
        'stock.move', None, None, 'Domain Moves')

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        # Migration from 1.2: packing renamed into shipment
        cursor.execute("UPDATE ir_model "
                "SET model = REPLACE(model, 'packing', 'shipment') "
                "WHERE model like '%%packing%%' AND module = %s",
                (module_name,))
        super(HandleShipmentExceptionAsk, cls).__register__(module_name)


class HandleShipmentException(Wizard):
    'Handle Shipment Exception'
    __name__ = 'sale.handle.shipment.exception'
    start_state = 'ask'
    ask = StateView('sale.handle.shipment.exception.ask',
        'sale.handle_shipment_exception_ask_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Ok', 'handle', 'tryton-ok', default=True),
            ])
    handle = StateTransition()

    def default_ask(self, fields):
        Sale = Pool().get('sale.sale')
        sale = Sale(Transaction().context.get('active_id'))

        moves = []
        for line in sale.lines:
            skips = set(line.moves_ignored)
            skips.update(line.moves_recreated)
            for move in line.moves:
                if move.state == 'cancel' and move not in skips:
                    moves.append(move.id)
        return {
            'recreate_moves': moves,
            'domain_moves': moves,
            }

    def transition_handle(self):
        pool = Pool()
        Sale = pool.get('sale.sale')
        SaleLine = pool.get('sale.line')

        sale = Sale(Transaction().context['active_id'])

        for line in sale.lines:
            moves_ignored = []
            moves_recreated = []
            skips = set(line.moves_ignored)
            skips.update(line.moves_recreated)
            for move in line.moves:
                if move not in self.ask.domain_moves or move in skips:
                    continue
                if move in self.ask.recreate_moves:
                    moves_recreated.append(move.id)
                else:
                    moves_ignored.append(move.id)

            SaleLine.write([line], {
                    'moves_ignored': [('add', moves_ignored)],
                    'moves_recreated': [('add', moves_recreated)],
                    })
        Sale.process([sale])
        return 'end'


class HandleInvoiceExceptionAsk(ModelView):
    'Handle Invoice Exception'
    __name__ = 'sale.handle.invoice.exception.ask'
    recreate_invoices = fields.Many2Many(
        'account.invoice', None, None, 'Recreate Invoices',
        domain=[('id', 'in', Eval('domain_invoices'))],
        depends=['domain_invoices'],
        help='The selected invoices will be recreated. '
            'The other ones will be ignored.')
    domain_invoices = fields.Many2Many(
        'account.invoice', None, None, 'Domain Invoices')


class HandleInvoiceException(Wizard):
    'Handle Invoice Exception'
    __name__ = 'sale.handle.invoice.exception'
    start_state = 'ask'
    ask = StateView('sale.handle.invoice.exception.ask',
        'sale.handle_invoice_exception_ask_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Ok', 'handle', 'tryton-ok', default=True),
            ])
    handle = StateTransition()

    def default_ask(self, fields):
        Sale = Pool().get('sale.sale')

        sale = Sale(Transaction().context['active_id'])
        skips = set(sale.invoices_ignored)
        skips.update(sale.invoices_recreated)
        invoices = []
        for invoice in sale.invoices:
            if invoice.state == 'cancel' and invoice not in skips:
                invoices.append(invoice.id)
        return {
            'recreate_invoices': invoices,
            'domain_invoices': invoices,
            }

    def transition_handle(self):
        Sale = Pool().get('sale.sale')

        sale = Sale(Transaction().context['active_id'])

        skips = set(sale.invoices_ignored)
        skips.update(sale.invoices_recreated)
        invoices_ignored = []
        invoices_recreated = []
        for invoice in sale.invoices:
            if invoice not in self.ask.domain_invoices or invoice in skips:
                continue
            if invoice in self.ask.recreate_invoices:
                invoices_recreated.append(invoice.id)
            else:
                invoices_ignored.append(invoice.id)

        Sale.write([sale], {
                'invoices_ignored': [('add', invoices_ignored)],
                'invoices_recreated': [('add', invoices_recreated)],
                })
        Sale.process([sale])
        return 'end'


class ReturnSale(Wizard):
    __name__ = 'sale.return_sale'
    start_state = 'make_return'
    make_return = StateTransition()

    def transition_make_return(self):
        Sale = Pool().get('sale.sale')

        sale = Sale(Transaction().context['active_id'])
        new_sale, = Sale.copy([sale])
        for new_line in new_sale.lines:
            new_line.quantity *= -1
            new_line.save()
        return 'end'
