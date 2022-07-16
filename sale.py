# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from collections import defaultdict
from decimal import Decimal
from functools import partial
from itertools import chain, groupby

from trytond.i18n import gettext
from trytond.ir.attachment import AttachmentCopyMixin
from trytond.ir.note import NoteCopyMixin
from trytond.model import (
    Model, ModelSQL, ModelView, Unique, Workflow, fields, sequence_ordered)
from trytond.model.exceptions import AccessError
from trytond.modules.account.tax import TaxableMixin
from trytond.modules.account_product.exceptions import AccountError
from trytond.modules.company import CompanyReport
from trytond.modules.company.model import (
    employee_field, reset_employee, set_employee)
from trytond.modules.currency.fields import Monetary
from trytond.modules.product import price_digits, round_price
from trytond.pool import Pool
from trytond.pyson import Bool, Eval, If, PYSONEncoder
from trytond.tools import firstline, sortable_values
from trytond.transaction import Transaction
from trytond.wizard import (
    Button, StateAction, StateTransition, StateView, Wizard)

from .exceptions import (
    PartyLocationError, SaleQuotationError, SaleValidationError)


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


class Sale(
        Workflow, ModelSQL, ModelView, TaxableMixin,
        AttachmentCopyMixin, NoteCopyMixin):
    'Sale'
    __name__ = 'sale.sale'
    _rec_name = 'number'
    company = fields.Many2One(
        'company.company', 'Company', required=True, select=True,
        states={
            'readonly': (
                (Eval('state') != 'draft')
                | Eval('lines', [0])
                | Eval('party', True)
                | Eval('invoice_party', True)
                | Eval('shipment_party', True)),
            })
    number = fields.Char('Number', readonly=True, select=True)
    reference = fields.Char('Reference', select=True)
    description = fields.Char('Description',
        states={
            'readonly': Eval('state') != 'draft',
            })
    sale_date = fields.Date('Sale Date',
        states={
            'readonly': ~Eval('state').in_(['draft', 'quotation']),
            'required': ~Eval('state').in_(
                ['draft', 'quotation', 'cancelled']),
            })
    payment_term = fields.Many2One('account.invoice.payment_term',
        'Payment Term',
        states={
            'readonly': Eval('state') != 'draft',
            })
    party = fields.Many2One('party.party', 'Party', required=True, select=True,
        states={
            'readonly': ((Eval('state') != 'draft')
                | (Eval('lines', [0]) & Eval('party'))),
            },
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    party_lang = fields.Function(fields.Char('Party Language'),
        'on_change_with_party_lang')
    contact = fields.Many2One(
        'party.contact_mechanism', "Contact",
        context={
            'company': Eval('company', -1),
            },
        search_context={
            'related_party': Eval('party'),
            },
        depends={'company'})
    invoice_party = fields.Many2One('party.party', "Invoice Party",
        states={
            'readonly': ((Eval('state') != 'draft')
                | Eval('lines', [0])),
            },
        context={
            'company': Eval('company', -1),
            },
        search_context={
            'related_party': Eval('party'),
            },
        depends={'company'})
    invoice_address = fields.Many2One('party.address', 'Invoice Address',
        domain=[
            ('party', '=', If(Bool(Eval('invoice_party')),
                    Eval('invoice_party'), Eval('party'))),
            ],
        states={
            'readonly': Eval('state') != 'draft',
            'required': ~Eval('state').in_(
                ['draft', 'quotation', 'cancelled']),
            })
    shipment_party = fields.Many2One('party.party', 'Shipment Party',
        states={
            'readonly': (Eval('state') != 'draft'),
            },
        context={
            'company': Eval('company', -1),
            },
        search_context={
            'related_party': Eval('party'),
            },
        depends={'company'})
    shipment_address = fields.Many2One('party.address', 'Shipment Address',
        domain=[
            ('party', '=', If(Bool(Eval('shipment_party')),
                    Eval('shipment_party'), Eval('party'))),
            ],
        states={
            'readonly': Eval('state') != 'draft',
            })
    warehouse = fields.Many2One('stock.location', 'Warehouse',
        domain=[('type', '=', 'warehouse')], states={
            'readonly': Eval('state') != 'draft',
            })
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states={
            'readonly': ((Eval('state') != 'draft')
                | (Eval('lines', [0]) & Eval('currency', 0))),
            })
    lines = fields.One2Many('sale.line', 'sale', 'Lines', states={
            'readonly': Eval('state') != 'draft',
            },
        depends={'party'})
    comment = fields.Text('Comment')
    untaxed_amount = fields.Function(Monetary(
            "Untaxed", digits='currency', currency='currency'), 'get_amount')
    untaxed_amount_cache = fields.Numeric(
        "Untaxed Cache", digits='currency', readonly=True)
    tax_amount = fields.Function(Monetary(
            "Tax", digits='currency', currency='currency'), 'get_amount')
    tax_amount_cache = fields.Numeric(
        "Tax Cache", digits='currency', readonly=True)
    total_amount = fields.Function(Monetary(
            "Total", digits='currency', currency='currency'), 'get_amount')
    total_amount_cache = fields.Numeric(
        "Total Cache", digits='currency', readonly=True)
    invoice_method = fields.Selection([
            ('manual', 'Manual'),
            ('order', 'On Order Processed'),
            ('shipment', 'On Shipment Sent'),
            ],
        'Invoice Method', required=True, states={
            'readonly': Eval('state') != 'draft',
            })
    invoice_method_string = invoice_method.translated('invoice_method')
    invoice_state = fields.Selection([
            ('none', 'None'),
            ('waiting', 'Waiting'),
            ('paid', 'Paid'),
            ('exception', 'Exception'),
            ], 'Invoice State', readonly=True, required=True, sort=False)
    invoices = fields.Function(fields.Many2Many(
            'account.invoice', None, None, "Invoices"),
        'get_invoices', searcher='search_invoices')
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
            })
    shipment_method_string = shipment_method.translated('shipment_method')
    shipment_state = fields.Selection([
            ('none', 'None'),
            ('waiting', 'Waiting'),
            ('sent', 'Sent'),
            ('exception', 'Exception'),
            ], "Shipment State", readonly=True, required=True, sort=False)
    shipments = fields.Function(fields.Many2Many(
            'stock.shipment.out', None, None, "Shipments"),
        'get_shipments', searcher='search_shipments')
    shipment_returns = fields.Function(fields.Many2Many(
            'stock.shipment.out.return', None, None, "Shipment Returns"),
        'get_shipment_returns', searcher='search_shipment_returns')
    moves = fields.Function(
        fields.Many2Many('stock.move', None, None, "Moves"),
        'get_moves', searcher='search_moves')
    origin = fields.Reference('Origin', selection='get_origin', select=True,
        states={
            'readonly': Eval('state') != 'draft',
            })
    shipping_date = fields.Date(
        "Shipping Date",
        domain=[If(Bool(Eval('sale_date')) & Bool(Eval('shipping_date')),
                ('shipping_date', '>=', Eval('sale_date')),
                ()),
            ],
        states={
            'readonly': Eval('state').in_(['processing', 'done', 'cancelled']),
            },
        help="When the shipping of goods should start.")

    quoted_by = employee_field(
        "Quoted By",
        states=['quotation', 'confirmed', 'processing', 'done', 'cancelled'])
    confirmed_by = employee_field(
        "Confirmed By",
        states=['confirmed', 'processing', 'done', 'cancelled'])
    state = fields.Selection([
            ('draft', "Draft"),
            ('quotation', "Quotation"),
            ('confirmed', "Confirmed"),
            ('processing', "Processing"),
            ('done', "Done"),
            ('cancelled', "Cancelled"),
            ], "State", readonly=True, required=True, sort=False)
    state_string = state.translated('state')

    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()
        cls.create_date.select = True
        cls._order = [
            ('sale_date', 'DESC NULLS FIRST'),
            ('id', 'DESC'),
            ]
        cls._transitions |= set((
                ('draft', 'quotation'),
                ('quotation', 'confirmed'),
                ('confirmed', 'processing'),
                ('confirmed', 'draft'),
                ('processing', 'processing'),
                ('processing', 'done'),
                ('done', 'processing'),
                ('draft', 'cancelled'),
                ('quotation', 'cancelled'),
                ('quotation', 'draft'),
                ('cancelled', 'draft'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': ~Eval('state').in_(['draft', 'quotation']),
                    'depends': ['state'],
                    },
                'draft': {
                    'invisible': ~Eval('state').in_(
                        ['cancelled', 'quotation', 'confirmed']),
                    'icon': If(Eval('state') == 'cancelled',
                        'tryton-undo',
                        'tryton-back'),
                    'depends': ['state'],
                    },
                'quote': {
                    'invisible': Eval('state') != 'draft',
                    'readonly': ~Eval('lines', Eval('untaxed_amount', 0)),
                    'depends': ['state'],
                    },
                'confirm': {
                    'invisible': Eval('state') != 'quotation',
                    'depends': ['state'],
                    },
                'process': {
                    'invisible': ~Eval('state').in_(
                        ['confirmed', 'processing']),
                    'icon': If(Eval('state') == 'confirmed',
                        'tryton-forward', 'tryton-refresh'),
                    'depends': ['state'],
                    },
                'handle_invoice_exception': {
                    'invisible': ((Eval('invoice_state') != 'exception')
                        | (Eval('state') == 'cancelled')),
                    'depends': ['state', 'invoice_state'],
                    },
                'handle_shipment_exception': {
                    'invisible': ((Eval('shipment_state') != 'exception')
                        | (Eval('state') == 'cancelled')),
                    'depends': ['state', 'shipment_state'],
                    },
                'modify_header': {
                    'invisible': ((Eval('state') != 'draft')
                        | ~Eval('lines', [-1])),
                    'depends': ['state'],
                    },
                })
        # The states where amounts are cached
        cls._states_cached = ['confirmed', 'processing', 'done', 'cancelled']

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        table = cls.__table_handler__(module_name)
        sql_table = cls.__table__()

        # Migration from 3.8: rename reference into number
        if (table.column_exist('reference')
                and not table.column_exist('number')):
            table.column_rename('reference', 'number')

        super(Sale, cls).__register__(module_name)
        table = cls.__table_handler__(module_name)

        # Migration from 4.0: Drop not null on payment_term
        table.not_null_action('payment_term', 'remove')

        # Migration from 5.6: rename state cancel to cancelled
        cursor.execute(*sql_table.update(
                [sql_table.state], ['cancelled'],
                where=sql_table.state == 'cancel'))

    @classmethod
    def default_payment_term(cls, **pattern):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        config = Configuration(1)
        payment_term = config.get_multivalue(
            'default_customer_payment_term', **pattern)
        return payment_term.id if payment_term else None

    @classmethod
    def default_warehouse(cls):
        Location = Pool().get('stock.location')
        return Location.get_default_warehouse()

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @fields.depends('company')
    def on_change_company(self):
        self.payment_term = self.default_payment_term(
            company=self.company.id if self.company else None)
        self.invoice_method = self.default_invoice_method(
            company=self.company.id if self.company else None)
        self.shipment_method = self.default_shipment_method(
            company=self.company.id if self.company else None)

    @staticmethod
    def default_state():
        return 'draft'

    @classmethod
    def default_currency(cls, **pattern):
        pool = Pool()
        Company = pool.get('company.company')
        company = pattern.get('company')
        if not company:
            company = cls.default_company()
        if company:
            return Company(company).currency.id

    @classmethod
    def default_invoice_method(cls, **pattern):
        Config = Pool().get('sale.configuration')
        config = Config(1)
        return config.get_multivalue('sale_invoice_method', **pattern)

    @staticmethod
    def default_invoice_state():
        return 'none'

    @classmethod
    def default_shipment_method(cls, **pattern):
        Config = Pool().get('sale.configuration')
        config = Config(1)
        return config.get_multivalue('sale_shipment_method', **pattern)

    @staticmethod
    def default_shipment_state():
        return 'none'

    @fields.depends(
        'company', 'party', 'invoice_party', 'shipment_party', 'payment_term',
        'lines')
    def on_change_party(self):
        if not self.invoice_party:
            self.invoice_address = None
        if not self.shipment_party:
            self.shipment_address = None
        self.payment_term = self.default_payment_term(
            company=self.company.id if self.company else None)
        if not self.lines:
            self.currency = self.default_currency(
                company=self.company.id if self.company else None)
        if self.party:
            if not self.invoice_party:
                self.invoice_address = self.party.address_get(type='invoice')
            if not self.shipment_party:
                self.shipment_address = self.party.address_get(type='delivery')
                if self.party.sale_shipment_method:
                    self.shipment_method = self.party.sale_shipment_method
                else:
                    self.shipment_method = self.default_shipment_method()
            if self.party.customer_payment_term:
                self.payment_term = self.party.customer_payment_term
            if self.party.sale_invoice_method:
                self.invoice_method = self.party.sale_invoice_method
            else:
                self.invoice_method = self.default_invoice_method()
            if not self.lines:
                if self.party.customer_currency:
                    self.currency = self.party.customer_currency

    @fields.depends('party', 'invoice_party')
    def on_change_invoice_party(self):
        if self.invoice_party:
            self.invoice_address = self.invoice_party.address_get(
                type='invoice')
        elif self.party:
            self.invoice_address = self.party.address_get(type='invoice')

    @fields.depends('party', 'shipment_party')
    def on_change_shipment_party(self):
        if self.shipment_party:
            self.shipment_address = self.shipment_party.address_get(
                type='delivery')
        elif self.party:
            self.shipment_address = self.party.address_get(type='delivery')
            if self.party.sale_shipment_method:
                self.shipment_method = self.party.sale_shipment_method

    @fields.depends('party', 'company')
    def _get_tax_context(self):
        context = {}
        if self.party and self.party.lang:
            context['language'] = self.party.lang.code
        if self.company:
            context['company'] = self.company.id
        return context

    @fields.depends('party')
    def on_change_with_party_lang(self, name=None):
        Config = Pool().get('ir.configuration')
        if self.party and self.party.lang:
            return self.party.lang.code
        return Config.get_language()

    @fields.depends('lines', 'currency', methods=['get_tax_amount'])
    def on_change_lines(self):
        self.untaxed_amount = Decimal('0.0')
        self.tax_amount = Decimal('0.0')
        self.total_amount = Decimal('0.0')

        if self.lines:
            for line in self.lines:
                self.untaxed_amount += getattr(line, 'amount', None) or 0
            self.tax_amount = self.get_tax_amount()
        if self.currency:
            self.untaxed_amount = self.currency.round(self.untaxed_amount)
            self.tax_amount = self.currency.round(self.tax_amount)
        self.total_amount = self.untaxed_amount + self.tax_amount
        if self.currency:
            self.total_amount = self.currency.round(self.total_amount)

    @property
    def taxable_lines(self):
        taxable_lines = []
        for line in self.lines:
            taxable_lines.extend(line.taxable_lines)
        return taxable_lines

    @fields.depends(methods=['_get_taxes'])
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
                        if line.type == 'line'), Decimal(0))
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
            if any(i.state == 'cancelled' for i in invoices):
                return 'exception'
            elif all(i.state == 'paid' for i in invoices):
                return 'paid'
            else:
                return 'waiting'
        return 'none'

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

    def get_moves(self, name):
        return [m.id for l in self.lines for m in l.moves]

    @classmethod
    def search_moves(cls, name, clause):
        return [('lines.' + clause[0],) + tuple(clause[1:])]

    @classmethod
    def _get_origin(cls):
        'Return list of Model names for origin Reference'
        return ['sale.sale']

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        get_name = Model.get_name
        models = cls._get_origin()
        return [(None, '')] + [(m, get_name(m)) for m in models]

    @property
    def report_address(self):
        if self.invoice_address:
            return self.invoice_address.full_address
        else:
            return ''

    @classmethod
    def validate_fields(cls, sales, field_names):
        super().validate_fields(sales, field_names)
        cls.check_method(sales, field_names)

    @classmethod
    def check_method(cls, sales, field_names=None):
        '''
        Check the methods.
        '''
        if field_names and not (field_names & {
                    'invoice_method', 'shipment_method'}):
            return
        for sale in sales:
            if (sale.invoice_method == 'shipment'
                    and sale.shipment_method in {'invoice', 'manual'}):
                raise SaleValidationError(
                    gettext('sale.msg_sale_invalid_method',
                        invoice_method=sale.invoice_method_string,
                        shipment_method=sale.shipment_method_string,
                        sale=sale.rec_name))
            if (sale.shipment_method == 'invoice'
                    and sale.invoice_method in {'shipment', 'manual'}):
                raise SaleValidationError(
                    gettext('sale.msg_sale_invalid_method',
                        invoice_method=sale.invoice_method_string,
                        shipment_method=sale.shipment_method_string,
                        sale=sale.rec_name))

    @property
    def full_number(self):
        return self.number

    def get_rec_name(self, name):
        items = []
        if self.full_number:
            items.append(self.full_number)
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
        attributes = super().view_attributes() + [
            ('/form//field[@name="comment"]', 'spell', Eval('party_lang')),
            ('/tree', 'visual', If(Eval('state') == 'cancelled', 'muted', '')),
            ('/tree/field[@name="invoice_state"]', 'visual',
                If(Eval('invoice_state') == 'exception', 'danger', '')),
            ('/tree/field[@name="shipment_state"]', 'visual',
                If(Eval('shipment_state') == 'exception', 'danger', '')),
            ]
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
    def get_resources_to_copy(cls, name):
        return {
            'stock.shipment.out',
            'stock.shipment.out.return',
            'account.invoice',
            }

    @classmethod
    def copy(cls, sales, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('number', None)
        default.setdefault('invoice_state', 'none')
        default.setdefault('invoices_ignored', None)
        default.setdefault('shipment_state', 'none')
        default.setdefault('sale_date', None)
        default.setdefault('quoted_by')
        default.setdefault('confirmed_by')
        return super(Sale, cls).copy(sales, default=default)

    def check_for_quotation(self):
        if not self.invoice_address:
            raise SaleQuotationError(
                gettext('sale.msg_sale_invoice_address_required_for_quotation',
                    sale=self.rec_name))
        for line in self.lines:
            if (line.product and line.product.type != 'service'
                    and not self.shipment_address):
                raise SaleQuotationError(
                    gettext('sale'
                        '.msg_sale_shipment_address_required_for_quotation',
                        sale=self.rec_name))
            if (line.quantity or 0) >= 0:
                location = line.from_location
            else:
                location = line.to_location
            if ((not location or not line.warehouse)
                    and line.product
                    and line.product.type in line.get_move_product_types()):
                raise SaleQuotationError(
                    gettext('sale.msg_sale_warehouse_required_for_quotation',
                        sale=self.rec_name))

    @classmethod
    def set_number(cls, sales):
        '''
        Fill the number field with the sale sequence
        '''
        pool = Pool()
        Config = pool.get('sale.configuration')

        config = Config(1)
        for sale in sales:
            if sale.number:
                continue
            sale.number = config.get_multivalue(
                'sale_sequence', company=sale.company.id).get()
        cls.save(sales)

    @classmethod
    def set_sale_date(cls, sales):
        Date = Pool().get('ir.date')
        for company, c_sales in groupby(sales, key=lambda s: s.company):
            with Transaction().set_context(company=company.id):
                today = Date.today()
            cls.write([s for s in c_sales if not s.sale_date], {
                    'sale_date': today,
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
        party = self.invoice_party or self.party
        invoice = Invoice(
            company=self.company,
            type='out',
            party=party,
            invoice_address=self.invoice_address,
            currency=self.currency,
            account=party.account_receivable_used,
            )
        invoice.on_change_type()
        invoice.payment_term = self.payment_term
        return invoice

    def create_invoice(self):
        'Create and return an invoice'
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

        invoice.update_taxes()
        self.copy_resources_to(invoice)
        return invoice

    def _group_shipment_key(self, moves, move):
        '''
        The key to group moves by shipments

        move is a tuple of line and a move
        '''
        line, move = move

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
            'customer': self.shipment_party or self.party,
            'delivery_address': self.shipment_address,
            'company': self.company,
            }
        values.update(dict(key))
        return Shipment(**values)

    def _get_shipment_moves(self, shipment_type):
        moves = {}
        for line in self.lines:
            move = line.get_move(shipment_type)
            if move:
                moves[line] = move
        return moves

    def create_shipment(self, shipment_type):
        '''
        Create and return shipments of type shipment_type
        '''
        pool = Pool()

        if self.shipment_method == 'manual':
            return

        moves = self._get_shipment_moves(shipment_type)
        if not moves:
            return
        if shipment_type == 'out':
            keyfunc = partial(self._group_shipment_key, list(moves.values()))
            Shipment = pool.get('stock.shipment.out')
        elif shipment_type == 'return':
            keyfunc = partial(self._group_return_key, list(moves.values()))
            Shipment = pool.get('stock.shipment.out.return')
        moves = moves.items()
        moves = sorted(moves, key=sortable_values(keyfunc))

        shipments = []
        for key, grouped_moves in groupby(moves, key=keyfunc):
            shipment = self._get_shipment_sale(Shipment, key)
            shipment.moves = (list(getattr(shipment, 'moves', []))
                + [x[1] for x in grouped_moves])
            shipment.save()
            self.copy_resources_to(shipment)
            shipments.append(shipment)
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
            if sale.state != 'cancelled':
                raise AccessError(
                    gettext('sale.msg_sale_delete_cancel',
                        sale=sale.rec_name))
        super(Sale, cls).delete(sales)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, sales):
        cls.store_cache(sales)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    @reset_employee('quoted_by', 'confirmed_by')
    def draft(cls, sales):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('quotation')
    @set_employee('quoted_by')
    def quote(cls, sales):
        for sale in sales:
            sale.check_for_quotation()
        cls.set_number(sales)

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    @set_employee('confirmed_by')
    def confirm(cls, sales):
        pool = Pool()
        Configuration = pool.get('sale.configuration')
        transaction = Transaction()
        context = transaction.context
        cls.set_sale_date(sales)
        cls.store_cache(sales)
        config = Configuration(1)
        with transaction.set_context(
                queue_scheduled_at=config.sale_process_after,
                queue_batch=context.get('queue_batch', True)):
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
        states = {'confirmed', 'processing', 'done'}
        sales = [s for s in sales if s.state in states]
        cls.lock(sales)
        cls._process_invoice(sales)
        cls._process_shipment(sales)
        cls._process_invoice_shipment_states(sales)
        cls._process_state(sales)

    @classmethod
    def _process_invoice(cls, sales):
        pool = Pool()
        Invoice = pool.get('account.invoice')

        invoices = {}
        for sale in sales:
            invoice = sale.create_invoice()
            if invoice:
                invoices[sale] = invoice

        Invoice.save(invoices.values())
        Invoice.update_taxes(invoices.values())
        for sale, invoice in invoices.items():
            sale.copy_resources_to(invoice)

    @classmethod
    def _process_shipment(cls, sales):
        pool = Pool()
        ShipmentOut = pool.get('stock.shipment.out')
        ShipmentOutReturn = pool.get('stock.shipment.out.return')

        shipments_out, shipments_return = {}, {}
        for sale in sales:
            shipments = sale.create_shipment('out')
            if shipments:
                shipments_out[sale] = shipments
            shipments = sale.create_shipment('return')
            if shipments:
                shipments_return[sale] = shipments

        shipments = sum((v for v in shipments_out.values()), [])
        ShipmentOut.save(shipments)
        ShipmentOut.wait(shipments)
        for sale, shipments in shipments_out.items():
            for shipment in shipments:
                sale.copy_resources_to(shipment)

        shipments = sum((v for v in shipments_return.values()), [])
        ShipmentOutReturn.save(shipments)
        for sale, shipments in shipments_return.items():
            for shipment in shipments:
                sale.copy_resources_to(shipment)

    @classmethod
    def _process_invoice_shipment_states(cls, sales):
        pool = Pool()
        Line = pool.get('sale.line')
        lines = []
        invoice_states, shipment_states = defaultdict(list), defaultdict(list)
        for sale in sales:
            invoice_state = sale.get_invoice_state()
            if sale.invoice_state != invoice_state:
                invoice_states[invoice_state].append(sale)
            shipment_state = sale.get_shipment_state()
            if sale.shipment_state != shipment_state:
                shipment_states[shipment_state].append(sale)

            for line in sale.lines:
                line.set_actual_quantity()
                lines.append(line)

        for invoice_state, sales in invoice_states.items():
            cls.write(sales, {'invoice_state': invoice_state})
        for shipment_state, sales in shipment_states.items():
            cls.write(sales, {'shipment_state': shipment_state})
        Line.save(lines)

    @classmethod
    def _process_state(cls, sales):
        done, process = [], []
        for sale in sales:
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


class SaleLine(TaxableMixin, sequence_ordered(), ModelSQL, ModelView):
    'Sale Line'
    __name__ = 'sale.line'
    sale = fields.Many2One('sale.sale', 'Sale', ondelete='CASCADE',
        select=True, required=True,
        states={
            'readonly': ((Eval('sale_state') != 'draft')
                & Bool(Eval('sale'))),
            })
    type = fields.Selection([
        ('line', 'Line'),
        ('subtotal', 'Subtotal'),
        ('title', 'Title'),
        ('comment', 'Comment'),
        ], 'Type', select=True, required=True,
        states={
            'readonly': Eval('sale_state') != 'draft',
            })
    quantity = fields.Float(
        "Quantity", digits='unit',
        states={
            'invisible': Eval('type') != 'line',
            'required': Eval('type') == 'line',
            'readonly': Eval('sale_state') != 'draft',
            })
    actual_quantity = fields.Float(
        "Actual Quantity", digits='unit', readonly=True,
        states={
            'invisible': Eval('type') != 'line',
            })
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
            ])
    product = fields.Many2One('product.product', 'Product',
        ondelete='RESTRICT',
        domain=[
            If(Eval('sale_state').in_(['draft', 'quotation']),
                ('salable', '=', True),
                ()),
            ],
        states={
            'invisible': Eval('type') != 'line',
            'readonly': Eval('sale_state') != 'draft',
            },
        context={
            'company': Eval('company', None),
            },
        search_context={
            'locations': If(Bool(Eval('_parent_sale', {}).get('warehouse')),
                [Eval('_parent_sale', {}).get('warehouse', 0)], []),
            'stock_date_end': Eval('_parent_sale', {}).get('sale_date'),
            'stock_skip_warehouse': True,
            'currency': Eval('_parent_sale', {}).get('currency'),
            'customer': Eval('_parent_sale', {}).get('party'),
            'sale_date': Eval('_parent_sale', {}).get('sale_date'),
            'uom': Eval('unit'),
            'taxes': Eval('taxes', []),
            'quantity': Eval('quantity'),
            },
        depends={'company'})
    product_uom_category = fields.Function(
        fields.Many2One('product.uom.category', 'Product Uom Category'),
        'on_change_with_product_uom_category')
    unit_price = Monetary(
        "Unit Price", digits=price_digits, currency='currency',
        states={
            'invisible': Eval('type') != 'line',
            'required': Eval('type') == 'line',
            'readonly': Eval('sale_state') != 'draft'
            })
    amount = fields.Function(Monetary(
            "Amount", digits='currency', currency='currency',
            states={
                'invisible': ~Eval('type').in_(['line', 'subtotal']),
                },
            depends={'sale_state'}), 'get_amount')
    currency = fields.Function(
        fields.Many2One('currency.currency', 'Currency'),
        'on_change_with_currency')
    description = fields.Text('Description', size=None,
        states={
            'readonly': Eval('sale_state') != 'draft',
            },
        depends=['sale_state'])
    summary = fields.Function(fields.Char('Summary'), 'on_change_with_summary')
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
            },
        depends={'sale'})
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
                }),
        'on_change_with_shipping_date')
    sale_state = fields.Function(
        fields.Selection('get_sale_states', "Sale State"),
        'on_change_with_sale_state')
    company = fields.Function(
        fields.Many2One('company.company', "Company"),
        'on_change_with_company')

    @classmethod
    def get_move_product_types(cls):
        pool = Pool()
        Move = pool.get('stock.move')
        return Move.get_product_types()

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('sale')

    @classmethod
    def __register__(cls, module_name):
        super(SaleLine, cls).__register__(module_name)
        table = cls.__table_handler__(module_name)

        # Migration from 4.6: drop required on description
        table.not_null_action('description', action='remove')

    @staticmethod
    def default_type():
        return 'line'

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
            if move.state == 'cancelled' \
                    and move.id not in skip_ids:
                return True
        return False

    @property
    def taxable_lines(self):
        # In case we're called from an on_change
        # we have to use some sensible defaults
        if getattr(self, 'type', None) == 'line':
            return [(
                    getattr(self, 'taxes', None) or [],
                    getattr(self, 'unit_price', None) or Decimal(0),
                    getattr(self, 'quantity', None) or 0,
                    None,
                    )]
        else:
            return []

    def _get_tax_context(self):
        return self.sale._get_tax_context()

    def _get_tax_rule_pattern(self):
        '''
        Get tax rule pattern
        '''
        return {}

    @fields.depends(
        'sale', '_parent_sale.currency', '_parent_sale.party',
        '_parent_sale.sale_date', 'company',
        'unit', 'product', 'taxes')
    def _get_context_sale_price(self):
        context = {}
        if self.sale:
            if self.sale.currency:
                context['currency'] = self.sale.currency.id
            if self.sale.party:
                context['customer'] = self.sale.party.id
            context['sale_date'] = self.sale.sale_date
        if self.company:
            context['company'] = self.company.id
        if self.unit:
            context['uom'] = self.unit.id
        elif self.product:
            context['uom'] = self.product.sale_uom.id
        context['taxes'] = [t.id for t in self.taxes or []]
        return context

    @fields.depends('product', 'unit', 'sale',
        '_parent_sale.party', '_parent_sale.invoice_party',
        methods=['compute_taxes', 'compute_unit_price',
            'on_change_with_amount'])
    def on_change_product(self):
        if not self.product:
            return

        party = None
        if self.sale:
            party = self.sale.invoice_party or self.sale.party

        # Set taxes before unit_price to have taxes in context of sale price
        self.taxes = self.compute_taxes(party)

        category = self.product.sale_uom.category
        if not self.unit or self.unit.category != category:
            self.unit = self.product.sale_uom

        self.unit_price = self.compute_unit_price()

        self.type = 'line'
        self.amount = self.on_change_with_amount()

    @fields.depends('product', methods=['_get_tax_rule_pattern'])
    def compute_taxes(self, party):
        taxes = set()
        pattern = self._get_tax_rule_pattern()
        for tax in self.product.customer_taxes_used:
            if party and party.customer_tax_rule:
                tax_ids = party.customer_tax_rule.apply(tax, pattern)
                if tax_ids:
                    taxes.update(tax_ids)
                continue
            taxes.add(tax.id)
        if party and party.customer_tax_rule:
            tax_ids = party.customer_tax_rule.apply(None, pattern)
            if tax_ids:
                taxes.update(tax_ids)
        return list(taxes)

    @fields.depends('product', 'quantity', methods=['_get_context_sale_price'])
    def compute_unit_price(self):
        pool = Pool()
        Product = pool.get('product.product')

        if not self.product:
            return

        with Transaction().set_context(
                self._get_context_sale_price()):
            unit_price = Product.get_sale_price([self.product],
                self.quantity or 0)[self.product.id]
            if unit_price is not None:
                unit_price = round_price(unit_price)
            return unit_price

    @fields.depends('product')
    def on_change_with_product_uom_category(self, name=None):
        if self.product:
            return self.product.default_uom_category.id

    @fields.depends(methods=['compute_unit_price'])
    def on_change_quantity(self):
        self.unit_price = self.compute_unit_price()

    @fields.depends(methods=['on_change_quantity'])
    def on_change_unit(self):
        self.on_change_quantity()

    @fields.depends(methods=['on_change_quantity'])
    def on_change_taxes(self):
        self.on_change_quantity()

    @fields.depends('description')
    def on_change_with_summary(self, name=None):
        return firstline(self.description or '')

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

    @fields.depends('moves', methods=['planned_shipping_date'])
    def on_change_with_shipping_date(self, name=None):
        moves = [m for m in self.moves if m.state != 'cancelled']
        if moves:
            dates = filter(
                None, (m.effective_date or m.planned_date for m in moves))
            return min(dates, default=None)
        return self.planned_shipping_date

    @property
    @fields.depends(
        'product', 'quantity', 'company', 'sale',
        '_parent_sale.sale_date', '_parent_sale.shipping_date')
    def planned_shipping_date(self):
        pool = Pool()
        Date = pool.get('ir.date')
        transaction = Transaction()
        if self.product and self.quantity is not None and self.quantity > 0:
            date = self.sale.sale_date if self.sale else None
            shipping_date = self.product.compute_shipping_date(date=date)
            if shipping_date == datetime.date.max:
                shipping_date = None
            elif self.sale and self.sale.shipping_date:
                shipping_date = max(shipping_date, self.sale.shipping_date)
            if shipping_date:
                if self.company:
                    company_id = self.company.id
                else:
                    company_id = transaction.context.get('company')
                with transaction.set_context(company=company_id):
                    shipping_date = max(shipping_date, Date.today())
            return shipping_date

    @fields.depends('sale', '_parent_sale.currency')
    def on_change_with_currency(self, name=None):
        if self.sale and self.sale.currency:
            return self.sale.currency.id

    @classmethod
    def get_sale_states(cls):
        pool = Pool()
        Sale = pool.get('sale.sale')
        return Sale.fields_get(['state'])['state']['selection']

    @fields.depends('sale', '_parent_sale.state')
    def on_change_with_sale_state(self, name=None):
        if self.sale:
            return self.sale.state

    @fields.depends('sale', '_parent_sale.company')
    def on_change_with_company(self, name=None):
        if self.sale and self.sale.company:
            return self.sale.company.id

    def get_invoice_line(self):
        'Return a list of invoice lines for sale line'
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        AccountConfiguration = pool.get('account.configuration')
        account_config = AccountConfiguration(1)

        invoice_line = InvoiceLine()
        invoice_line.type = self.type
        invoice_line.currency = self.currency
        invoice_line.company = self.company
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
                raise AccountError(
                    gettext('sale.msg_sale_product_missing_account_revenue',
                        sale=self.sale.rec_name,
                        product=self.product.rec_name))
        else:
            invoice_line.account = account_config.get_multivalue(
                'default_category_account_revenue', company=self.company.id)
            if not invoice_line.account:
                raise AccountError(
                    gettext('sale.msg_sale_missing_account_revenue',
                        sale=self.sale.rec_name))
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
                if move.state != 'done':
                    continue
                qty = Uom.compute_qty(move.uom, move.quantity, self.unit)
                # Test only against to_location
                # as it is what matters for sale
                dest_type = self.to_location.type
                if (move.to_location.type == dest_type
                        and move.from_location.type != dest_type):
                    quantity += qty
                elif (move.from_location.type == dest_type
                        and move.to_location.type != dest_type):
                    quantity -= qty
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

        if self.type != 'line':
            return
        if not self.product:
            return
        if self.product.type not in Move.get_product_types():
            return

        if (shipment_type == 'out') != (self.quantity >= 0):
            return

        quantity = (self._get_move_quantity(shipment_type)
            - self._get_shipped_quantity(shipment_type))

        quantity = self.unit.round(quantity)
        if quantity <= 0:
            return

        if not self.sale.party.customer_location:
            raise PartyLocationError(
                gettext('sale.msg_sale_customer_location_required',
                    sale=self.sale.rec_name,
                    party=self.sale.party.rec_name))
        move = Move()
        move.quantity = quantity
        move.uom = self.unit
        move.product = self.product
        move.from_location = self.from_location
        move.to_location = self.to_location
        move.state = 'draft'
        move.company = self.sale.company
        if move.on_change_with_unit_price_required():
            move.unit_price = self.unit_price
            move.currency = self.sale.currency
        move.planned_date = self.planned_shipping_date
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

    def set_actual_quantity(self):
        pool = Pool()
        Uom = pool.get('product.uom')
        if self.type != 'line':
            return
        moved_quantity = 0
        for move in self.moves:
            if move.state != 'cancelled' and self.unit:
                moved_quantity += Uom.compute_qty(
                    move.uom, move.quantity, self.unit, round=False)
        if self.quantity < 0:
            moved_quantity *= -1
        invoiced_quantity = 0
        for invoice_line in self.invoice_lines:
            if (
                    (not invoice_line.invoice
                        or invoice_line.invoice.state != 'cancelled')
                    and self.unit and invoice_line.unit):
                invoiced_quantity += Uom.compute_qty(
                    invoice_line.unit, invoice_line.quantity, self.unit,
                    round=False)
        actual_quantity = max(moved_quantity, invoiced_quantity, key=abs)
        if self.unit:
            actual_quantity = self.unit.round(actual_quantity)
        if self.actual_quantity != actual_quantity:
            self.actual_quantity = actual_quantity

    def get_rec_name(self, name):
        pool = Pool()
        Lang = pool.get('ir.lang')
        if self.product:
            lang = Lang.get()
            return (lang.format_number_symbol(
                    self.quantity or 0, self.unit, digits=self.unit.digits)
                + ' %s @ %s' % (self.product.rec_name, self.sale.rec_name))
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
        return super().view_attributes() + [
            ('/form//field[@name="note"]|/form//field[@name="description"]',
                'spell', Eval('_parent_sale', {}).get('party_lang'))]

    @classmethod
    def delete(cls, lines):
        for line in lines:
            if line.sale_state not in {'cancelled', 'draft'}:
                raise AccessError(
                    gettext('sale.msg_sale_line_delete_cancel_draft',
                        line=line.rec_name,
                        sale=line.sale.rec_name))
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
        default.setdefault('actual_quantity')
        return super(SaleLine, cls).copy(lines, default=default)


