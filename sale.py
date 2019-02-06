# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal
from itertools import groupby, chain
from functools import partial

from trytond.model import Workflow, Model, ModelView, ModelSQL, fields, \
    sequence_ordered
from trytond.modules.company import CompanyReport
from trytond.wizard import Wizard, StateAction, StateView, StateTransition, \
    Button
from trytond.pyson import If, Eval, Bool, PYSONEncoder
from trytond.transaction import Transaction
from trytond.pool import Pool

from trytond.modules.account.tax import TaxableMixin
from trytond.modules.product import price_digits

__all__ = ['Sale', 'SaleIgnoredInvoice', 'SaleRecreatedInvoice',
    'SaleLine', 'SaleLineTax', 'SaleLineIgnoredMove',
    'SaleLineRecreatedMove', 'SaleReport', 'OpenCustomer',
    'HandleShipmentExceptionAsk', 'HandleShipmentException',
    'HandleInvoiceExceptionAsk', 'HandleInvoiceException',
    'ReturnSaleStart', 'ReturnSale', 'ModifyHeader',
    'get_shipments_returns', 'search_shipments_returns']

_ZERO = Decimal(0)
STATES = [
    ('draft', 'Draft'),
    ('quotation', 'Quotation'),
    ('confirmed', 'Confirmed'),
    ('processing', 'Processing'),
    ('done', 'Done'),
    ('cancel', 'Canceled'),
    ]


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


def search_shipments_returns(model_name):
    "Search on shipments or returns"
    def method(self, name, clause):
        nested = clause[0].lstrip(name)
        if nested:
            return [('lines.moves.shipment' + nested,)
                + tuple(clause[1:3]) + (model_name,) + tuple(clause[3:])]
        else:
            if isinstance(clause[2], str):
                target = 'rec_name'
            else:
                target = 'id'
            return [('lines.moves.shipment.' + target,)
                + tuple(clause[1:3]) + (model_name,)]
    return classmethod(method)