class SaleLineTax(ModelSQL):
    'Sale Line - Tax'
    __name__ = 'sale.line-account.tax'
    _table = 'sale_line_account_tax'
    line = fields.Many2One('sale.line', 'Sale Line', ondelete='CASCADE',
            select=True, required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
            select=True, required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('line_tax_unique', Unique(t, t.line, t.tax),
                'sale.msg_sale_line_tax_unique'),
            ]


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
    def get_context(cls, records, header, data):
        pool = Pool()
        Date = pool.get('ir.date')
        context = super().get_context(records, header, data)
        with Transaction().set_context(company=header['company'].id):
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
        customer_ids = [line[0] for line in cursor]
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
        domain=[('id', 'in', Eval('domain_moves'))])
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
        moves = []
        for line in self.record.lines:
            skips = set(line.moves_ignored)
            skips.update(line.moves_recreated)
            for move in line.moves:
                if move.state == 'cancelled' and move not in skips:
                    moves.append(move.id)
        return {
            'recreate_moves': moves,
            'domain_moves': moves,
            }

    def transition_handle(self):
        pool = Pool()
        SaleLine = pool.get('sale.line')

        for line in self.record.lines:
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
        self.model.__queue__.process([self.record])
        return 'end'


class HandleInvoiceExceptionAsk(ModelView):
    'Handle Invoice Exception'
    __name__ = 'sale.handle.invoice.exception.ask'
    recreate_invoices = fields.Many2Many(
        'account.invoice', None, None, 'Recreate Invoices',
        domain=[('id', 'in', Eval('domain_invoices'))],
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
        skips = set(self.record.invoices_ignored)
        skips.update(self.record.invoices_recreated)
        invoices = []
        for invoice in self.record.invoices:
            if invoice.state == 'cancelled' and invoice not in skips:
                invoices.append(invoice.id)
        return {
            'recreate_invoices': invoices,
            'domain_invoices': invoices,
            }

    def transition_handle(self):
        invoices_ignored = []
        invoices_recreated = []
        for invoice in self.ask.domain_invoices:
            if invoice in self.ask.recreate_invoices:
                invoices_recreated.append(invoice.id)
            else:
                invoices_ignored.append(invoice.id)

        self.model.write([self.record], {
                'invoices_ignored': [('add', invoices_ignored)],
                'invoices_recreated': [('add', invoices_recreated)],
                })
        self.model.__queue__.process([self.record])
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
        sales = self.records
        return_sales = self.model.copy(sales)
        for return_sale, sale in zip(return_sales, sales):
            return_sale.origin = sale
            for line in return_sale.lines:
                if line.type == 'line':
                    line.quantity *= -1
            return_sale.lines = return_sale.lines  # Force saving
        self.model.save(return_sales)

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

    def get_sale(self):
        if self.record.state != 'draft':
            raise AccessError(
                gettext('sale.msg_sale_modify_header_draft',
                    sale=self.record.rec_name))
        return self.record

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
        self.model.write([sale], self.start._save_values)

        # Call on_change after the save to ensure parent sale
        # has the modified values
        for line in sale.lines:
            line.on_change_product()
        Line.save(sale.lines)

        return 'end'