class Sale(Workflow, ModelSQL, ModelView, TaxableMixin):
    'Sale'
    __name__ = 'sale.sale'
    _rec_name = 'number'
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': (Eval('state') != 'draft') | Eval('lines', [0]),
            },
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        depends=['state'], select=True)
    number = fields.Char('Number', readonly=True, select=True)
    reference = fields.Char('Reference', select=True)
    description = fields.Char('Description',
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])
    state = fields.Selection(STATES, 'State', readonly=True, required=True)
    sale_date = fields.Date('Sale Date',
        states={
            'readonly': ~Eval('state').in_(['draft', 'quotation']),
            'required': ~Eval('state').in_(['draft', 'quotation', 'cancel']),
            },
        depends=['state'])
    payment_term = fields.Many2One('account.invoice.payment_term',
        'Payment Term',
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])
    party = fields.Many2One('party.party', 'Party', required=True, select=True,
        states={
            'readonly': ((Eval('state') != 'draft')
                | (Eval('lines', [0]) & Eval('party'))),
            },
        depends=['state'])
    party_lang = fields.Function(fields.Char('Party Language'),
        'on_change_with_party_lang')
    invoice_address = fields.Many2One('party.address', 'Invoice Address',
        domain=[('party', '=', Eval('party'))], states={
            'readonly': Eval('state') != 'draft',
            'required': ~Eval('state').in_(['draft', 'quotation', 'cancel']),
            }, depends=['state', 'party'])
    shipment_party = fields.Many2One('party.party', 'Shipment Party',
        states={
            'readonly': (Eval('state') != 'draft'),
            },
        depends=['state'])
    shipment_address = fields.Many2One('party.address', 'Shipment Address',
        domain=[
            ('party', '=', If(Bool(Eval('shipment_party')),
                    Eval('shipment_party'), Eval('party'))),
            ],
        states={
            'readonly': Eval('state') != 'draft',
            'required': ~Eval('state').in_(['draft', 'quotation', 'cancel']),
            },
        depends=['party', 'shipment_party', 'state'])
    warehouse = fields.Many2One('stock.location', 'Warehouse',
        domain=[('type', '=', 'warehouse')], states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states={
            'readonly': ((Eval('state') != 'draft')
                | (Eval('lines', [0]) & Eval('currency', 0))),
            },
        depends=['state'])
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    lines = fields.One2Many('sale.line', 'sale', 'Lines', states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['party', 'state'])
    comment = fields.Text('Comment')
    untaxed_amount = fields.Function(fields.Numeric('Untaxed',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_amount')
    untaxed_amount_cache = fields.Numeric('Untaxed Cache',
        digits=(16, Eval('currency_digits', 2)),
        readonly=True,
        depends=['currency_digits'])
    tax_amount = fields.Function(fields.Numeric('Tax',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_amount')
    tax_amount_cache = fields.Numeric('Tax Cache',
        digits=(16, Eval('currency_digits', 2)),
        readonly=True,
        depends=['currency_digits'])
    total_amount = fields.Function(fields.Numeric('Total',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_amount')
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
    invoices = fields.Function(fields.One2Many('account.invoice', None,
            'Invoices'), 'get_invoices', searcher='search_invoices')
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
        'Shipments'), 'get_shipments', searcher='search_shipments')
    shipment_returns = fields.Function(
        fields.One2Many('stock.shipment.out.return', None, 'Shipment Returns'),
        'get_shipment_returns', searcher='search_shipment_returns')
    moves = fields.One2Many('stock.move', 'sale', 'Moves', readonly=True)
    origin = fields.Reference('Origin', selection='get_origin', select=True,
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])

    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()
        cls._order = [
            ('sale_date', 'DESC'),
            ('id', 'DESC'),
            ]
        cls._error_messages.update({
                'invalid_method': ('Invalid combination of shipment and '
                    'invoicing methods on sale "%s".'),
                'addresses_required': (
                    'Invoice and Shipment addresses must be '
                    'defined for the quotation of sale "%s".'),
                'warehouse_required': ('Warehouse must be defined for the '
                    'quotation of sale "%s".'),
                'delete_cancel': ('Sale "%s" must be cancelled before '
                    'deletion.'),
                })
        cls._transitions |= set((
                ('draft', 'quotation'),
                ('quotation', 'confirmed'),
                ('confirmed', 'processing'),
                ('confirmed', 'draft'),
                ('processing', 'processing'),
                ('processing', 'done'),
                ('done', 'processing'),
                ('draft', 'cancel'),
                ('quotation', 'cancel'),
                ('quotation', 'draft'),
                ('cancel', 'draft'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': ~Eval('state').in_(['draft', 'quotation']),
                    'depends': ['state'],
                    },
                'draft': {
                    'invisible': ~Eval('state').in_(
                        ['cancel', 'quotation', 'confirmed']),
                    'icon': If(Eval('state') == 'cancel',
                        'tryton-undo',
                        'tryton-back'),
                    'depends': ['state'],
                    },
                'quote': {
                    'invisible': Eval('state') != 'draft',
                    'readonly': ~Eval('lines', []),
                    'depends': ['state'],
                    },
                'confirm': {
                    'invisible': Eval('state') != 'quotation',
                    'depends': ['state'],
                    },
                'process': {
                    'invisible': Eval('state') != 'confirmed',
                    'depends': ['state'],
                    },
                'handle_invoice_exception': {
                    'invisible': ((Eval('invoice_state') != 'exception')
                        | (Eval('state') == 'cancel')),
                    'depends': ['state', 'invoice_state'],
                    },
                'handle_shipment_exception': {
                    'invisible': ((Eval('shipment_state') != 'exception')
                        | (Eval('state') == 'cancel')),
                    'depends': ['state', 'shipment_state'],
                    },
                'modify_header': {
                    'invisible': ((Eval('state') != 'draft')
                        | ~Eval('lines', [-1])),
                    'depends': ['state'],
                    },
                })
        # The states where amounts are cached
        cls._states_cached = ['confirmed', 'processing', 'done', 'cancel']

    @classmethod
    def __register__(cls, module_name):
        table = cls.__table_handler__(module_name)

        # Migration from 3.8: rename reference into number
        if (table.column_exist('reference')
                and not table.column_exist('number')):
            table.column_rename('reference', 'number')

        super(Sale, cls).__register__(module_name)
        table = cls.__table_handler__(module_name)

        # Migration from 4.0: Drop not null on payment_term
        table.not_null_action('payment_term', 'remove')

        # Add index on create_date
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

    @fields.depends('party', 'shipment_party', 'payment_term')
    def on_change_party(self):
        self.invoice_address = None
        if not self.shipment_party:
            self.shipment_address = None
        self.payment_term = self.default_payment_term()
        if self.party:
            self.invoice_address = self.party.address_get(type='invoice')
            if not self.shipment_party:
                self.shipment_address = self.party.address_get(type='delivery')
            if self.party.customer_payment_term:
                self.payment_term = self.party.customer_payment_term

    @fields.depends('party', 'shipment_party')
    def on_change_shipment_party(self):
        if self.shipment_party:
            self.shipment_address = self.shipment_party.address_get(
                type='delivery')
        elif self.party:
            self.shipment_address = self.party.address_get(type='delivery')

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2

    def _get_tax_context(self):
        res = {}
        if self.party and self.party.lang:
            res['language'] = self.party.lang.code
        return res

    @fields.depends('party')
    def on_change_with_party_lang(self, name=None):
        Config = Pool().get('ir.configuration')
        if self.party and self.party.lang:
            return self.party.lang.code
        return Config.get_language()

    @fields.depends('lines', 'currency', 'party')
    def on_change_lines(self):
        self.untaxed_amount = Decimal('0.0')
        self.tax_amount = Decimal('0.0')
        self.total_amount = Decimal('0.0')

        taxes = {}
        if self.lines:
            for line in self.lines:
                self.untaxed_amount += getattr(line, 'amount', None) or 0
            taxes = self._get_taxes()
            self.tax_amount = sum(v['amount'] for v in taxes.values())
        if self.currency:
            self.untaxed_amount = self.currency.round(self.untaxed_amount)
            self.tax_amount = self.currency.round(self.tax_amount)
        self.total_amount = self.untaxed_amount + self.tax_amount
        if self.currency:
            self.total_amount = self.currency.round(self.total_amount)

    @property
    def taxable_lines(self):
        taxable_lines = []
        # In case we're called from an on_change we have to use some sensible
        # defaults
        for line in self.lines:
            if getattr(line, 'type', None) != 'line':
                continue
            taxable_lines.append(tuple())
            for attribute, default_value in (
                    ('taxes', []),
                    ('unit_price', Decimal(0)),
                    ('quantity', 0.0)):
                value = getattr(line, attribute, None)
                taxable_lines[-1] += (value
                    if value is not None else default_value,)
        return taxable_lines

    def get_tax_amount(self):
        return sum(
            (v['amount'] for v in self._get_taxes().values()), Decimal(0))

    @classmethod
    def get_amount(cls, sales, names):
        untaxed_amount = {}
        tax_amount = {}
        total_amount = {}

        if {'tax_amount', 'total_amount'} & set(names):
            compute_taxes = True
        else:
            compute_taxes = False
        # Sort cached first and re-instanciate to optimize cache management
        sales = sorted(sales, key=lambda s: s.state in cls._states_cached,
            reverse=True)
        sales = cls.browse(sales)
        for sale in sales:
            if (sale.state in cls._states_cached
                    and sale.untaxed_amount_cache is not None
                    and sale.tax_amount_cache is not None
                    and sale.total_amount_cache is not None):
                untaxed_amount[sale.id] = sale.untaxed_amount_cache
                if compute_taxes:
                    tax_amount[sale.id] = sale.tax_amount_cache
                    total_amount[sale.id] = sale.total_amount_cache
            else:
                untaxed_amount[sale.id] = sum(
                    (line.amount for line in sale.lines
                        if line.type == 'line'), _ZERO)
                if compute_taxes:
                    tax_amount[sale.id] = sale.get_tax_amount()
                    total_amount[sale.id] = (
                        untaxed_amount[sale.id] + tax_amount[sale.id])

        result = {
            'untaxed_amount': untaxed_amount,
            'tax_amount': tax_amount,
            'total_amount': total_amount,
            }
        for key in list(result.keys()):
            if key not in names:
                del result[key]
        return result

    def get_invoices(self, name):
        invoices = set()
        for line in self.lines:
            for invoice_line in line.invoice_lines:
                if invoice_line.invoice:
                    invoices.add(invoice_line.invoice.id)
        return list(invoices)

    @classmethod
    def search_invoices(cls, name, clause):
        return [('lines.invoice_lines.invoice' + clause[0].lstrip(name),)
            + tuple(clause[1:])]

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

    get_shipments = get_shipments_returns('stock.shipment.out')
    get_shipment_returns = get_shipments_returns('stock.shipment.out.return')

    search_shipments = search_shipments_returns('stock.shipment.out')
    search_shipment_returns = search_shipments_returns(
        'stock.shipment.out.return')

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
    def _get_origin(cls):
        'Return list of Model names for origin Reference'
        return ['sale.sale']

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        models = cls._get_origin()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [(None, '')] + [(m.model, m.name) for m in models]

    @property
    def report_address(self):
        if self.invoice_address:
            return self.invoice_address.full_address
        else:
            return ''

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
        items = []
        if self.number:
            items.append(self.number)
        if self.reference:
            items.append('[%s]' % self.reference)
        if not items:
            items.append('(%s)' % self.id)
        return ' '.join(items)

    @classmethod
    def search_rec_name(cls, name, clause):
        _, operator, value = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        domain = [bool_op,
            ('number', operator, value),
            ('reference', operator, value),
            ]
        return domain

    @classmethod
    def view_attributes(cls):
        attributes = [
            ('/form//field[@name="comment"]', 'spell', Eval('party_lang'))]
        if Transaction().context.get('modify_header'):
            attributes.extend([
                    ('//group[@id="states"]', 'states', {'invisible': True}),
                    ('//group[@id="amount_buttons"]',
                        'states', {'invisible': True}),
                    ('//page[@name="invoices"]',
                        'states', {'invisible': True}),
                    ('//page[@name="shipments"]',
                        'states', {'invisible': True}),
                    ])
        return attributes

    @classmethod
    def copy(cls, sales, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('number', None)
        default.setdefault('invoice_state', 'none')
        default.setdefault('invoices_ignored', None)
        default.setdefault('moves', None)
        default.setdefault('shipment_state', 'none')
        default.setdefault('sale_date', None)
        return super(Sale, cls).copy(sales, default=default)

    def check_for_quotation(self):
        if not self.invoice_address or not self.shipment_address:
            self.raise_user_error('addresses_required', (self.rec_name,))
        for line in self.lines:
            if (line.quantity or 0) >= 0:
                location = line.from_location
            else:
                location = line.to_location
            if ((not location or not line.warehouse)
                    and line.product
                    and line.product.type in ('goods', 'assets')):
                self.raise_user_error('warehouse_required',
                    (self.rec_name,))

    @classmethod
    def set_number(cls, sales):
        '''
        Fill the number field with the sale sequence
        '''
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Config = pool.get('sale.configuration')

        config = Config(1)
        for sale in sales:
            if sale.number:
                continue
            sale.number = Sequence.get_id(config.sale_sequence.id)
        cls.save(sales)

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
            sale.untaxed_amount_cache = sale.untaxed_amount
            sale.tax_amount_cache = sale.tax_amount
            sale.total_amount_cache = sale.total_amount
        cls.save(sales)

    def _get_invoice_sale(self):
        'Return invoice'
        pool = Pool()
        Invoice = pool.get('account.invoice')
        invoice = Invoice(
            company=self.company,
            type='out',
            party=self.party,
            invoice_address=self.invoice_address,
            currency=self.currency,
            account=self.party.account_receivable_used,
            )
        invoice.on_change_type()
        invoice.payment_term = self.payment_term
        return invoice

    def create_invoice(self):
        'Create and return an invoice'
        pool = Pool()
        Invoice = pool.get('account.invoice')
        if self.invoice_method == 'manual':
            return

        invoice_lines = []
        for line in self.lines:
            invoice_lines.append(line.get_invoice_line())
        invoice_lines = list(chain(*invoice_lines))
        if not invoice_lines:
            return

        invoice = self._get_invoice_sale()
        if getattr(invoice, 'lines', None):
            invoice_lines = list(invoice.lines) + invoice_lines
        invoice.lines = invoice_lines
        invoice.save()

        Invoice.update_taxes([invoice])
        return invoice

    def _group_shipment_key(self, moves, move):
        '''
        The key to group moves by shipments

        move is a tuple of line id and a move
        '''
        SaleLine = Pool().get('sale.line')
        line_id, move = move
        line = SaleLine(line_id)

        if any(m.planned_date is None for m in moves):
            planned_date = None
        else:
            planned_date = max(m.planned_date for m in moves)
        return (
            ('planned_date', planned_date),
            ('warehouse', line.warehouse.id),
            )

    _group_return_key = _group_shipment_key

    def _get_shipment_sale(self, Shipment, key):
        values = {
            'customer': (self.shipment_party.id if self.shipment_party
                else self.party.id),
            'delivery_address': self.shipment_address.id,
            'company': self.company.id,
            }
        values.update(dict(key))
        return Shipment(**values)

    def create_shipment(self, shipment_type):
        '''
        Create and return shipments of type shipment_type
        '''
        pool = Pool()

        if self.shipment_method == 'manual':
            return

        moves = {}
        for line in self.lines:
            move = line.get_move(shipment_type)
            if move:
                moves[line.id] = move
        if not moves:
            return
        if shipment_type == 'out':
            keyfunc = partial(self._group_shipment_key, list(moves.values()))
            Shipment = pool.get('stock.shipment.out')
        elif shipment_type == 'return':
            keyfunc = partial(self._group_return_key, list(moves.values()))
            Shipment = pool.get('stock.shipment.out.return')
        moves = moves.items()
        moves = sorted(moves, key=keyfunc)

        shipments = []
        for key, grouped_moves in groupby(moves, key=keyfunc):
            shipment = self._get_shipment_sale(Shipment, key)
            shipment.moves = (list(getattr(shipment, 'moves', []))
                + [x[1] for x in grouped_moves])
            shipment.save()
            shipments.append(shipment)
        if shipment_type == 'out':
            Shipment.wait(shipments)
        return shipments

    def is_done(self):
        return ((self.invoice_state == 'paid'
                or self.invoice_state == 'none')
            and (self.shipment_state == 'sent'
                or self.shipment_state == 'none'
                or all(l.product.type == 'service'
                    for l in self.lines if l.product)))

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
        cls.set_number(sales)

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(cls, sales):
        pool = Pool()
        Configuration = pool.get('sale.configuration')
        cls.set_sale_date(sales)
        cls.store_cache(sales)
        config = Configuration(1)
        with Transaction().set_context(
                queue_name='sale',
                queue_scheduled_at=config.sale_process_after):
            cls.__queue__.process(sales)

    @classmethod
    @ModelView.button_action('sale.wizard_invoice_handle_exception')
    def handle_invoice_exception(cls, sales):
        pass

    @classmethod
    @ModelView.button_action('sale.wizard_shipment_handle_exception')
    def handle_shipment_exception(cls, sales):
        pass

    @classmethod
    @Workflow.transition('processing')
    def proceed(cls, sales):
        pass

    @classmethod
    @Workflow.transition('done')
    def do(cls, sales):
        pass

    @classmethod
    @ModelView.button
    def process(cls, sales):
        done = []
        process = []
        cls.__lock(sales)
        for sale in sales:
            if sale.state not in ('confirmed', 'processing', 'done'):
                continue
            sale.create_invoice()
            sale.set_invoice_state()
            sale.create_shipment('out')
            sale.create_shipment('return')
            sale.set_shipment_state()
            if sale.is_done():
                if sale.state != 'done':
                    if sale.state == 'confirmed':
                        process.append(sale)
                    done.append(sale)
            elif sale.state != 'processing':
                process.append(sale)
        if process:
            cls.proceed(process)
        if done:
            cls.do(done)

    @classmethod
    def __lock(cls, records):
        from trytond.tools import grouped_slice, reduce_ids
        from sql import Literal, For
        transaction = Transaction()
        database = transaction.database
        connection = transaction.connection
        table = cls.__table__()

        if database.has_select_for():
            for sub_records in grouped_slice(records):
                where = reduce_ids(table.id, sub_records)
                query = table.select(
                    Literal(1), where=where, for_=For('UPDATE', nowait=True))
                with connection.cursor() as cursor:
                    cursor.execute(*query)
        else:
            database.lock(connection, cls._table)

    @classmethod
    @ModelView.button_action('sale.wizard_modify_header')
    def modify_header(cls, sales):
        pass


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


class SaleLine(sequence_ordered(), ModelSQL, ModelView):
    'Sale Line'
    __name__ = 'sale.line'
    sale = fields.Many2One('sale.sale', 'Sale', ondelete='CASCADE',
        select=True,
        states={
            'readonly': ((Eval('sale_state') != 'draft')
                & Bool(Eval('sale'))),
            },
        depends=['sale_state'])
    type = fields.Selection([
        ('line', 'Line'),
        ('subtotal', 'Subtotal'),
        ('title', 'Title'),
        ('comment', 'Comment'),
        ], 'Type', select=True, required=True,
        states={
            'readonly': Eval('sale_state') != 'draft',
            },
        depends=['sale_state'])
    quantity = fields.Float('Quantity',
        digits=(16, Eval('unit_digits', 2)),
        states={
            'invisible': Eval('type') != 'line',
            'required': Eval('type') == 'line',
            'readonly': Eval('sale_state') != 'draft',
            },
        depends=['type', 'unit_digits', 'sale_state'])
    unit = fields.Many2One('product.uom', 'Unit', ondelete='RESTRICT',
            states={
                'required': Bool(Eval('product')),
                'invisible': Eval('type') != 'line',
                'readonly': Eval('sale_state') != 'draft',
            },
        domain=[
            If(Bool(Eval('product_uom_category')),
                ('category', '=', Eval('product_uom_category')),
                ('category', '!=', -1)),
            ],
        depends=['product', 'type', 'product_uom_category', 'sale_state'])
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
        'on_change_with_unit_digits')
    product = fields.Many2One('product.product', 'Product',
        ondelete='RESTRICT', domain=[('salable', '=', True)],
        states={
            'invisible': Eval('type') != 'line',
            'readonly': Eval('sale_state') != 'draft',
            },
        context={
            'locations': If(Bool(Eval('_parent_sale', {}).get('warehouse')),
                [Eval('_parent_sale', {}).get('warehouse', 0)], []),
            'stock_date_end': Eval('_parent_sale', {}).get('sale_date'),
            'stock_skip_warehouse': True,
            # From _get_context_sale_price
            'currency': Eval('_parent_sale', {}).get('currency'),
            'customer': Eval('_parent_sale', {}).get('party'),
            'sale_date': Eval('_parent_sale', {}).get('sale_date'),
            'uom': Eval('unit'),
            'taxes': Eval('taxes', []),
            'quantity': Eval('quantity'),
            }, depends=['type', 'sale_state'])
    product_uom_category = fields.Function(
        fields.Many2One('product.uom.category', 'Product Uom Category'),
        'on_change_with_product_uom_category')
    unit_price = fields.Numeric('Unit Price', digits=price_digits,
        states={
            'invisible': Eval('type') != 'line',
            'required': Eval('type') == 'line',
            'readonly': Eval('sale_state') != 'draft'
            }, depends=['type', 'sale_state'])
    amount = fields.Function(fields.Numeric('Amount',
            digits=(16, Eval('_parent_sale', {}).get('currency_digits', 2)),
            states={
                'invisible': ~Eval('type').in_(['line', 'subtotal']),
                },
            depends=['type', 'sale_state']), 'get_amount')
    description = fields.Text('Description', size=None,
        states={
            'readonly': Eval('sale_state') != 'draft',
            },
        depends=['sale_state'])
    note = fields.Text('Note')
    taxes = fields.Many2Many('sale.line-account.tax', 'line', 'tax', 'Taxes',
        order=[('tax.sequence', 'ASC'), ('tax.id', 'ASC')],
        domain=[('parent', '=', None), ['OR',
                ('group', '=', None),
                ('group.kind', 'in', ['sale', 'both'])],
                ('company', '=',
                    Eval('_parent_sale', {}).get('company', -1)),
            ],
        states={
            'invisible': Eval('type') != 'line',
            'readonly': Eval('sale_state') != 'draft',
            }, depends=['type', 'sale_state'])
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
    shipping_date = fields.Function(fields.Date('Shipping Date',
            states={
                'invisible': Eval('type') != 'line',
                },
            depends=['type']),
        'on_change_with_shipping_date')
    sale_state = fields.Function(fields.Selection(STATES, 'Sale State'),
        'on_change_with_sale_state')

    @classmethod
    def __setup__(cls):
        super(SaleLine, cls).__setup__()
        cls._error_messages.update({
                'customer_location_required': (
                    'Sale "%(sale)s" is missing the '
                    'customer location in line "%(line)s".'),
                'missing_account_revenue': ('Product "%(product)s" of sale '
                    '%(sale)s misses a revenue account.'),
                'missing_default_account_revenue': ('Sale "%(sale)s" '
                    'misses a default "account revenue".'),
                'delete_cancel_draft': ('The line "%(line)s" must be on '
                    'canceled or draft sale to be deleted.'),
                })

    @classmethod
    def __register__(cls, module_name):
        super(SaleLine, cls).__register__(module_name)
        table = cls.__table_handler__(module_name)

        # Migration from 4.6: drop required on description
        table.not_null_action('description', action='remove')

    @staticmethod
    def default_type():
        return 'line'

    @staticmethod
    def default_unit_digits():
        return 2

    @fields.depends('unit')
    def on_change_with_unit_digits(self, name=None):
        if self.unit:
            return self.unit.digits
        return 2

    @property
    def _move_remaining_quantity(self):
        "Compute the remaining quantity to ship"
        pool = Pool()
        Uom = pool.get('product.uom')
        if self.type != 'line' or not self.product:
            return
        if self.product.type == 'service':
            return
        skip_ids = set(x.id for x in self.moves_ignored)
        quantity = abs(self.quantity)
        for move in self.moves:
            if move.state == 'done' or move.id in skip_ids:
                quantity -= Uom.compute_qty(move.uom, move.quantity, self.unit)
        return quantity

    def get_move_done(self, name):
        quantity = self._move_remaining_quantity
        if quantity is None:
            return True
        else:
            return self.unit.round(quantity) <= 0

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

    @fields.depends('sale', '_parent_sale.currency', '_parent_sale.party',
        '_parent_sale.sale_date', 'unit', 'product', 'taxes')
    def _get_context_sale_price(self):
        context = {}
        if self.sale:
            if self.sale.currency:
                context['currency'] = self.sale.currency.id
            if self.sale.party:
                context['customer'] = self.sale.party.id
            context['sale_date'] = self.sale.sale_date
        if self.unit:
            context['uom'] = self.unit.id
        elif self.product:
            context['uom'] = self.product.sale_uom.id
        context['taxes'] = [t.id for t in self.taxes or []]
        return context

    @fields.depends('product', 'unit', 'quantity', 'sale',
        '_parent_sale.party',
        methods=['_get_tax_rule_pattern', '_get_context_sale_price',
        'on_change_with_amount'])
    def on_change_product(self):
        Product = Pool().get('product.product')

        if not self.product:
            return

        party = None
        if self.sale and self.sale.party:
            party = self.sale.party

        # Set taxes before unit_price to have taxes in context of sale price
        taxes = []
        pattern = self._get_tax_rule_pattern()
        for tax in self.product.customer_taxes_used:
            if party and party.customer_tax_rule:
                tax_ids = party.customer_tax_rule.apply(tax, pattern)
                if tax_ids:
                    taxes.extend(tax_ids)
                continue
            taxes.append(tax.id)
        if party and party.customer_tax_rule:
            tax_ids = party.customer_tax_rule.apply(None, pattern)
            if tax_ids:
                taxes.extend(tax_ids)
        self.taxes = taxes

        category = self.product.sale_uom.category
        if not self.unit or self.unit.category != category:
            self.unit = self.product.sale_uom
            self.unit_digits = self.product.sale_uom.digits

        with Transaction().set_context(self._get_context_sale_price()):
            self.unit_price = Product.get_sale_price([self.product],
                    self.quantity or 0)[self.product.id]
            if self.unit_price:
                self.unit_price = self.unit_price.quantize(
                    Decimal(1) / 10 ** self.__class__.unit_price.digits[1])

        self.type = 'line'
        self.amount = self.on_change_with_amount()

    @fields.depends('product')
    def on_change_with_product_uom_category(self, name=None):
        if self.product:
            return self.product.default_uom_category.id

    @fields.depends('product', 'quantity',
        methods=['_get_context_sale_price'])
    def on_change_quantity(self):
        Product = Pool().get('product.product')

        if not self.product:
            return

        with Transaction().set_context(
                self._get_context_sale_price()):
            self.unit_price = Product.get_sale_price([self.product],
                self.quantity or 0)[self.product.id]
            if self.unit_price:
                self.unit_price = self.unit_price.quantize(
                    Decimal(1) / 10 ** self.__class__.unit_price.digits[1])

    @fields.depends(methods=['on_change_quantity'])
    def on_change_unit(self):
        self.on_change_quantity()

    @fields.depends(methods=['on_change_quantity'])
    def on_change_taxes(self):
        self.on_change_quantity()

    @fields.depends('type', 'quantity', 'unit_price', 'unit', 'sale',
        '_parent_sale.currency')
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
            return self.on_change_with_amount()
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
        if (self.quantity or 0) >= 0:
            if self.warehouse:
                return self.warehouse.output_location.id
        else:
            party = self.sale.shipment_party or self.sale.party
            return party.customer_location.id

    def get_to_location(self, name):
        if (self.quantity or 0) >= 0:
            party = self.sale.shipment_party or self.sale.party
            return party.customer_location.id
        else:
            if self.warehouse:
                return self.warehouse.input_location.id

    @fields.depends('product', 'quantity', 'moves', 'sale',
        '_parent_sale.sale_date')
    def on_change_with_shipping_date(self, name=None):
        pool = Pool()
        Date = pool.get('ir.date')
        if self.moves:
            dates = filter(
                None, (m.effective_date or m.planned_date for m in self.moves
                    if m.state != 'cancel'))
            return min(dates, default=None)
        if self.product and self.quantity is not None and self.quantity > 0:
            date = self.sale.sale_date if self.sale else None
            shipping_date = self.product.compute_shipping_date(date=date)
            if shipping_date == datetime.date.max:
                shipping_date = None
            if shipping_date:
                shipping_date = max(shipping_date, Date.today())
            return shipping_date

    @fields.depends('sale', '_parent_sale.state')
    def on_change_with_sale_state(self, name=None):
        if self.sale:
            return self.sale.state

    def get_invoice_line(self):
        'Return a list of invoice lines for sale line'
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        AccountConfiguration = pool.get('account.configuration')
        account_config = AccountConfiguration(1)

        invoice_line = InvoiceLine()
        invoice_line.type = self.type
        invoice_line.description = self.description
        invoice_line.note = self.note
        invoice_line.origin = self
        if self.type != 'line':
            if self._get_invoice_not_line():
                return [invoice_line]
            else:
                return []

        quantity = (self._get_invoice_line_quantity()
            - self._get_invoiced_quantity())

        if self.unit:
            quantity = self.unit.round(quantity)
        invoice_line.quantity = quantity

        if not invoice_line.quantity:
            return []

        invoice_line.unit = self.unit
        invoice_line.product = self.product
        invoice_line.unit_price = self.unit_price
        invoice_line.taxes = self.taxes
        invoice_line.invoice_type = 'out'
        if self.product:
            invoice_line.account = self.product.account_revenue_used
            if not invoice_line.account:
                self.raise_user_error('missing_account_revenue', {
                        'sale': self.sale.rec_name,
                        'product': self.product.rec_name,
                        })
        else:
            invoice_line.account = account_config.get_multivalue(
                'default_category_account_revenue')
            if not invoice_line.account:
                self.raise_user_error('missing_default_account_revenue', {
                        'sale': self.sale.rec_name,
                        })
        invoice_line.stock_moves = self._get_invoice_line_moves()
        return [invoice_line]

    def _get_invoice_not_line(self):
        'Return if the not line should be invoiced'
        return self.sale.invoice_method == 'order' and not self.invoice_lines

    def _get_invoice_line_quantity(self):
        'Return the quantity that should be invoiced'
        pool = Pool()
        Uom = pool.get('product.uom')

        if (self.sale.invoice_method == 'order'
                or not self.product
                or self.product.type == 'service'):
            return self.quantity
        elif self.sale.invoice_method == 'shipment':
            quantity = 0.0
            for move in self.moves:
                if move.state == 'done':
                    quantity += Uom.compute_qty(move.uom, move.quantity,
                        self.unit)
            if self.quantity < 0:
                quantity *= -1
            return quantity

    def _get_invoiced_quantity(self):
        'Return the quantity already invoiced'
        pool = Pool()
        Uom = pool.get('product.uom')

        quantity = 0
        skips = {l for i in self.sale.invoices_recreated for l in i.lines}
        for invoice_line in self.invoice_lines:
            if invoice_line.type != 'line':
                continue
            if invoice_line not in skips:
                quantity += Uom.compute_qty(invoice_line.unit,
                    invoice_line.quantity, self.unit)
        return quantity

    def _get_invoice_line_moves(self):
        'Return the stock moves that should be invoiced'
        moves = []
        if self.sale.invoice_method == 'order':
            if self.sale.shipment_method != 'order':
                moves.extend(self.moves)
        elif self.sale.invoice_method == 'shipment':
            for move in self.moves:
                if move.state == 'done':
                    if move.invoiced_quantity < move.quantity:
                        moves.append(move)
        return moves

    def get_move(self, shipment_type):
        '''
        Return moves for the sale line according to shipment_type
        '''
        pool = Pool()
        Move = pool.get('stock.move')
        Date = pool.get('ir.date')

        if self.type != 'line':
            return
        if not self.product:
            return
        if self.product.type == 'service':
            return

        if (shipment_type == 'out') != (self.quantity >= 0):
            return

        quantity = (self._get_move_quantity(shipment_type)
            - self._get_shipped_quantity(shipment_type))

        quantity = self.unit.round(quantity)
        if quantity <= 0:
            return

        if not self.sale.party.customer_location:
            self.raise_user_error('customer_location_required', {
                    'sale': self.sale.rec_name,
                    'line': self.rec_name,
                    })
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
        if self.moves:
            # backorder can not be planned
            move.planned_date = Date.today()
        else:
            move.planned_date = self.shipping_date
        move.invoice_lines = self._get_move_invoice_lines(shipment_type)
        move.origin = self
        return move

    def _get_move_quantity(self, shipment_type):
        'Return the quantity that should be shipped'
        pool = Pool()
        Uom = pool.get('product.uom')

        if self.sale.shipment_method == 'order':
            return abs(self.quantity)
        elif self.sale.shipment_method == 'invoice':
            quantity = 0.0
            for invoice_line in self.invoice_lines:
                if (invoice_line.invoice
                        and invoice_line.invoice.state == 'paid'):
                    quantity += Uom.compute_qty(invoice_line.unit,
                        invoice_line.quantity, self.unit)
            return quantity

    def _get_shipped_quantity(self, shipment_type):
        'Return the quantity already shipped'
        pool = Pool()
        Uom = pool.get('product.uom')

        quantity = 0
        skips = set(m for m in self.moves_recreated)
        for move in self.moves:
            if move not in skips:
                quantity += Uom.compute_qty(move.uom, move.quantity,
                    self.unit)
        return quantity

    def _get_move_invoice_lines(self, shipment_type):
        'Return the invoice lines that should be shipped'
        invoice_lines = []
        if self.sale.shipment_method == 'order':
            if self.sale.invoice_method == 'order':
                invoice_lines.extend(self.invoice_lines)
        elif self.sale.shipment_method == 'invoice':
            for invoice_line in self.invoice_lines:
                if (invoice_line.invoice
                        and invoice_line.invoice.state == 'paid'):
                    if invoice_line.moved_quantity < invoice_line.quantity:
                        invoice_lines.append(invoice_line)
        return invoice_lines

    def get_rec_name(self, name):
        if self.product:
            return '%s @ %s' % (self.product.rec_name, self.sale.rec_name)
        else:
            return self.sale.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            ('sale.rec_name',) + tuple(clause[1:]),
            ('product.rec_name',) + tuple(clause[1:]),
            ]

    @classmethod
    def view_attributes(cls):
        return [
            ('/form//field[@name="note"]|/form//field[@name="description"]',
                'spell', Eval('_parent_sale', {}).get('party_lang'))]

    @classmethod
    def delete(cls, lines):
        for line in lines:
            if line.sale_state not in {'cancel', 'draft'}:
                cls.raise_user_error('delete_cancel_draft', {
                        'line': line.rec_name,
                        })
        super(SaleLine, cls).delete(lines)

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('moves', None)
        default.setdefault('moves_ignored', None)
        default.setdefault('moves_recreated', None)
        default.setdefault('invoice_lines', None)
        return super(SaleLine, cls).copy(lines, default=default)


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

    @classmethod
    def execute(cls, ids, data):
        with Transaction().set_context(address_with_party=True):
            return super(SaleReport, cls).execute(ids, data)

    @classmethod
    def get_context(cls, records, data):
        pool = Pool()
        Date = pool.get('ir.date')
        context = super(SaleReport, cls).get_context(records, data)
        context['today'] = Date.today()
        return context


class OpenCustomer(Wizard):
    'Open Customers'
    __name__ = 'sale.open_customer'
    start_state = 'open_'
    open_ = StateAction('party.act_party_form')

    def do_open_(self, action):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Wizard = pool.get('ir.action.wizard')
        Sale = pool.get('sale.sale')
        cursor = Transaction().connection.cursor()
        sale = Sale.__table__()

        cursor.execute(*sale.select(sale.party, group_by=sale.party))
        customer_ids = [line[0] for line in cursor.fetchall()]
        action['pyson_domain'] = PYSONEncoder().encode(
            [('id', 'in', customer_ids)])
        wizard = Wizard(ModelData.get_id('sale', 'act_open_customer'))
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


class HandleShipmentException(Wizard):
    'Handle Shipment Exception'
    __name__ = 'sale.handle.shipment.exception'
    start_state = 'ask'
    ask = StateView('sale.handle.shipment.exception.ask',
        'sale.handle_shipment_exception_ask_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'handle', 'tryton-ok', default=True),
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
        Sale.__queue__.process([sale])
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
            Button('OK', 'handle', 'tryton-ok', default=True),
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

        invoices_ignored = []
        invoices_recreated = []
        for invoice in self.ask.domain_invoices:
            if invoice in self.ask.recreate_invoices:
                invoices_recreated.append(invoice.id)
            else:
                invoices_ignored.append(invoice.id)

        Sale.write([sale], {
                'invoices_ignored': [('add', invoices_ignored)],
                'invoices_recreated': [('add', invoices_recreated)],
                })
        Sale.__queue__.process([sale])
        return 'end'


class ReturnSaleStart(ModelView):
    'Return Sale'
    __name__ = 'sale.return_sale.start'


class ReturnSale(Wizard):
    'Return Sale'
    __name__ = 'sale.return_sale'
    start = StateView('sale.return_sale.start',
        'sale.return_sale_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Return', 'return_', 'tryton-ok', default=True),
            ])
    return_ = StateAction('sale.act_sale_form')

    def do_return_(self, action):
        Sale = Pool().get('sale.sale')

        sales = Sale.browse(Transaction().context['active_ids'])
        return_sales = Sale.copy(sales)
        for return_sale, sale in zip(return_sales, sales):
            return_sale.origin = sale
            for line in return_sale.lines:
                if line.type == 'line':
                    line.quantity *= -1
            return_sale.lines = return_sale.lines  # Force saving
        Sale.save(return_sales)

        data = {'res_id': [s.id for s in return_sales]}
        if len(return_sales) == 1:
            action['views'].reverse()
        return action, data


class ModifyHeaderStateView(StateView):
    def get_view(self, wizard, state_name):
        with Transaction().set_context(modify_header=True):
            return super(ModifyHeaderStateView, self).get_view(
                wizard, state_name)


class ModifyHeader(Wizard):
    "Modify Header"
    __name__ = 'sale.modify_header'
    start = ModifyHeaderStateView('sale.sale',
        'sale.modify_header_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Modify", 'modify', 'tryton-ok', default=True),
            ])
    modify = StateTransition()

    @classmethod
    def __setup__(cls):
        super(ModifyHeader, cls).__setup__()
        cls._error_messages.update({
                'not_in_draft': (
                    'The sale "%(sale)s" must be in draft to modify header.'),
                })

    def get_sale(self):
        pool = Pool()
        Sale = pool.get('sale.sale')

        sale = Sale(Transaction().context['active_id'])
        if sale.state != 'draft':
            self.raise_user_error('not_in_draft', {
                    'sale': sale.rec_name,
                    })
        return sale

    def default_start(self, fields):
        sale = self.get_sale()
        defaults = {}
        for fieldname in fields:
            value = getattr(sale, fieldname)
            if isinstance(value, Model):
                if getattr(sale.__class__, fieldname)._type == 'reference':
                    value = str(value)
                else:
                    value = value.id
            elif isinstance(value, (list, tuple)):
                value = [r.id for r in value]
            defaults[fieldname] = value

        # Mimic an empty sale in draft state to get the fields' states right
        defaults['lines'] = []
        return defaults

    def transition_modify(self):
        pool = Pool()
        Line = pool.get('sale.line')

        sale = self.get_sale()
        sale.__class__.write([sale], self.start._save_values)

        # Call on_change after the save to ensure parent sale
        # has the modified values
        for line in sale.lines:
            line.on_change_product()
        Line.save(sale.lines)

        return 'end'
