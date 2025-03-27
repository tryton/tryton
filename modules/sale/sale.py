# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import math
from collections import defaultdict
from decimal import Decimal
from functools import partial
from itertools import chain, groupby

from sql import Null
from sql.functions import CharLength

from trytond import backend
from trytond.i18n import gettext
from trytond.ir.attachment import AttachmentCopyMixin
from trytond.ir.note import NoteCopyMixin
from trytond.model import (
    Index, Model, ModelSQL, ModelView, Unique, Workflow, fields,
    sequence_ordered)
from trytond.model.exceptions import AccessError
from trytond.modules.account.tax import TaxableMixin
from trytond.modules.account_product.exceptions import AccountError
from trytond.modules.company import CompanyReport
from trytond.modules.company.model import (
    employee_field, reset_employee, set_employee)
from trytond.modules.currency.fields import Monetary
from trytond.modules.product import price_digits
from trytond.pool import Pool
from trytond.pyson import Bool, Eval, If
from trytond.tools import cached_property, firstline, sortable_values
from trytond.transaction import Transaction
from trytond.wizard import (
    Button, StateAction, StateTransition, StateView, Wizard)

from .exceptions import (
    PartyLocationError, SaleMoveQuantity, SaleQuotationError,
    SaleValidationError)


def samesign(a, b):
    return math.copysign(a, b) == a


def get_shipments_returns(model_name):
    "Computes the returns or shipments"
    def method(self, name):
        Model = Pool().get(model_name)
        shipments = set()
        for line in self.line_lines:
            for move in line.moves:
                if isinstance(move.shipment, Model):
                    shipments.add(move.shipment.id)
        return list(shipments)
    return method


def search_shipments_returns(model_name):
    "Search on shipments or returns"
    def method(self, name, clause):
        _, operator, operand, *extra = clause
        nested = clause[0][len(name):]
        if not nested:
            if isinstance(clause[2], str):
                nested = '.rec_name'
            else:
                nested = '.id'
        return [('lines.moves.shipment' + nested,
                operator, operand, model_name, *extra)]
    return classmethod(method)


class Sale(
        Workflow, ModelSQL, ModelView, TaxableMixin,
        AttachmentCopyMixin, NoteCopyMixin):
    'Sale'
    __name__ = 'sale.sale'
    _rec_name = 'number'
    company = fields.Many2One(
        'company.company', "Company", required=True,
        states={
            'readonly': (
                (Eval('state') != 'draft')
                | Eval('lines', [0])
                | Eval('party', True)
                | Eval('invoice_party', True)
                | Eval('shipment_party', True)),
            })
    number = fields.Char("Number", readonly=True)
    reference = fields.Char("Reference")
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
    payment_term = fields.Many2One(
        'account.invoice.payment_term', "Payment Term", ondelete='RESTRICT',
        states={
            'readonly': Eval('state') != 'draft',
            })
    party = fields.Many2One(
        'party.party', "Party", required=True,
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
            'party_contact_mechanism_usage': 'invoice',
            },
        search_context={
            'related_party': Eval('party'),
            },
        depends={'company'})
    invoice_address = fields.Many2One('party.address', 'Invoice Address',
        domain=[
            ('party', '=', If(Bool(Eval('invoice_party')),
                    Eval('invoice_party', -1), Eval('party', -1))),
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
            'party_contact_mechanism_usage': 'delivery',
            },
        search_context={
            'related_party': Eval('party'),
            },
        depends={'company'})
    shipment_address = fields.Many2One('party.address', 'Shipment Address',
        domain=['OR',
            ('party', '=', If(Bool(Eval('shipment_party')),
                    Eval('shipment_party', -1), Eval('party', -1))),
            ('warehouses', 'where', [
                    ('id', '=', Eval('warehouse', -1)),
                    If(Eval('state').in_(['draft', 'quotation']),
                        ('allow_pickup', '=', True),
                        ()),
                    ]),
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
    lines = fields.One2Many(
        'sale.line', 'sale', "Lines",
        states={
            'readonly': (
                (Eval('state') != 'draft')
                | ~Eval('company')
                | ~Eval('currency')),
            })
    line_lines = fields.One2Many(
        'sale.line', 'sale', "Line - Lines", readonly=True,
        filter=[
            ('type', '=', 'line'),
            ])
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
            ('pending', "Pending"),
            ('awaiting payment', "Awaiting Payment"),
            ('partially paid', "Partially Paid"),
            ('paid', 'Paid'),
            ('exception', 'Exception'),
            ], 'Invoice State', readonly=True, required=True, sort=False)
    invoices = fields.Function(fields.Many2Many(
            'account.invoice', None, None, "Invoices"),
        'get_invoices', searcher='search_invoices')
    invoices_ignored = fields.Many2Many(
        'sale.sale-ignored-account.invoice', 'sale', 'invoice',
        "Ignored Invoices",
        domain=[
            ('id', 'in', Eval('invoices', [])),
            ('state', '=', 'cancelled'),
            ],
        states={
            'invisible': ~Eval('invoices_ignored', []),
            })
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
            ('partially shipped', 'Partially Shipped'),
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
        fields.Many2Many('stock.move', None, None, "Stock Moves"),
        'get_moves', searcher='search_moves')
    origin = fields.Reference(
        "Origin", selection='get_origin',
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
        cls.number.search_unaccented = False
        cls.reference.search_unaccented = False
        super(Sale, cls).__setup__()
        t = cls.__table__()
        cls._sql_indexes.update({
                Index(t, (t.reference, Index.Similarity())),
                Index(t, (t.party, Index.Range())),
                Index(
                    t,
                    (t.state, Index.Equality(cardinality='low')),
                    where=t.state.in_([
                            'draft', 'quotation', 'confirmed', 'processing'])),
                Index(
                    t,
                    (t.invoice_state, Index.Equality(cardinality='low')),
                    where=t.invoice_state.in_([
                            'none', 'waiting', 'exception'])),
                Index(
                    t,
                    (t.shipment_state, Index.Equality(cardinality='low')),
                    where=t.shipment_state.in_([
                            'none', 'waiting', 'exception'])),
                })
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
                        ['confirmed', 'processing', 'done']),
                    'icon': If(Eval('state') == 'confirmed',
                        'tryton-forward', 'tryton-refresh'),
                    'depends': ['state'],
                    },
                'manual_invoice': {
                    'invisible': (
                        (Eval('invoice_method') != 'manual')
                        | ~Eval('state').in_(['processing', 'done'])),
                    'depends': ['invoice_method', 'state'],
                    },
                'manual_shipment': {
                    'invisible': (
                        (Eval('shipment_method') != 'manual')
                        | ~Eval('state').in_(['processing', 'done'])),
                    'depends': ['shipment_method', 'state'],
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
        sql_table = cls.__table__()

        super(Sale, cls).__register__(module_name)

        # Migration from 5.6: rename state cancel to cancelled
        cursor.execute(*sql_table.update(
                [sql_table.state], ['cancelled'],
                where=sql_table.state == 'cancel'))

        # Migration from 6.6: rename invoice state waiting to pending
        cursor.execute(*sql_table.update(
                [sql_table.invoice_state], ['pending'],
                where=sql_table.invoice_state == 'waiting'))

    @classmethod
    def order_number(cls, tables):
        table, _ = tables[None]
        return [
            ~((table.state == 'cancelled') & (table.number == Null)),
            CharLength(table.number), table.number]

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
        if company is not None and company >= 0:
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
        'company', 'party', 'invoice_party', 'shipment_party', 'warehouse',
        'payment_term', 'lines')
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
                with Transaction().set_context(
                        warehouse=(
                            self.warehouse.id if self.warehouse else None)):
                    self.shipment_address = self.party.address_get(
                        type='delivery')
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

    @fields.depends('party', 'shipment_party', 'warehouse')
    def on_change_shipment_party(self):
        with Transaction().set_context(
                warehouse=self.warehouse.id if self.warehouse else None):
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
        self.untaxed_amount = Decimal(0)
        self.tax_amount = Decimal(0)
        self.total_amount = Decimal(0)

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
        # Browse separately not cached to limit number of lines read
        cached, not_cached = [], []
        for sale in sales:
            if sale.state in cls._states_cached:
                cached.append(sale)
            else:
                not_cached.append(sale)
        for sale in chain(cached, cls.browse(not_cached)):
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
                    (line.amount for line in sale.line_lines), Decimal(0))
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
        for line in self.line_lines:
            for invoice_line in line.invoice_lines:
                if invoice_line.invoice:
                    invoices.add(invoice_line.invoice.id)
        return list(invoices)

    @classmethod
    def search_invoices(cls, name, clause):
        return [
            ('lines', 'where', [
                    ('invoice_lines.invoice' + clause[0][len(name):],
                        *clause[1:]),
                    ('type', '=', 'line'),
                    ]),
            ]

    @property
    def _invoices_for_state(self):
        return self.invoices

    def get_invoice_state(self):
        '''
        Return the invoice state for the sale.
        '''
        skips = set(self.invoices_ignored)
        skips.update(self.invoices_recreated)
        invoices = [i for i in self._invoices_for_state if i not in skips]

        def is_cancelled(invoice):
            return invoice.state == 'cancelled' and not invoice.cancel_move

        def is_paid(invoice):
            return (
                invoice.state == 'paid'
                or (invoice.state == 'cancelled' and invoice.cancel_move))
        if invoices:
            if any(is_cancelled(i) for i in invoices):
                return 'exception'
            elif all(is_paid(i) for i in invoices):
                return 'paid'
            elif any(is_paid(i) for i in invoices):
                return 'partially paid'
            elif any(i.state == 'posted' for i in invoices):
                return 'awaiting payment'
            else:
                return 'pending'
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
        if any(l.moves_exception for l in self.line_lines):
            return 'exception'
        elif any(m.state != 'cancelled' for m in self.moves):
            if all(l.moves_progress >= 1.0 for l in self.line_lines
                    if l.moves_progress is not None):
                return 'sent'
            elif any(l.moves_progress for l in self.line_lines):
                return 'partially shipped'
            else:
                return 'waiting'
        return 'none'

    def get_moves(self, name):
        return [m.id for l in self.line_lines for m in l.moves]

    @classmethod
    def search_moves(cls, name, clause):
        return [
            ('lines', 'where', [
                    clause,
                    ('type', '=', 'line'),
                    ]),
            ]

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

    @property
    def delivery_full_address(self):
        if self.shipment_address:
            return self.shipment_address.full_address
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
                    ('//group[@id="amount"]', 'states', {'invisible': True}),
                    ('//group[@id="links"]', 'states', {'invisible': True}),
                    ('//group[@id="buttons"]', 'states', {'invisible': True}),
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
        default.setdefault('untaxed_amount_cache')
        default.setdefault('tax_amount_cache')
        default.setdefault('total_amount_cache')
        return super(Sale, cls).copy(sales, default=default)

    def check_for_quotation(self):
        if not self.invoice_address:
            raise SaleQuotationError(
                gettext('sale.msg_sale_invoice_address_required_for_quotation',
                    sale=self.rec_name))
        for line in self.line_lines:
            if (line.product
                    and line.product.type != 'service'
                    and line.quantity >= 0
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
                    and line.movable):
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
        for company, c_sales in groupby(sales, key=lambda s: s.company):
            c_sales = [s for s in c_sales if not s.number]
            if c_sales:
                sequence = config.get_multivalue(
                    'sale_sequence', company=company.id)
                for sale, number in zip(
                        c_sales, sequence.get_many(len(c_sales))):
                    sale.number = number
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
        sales = list(sales)
        cls.write(sales, {
                'untaxed_amount_cache': None,
                'tax_amount_cache': None,
                'total_amount_cache': None,
                })
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
        invoice.set_journal()
        invoice.payment_term = self.payment_term
        return invoice

    def create_invoice(self):
        'Create and return an invoice'
        context = Transaction().context
        if (self.invoice_method == 'manual'
                and not context.get('_sale_manual_invoice', False)):
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
            ('origin_planned_date', planned_date),
            ('warehouse', line.warehouse.id),
            )

    _group_return_key = _group_shipment_key

    def _get_shipment_sale(self, Shipment, key):
        values = {
            'customer': self.shipment_party or self.party,
            'company': self.company,
            }
        values.update(dict(key))
        shipment = Shipment(**values)
        shipment.on_change_warehouse()
        if Shipment.__name__ == 'stock.shipment.out':
            if self.shipment_address == self.warehouse.address:
                shipment.delivery_address = shipment.warehouse.address
            else:
                shipment.delivery_address = self.shipment_address
        elif Shipment.__name__ == 'stock.shipment.out.return':
            shipment.contact_address = values['customer'].address_get()
        return shipment

    def _get_shipment_moves(self, shipment_type):
        moves = {}
        for line in self.line_lines:
            move = line.get_move(shipment_type)
            if move:
                moves[line] = move
        return moves

    def create_shipment(self, shipment_type):
        '''
        Create and return shipments of type shipment_type
        '''
        pool = Pool()
        context = Transaction().context
        if (self.shipment_method == 'manual'
                and not context.get('_sale_manual_shipment', False)):
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
            shipments.append(shipment)
        return shipments

    def is_done(self):
        return ((self.invoice_state == 'paid'
                or (self.invoice_state == 'none'
                    and all(
                        l.invoice_progress >= 1
                        for l in self.line_lines
                        if l.invoice_progress is not None)))
            and (self.shipment_state == 'sent'
                or (self.shipment_state == 'none'
                    and all(
                        l.moves_progress >= 1
                        for l in self.line_lines
                        if l.moves_progress is not None))))

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
        cls.write(sales, {
                'tax_amount_cache': None,
                'untaxed_amount_cache': None,
                'total_amount_cache': None,
                })

    @classmethod
    @ModelView.button
    @Workflow.transition('quotation')
    @set_employee('quoted_by')
    def quote(cls, sales):
        for sale in sales:
            sale.check_for_quotation()
        cls.set_number(sales)

    @property
    def process_after(self):
        pool = Pool()
        Configuration = pool.get('sale.configuration')
        config = Configuration(1)
        return config.sale_process_after

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    @set_employee('confirmed_by')
    def confirm(cls, sales):
        transaction = Transaction()
        context = transaction.context
        cls.set_sale_date(sales)
        cls.store_cache(sales)
        for process_after, sub_sales in groupby(
                sales, lambda s: s.process_after):
            with transaction.set_context(
                    queue_scheduled_at=process_after,
                    queue_batch=context.get('queue_batch', True)):
                cls.__queue__.process(sub_sales)

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

            for line in sale.line_lines:
                line.set_actual_quantity()
                lines.append(line)

        for invoice_state, sales in invoice_states.items():
            cls.write(sales, {'invoice_state': invoice_state})
            cls.log(sales, 'transition', f'invoice_state:{invoice_state}')
        for shipment_state, sales in shipment_states.items():
            cls.write(sales, {'shipment_state': shipment_state})
            cls.log(sales, 'transition', f'shipment_state:{shipment_state}')
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
    @ModelView.button
    def manual_invoice(cls, sales):
        sales = [s for s in sales if s.invoice_method == 'manual']
        with Transaction().set_context(_sale_manual_invoice=True):
            cls.process(sales)

    @classmethod
    @ModelView.button
    def manual_shipment(cls, sales):
        sales = [s for s in sales if s.shipment_method == 'manual']
        with Transaction().set_context(_sale_manual_shipment=True):
            cls.process(sales)

    @classmethod
    @ModelView.button_action('sale.wizard_modify_header')
    def modify_header(cls, sales):
        pass


class SaleIgnoredInvoice(ModelSQL):
    'Sale - Ignored Invoice'
    __name__ = 'sale.sale-ignored-account.invoice'
    sale = fields.Many2One(
        'sale.sale', "Sale", ondelete='CASCADE', required=True)
    invoice = fields.Many2One(
        'account.invoice', "Invoice", ondelete='RESTRICT', required=True,
        domain=[
            ('sales', '=', Eval('sale', -1)),
            ('state', '=', 'cancelled'),
            ])

    @classmethod
    def __register__(cls, module):
        # Migration from 7.0: rename to standard name
        backend.TableHandler.table_rename(
            'sale_invoice_ignored_rel', cls._table)
        super().__register__(module)


class SaleRecreatedInvoice(ModelSQL):
    'Sale - Recreated Invoice'
    __name__ = 'sale.sale-recreated-account.invoice'
    sale = fields.Many2One(
        'sale.sale', "Sale", ondelete='CASCADE', required=True)
    invoice = fields.Many2One(
        'account.invoice', "Invoice", ondelete='RESTRICT', required=True,
        domain=[
            ('sales', '=', Eval('sale', -1)),
            ('state', '=', 'cancelled'),
            ])

    @classmethod
    def __register__(cls, module):
        # Migration from 7.0: rename to standard name
        backend.TableHandler.table_rename(
            'sale_invoice_recreated_rel', cls._table)
        super().__register__(module)


class SaleLine(TaxableMixin, sequence_ordered(), ModelSQL, ModelView):
    'Sale Line'
    __name__ = 'sale.line'
    sale = fields.Many2One(
        'sale.sale', "Sale", ondelete='CASCADE', required=True,
        states={
            'readonly': ((Eval('sale_state') != 'draft')
                & Bool(Eval('sale'))),
            })
    type = fields.Selection([
        ('line', 'Line'),
        ('subtotal', 'Subtotal'),
        ('title', 'Title'),
        ('comment', 'Comment'),
        ], "Type", required=True,
        states={
            'readonly': Eval('sale_state') != 'draft',
            })
    quantity = fields.Float(
        "Quantity", digits='unit',
        domain=[
            If(Eval('type') != 'line',
                ('quantity', '=', None),
                ()),
            ],
        states={
            'invisible': Eval('type') != 'line',
            'required': Eval('type') == 'line',
            'readonly': Eval('sale_state') != 'draft',
            })
    actual_quantity = fields.Float(
        "Actual Quantity", digits='unit', readonly=True,
        domain=[
            If(Eval('type') != 'line',
                ('actual_quantity', '=', None),
                ()),
            ],
        states={
            'invisible': ((Eval('type') != 'line') | ~Eval('actual_quantity')),
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
            If(Eval('type') != 'line',
                ('id', '=', None),
                ()),
            ])
    product = fields.Many2One('product.product', 'Product',
        ondelete='RESTRICT',
        domain=[
            If(Eval('sale_state').in_(['draft', 'quotation'])
                & ~(Eval('quantity', 0) < 0),
                ('salable', '=', True),
                ()),
            If(Eval('type') != 'line',
                ('id', '=', None),
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
            'locations': If(Bool(Eval('warehouse')),
                [Eval('warehouse', -1)], []),
            'stock_date_end': Eval('sale_date', None),
            'stock_skip_warehouse': True,
            'currency': Eval('currency', -1),
            'customer': Eval('customer', -1),
            'sale_date': Eval('sale_date', None),
            'uom': Eval('unit'),
            'taxes': Eval('taxes', []),
            'quantity': Eval('quantity'),
            },
        depends={
            'company', 'warehouse', 'sale_date', 'currency', 'customer'})
    product_uom_category = fields.Function(
        fields.Many2One(
            'product.uom.category', "Product UoM Category",
            help="The category of Unit of Measure for the product."),
        'on_change_with_product_uom_category')
    unit_price = Monetary(
        "Unit Price", digits=price_digits, currency='currency',
        domain=[
            If(Eval('type') != 'line',
                ('unit_price', '=', None),
                ()),
            ],
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
    summary = fields.Function(
        fields.Char('Summary'), 'on_change_with_summary',
        searcher='search_summary')
    note = fields.Text('Note')
    taxes = fields.Many2Many('sale.line-account.tax', 'line', 'tax', 'Taxes',
        order=[('tax.sequence', 'ASC'), ('tax.id', 'ASC')],
        domain=[
            ('parent', '=', None),
            ['OR',
                ('group', '=', None),
                ('group.kind', 'in', ['sale', 'both']),
                ],
            ('company', '=', Eval('company', -1)),
            If(Eval('type') != 'line',
                ('id', '=', None),
                ()),
            ],
        states={
            'invisible': Eval('type') != 'line',
            'readonly': Eval('sale_state') != 'draft',
            },
        depends={'sale'})
    invoice_lines = fields.One2Many(
        'account.invoice.line', 'origin', "Invoice Lines", readonly=True,
        states={
            'invisible': ~Eval('invoice_lines'),
            })
    invoice_progress = fields.Function(
        fields.Float("Invoice Progress", digits=(1, 4)),
        'get_invoice_progress')
    moves = fields.One2Many(
        'stock.move', 'origin', "Stock Moves", readonly=True,
        states={
            'invisible': ~Eval('moves'),
            })
    moves_ignored = fields.Many2Many(
        'sale.line-ignored-stock.move', 'sale_line', 'move',
        "Ignored Stock Moves",
        domain=[
            ('id', 'in', Eval('moves', [])),
            ('state', '=', 'cancelled'),
            ],
        states={
            'invisible': ~Eval('moves_ignored', []),
            })
    moves_recreated = fields.Many2Many(
        'sale.line-recreated-stock.move', 'sale_line', 'move',
        "Recreated Moves", readonly=True,
        states={
            'invisible': ~Eval('moves_recreated'),
            })
    moves_exception = fields.Function(fields.Boolean(
            "Moves Exception",
            states={
                'invisible': ~Eval('movable'),
                }),
        'get_moves_exception')
    moves_progress = fields.Function(fields.Float(
            "Moves Progress", digits=(1, 4),
            states={
                'invisible': ~Eval('movable'),
                }),
        'get_moves_progress')
    warehouse = fields.Function(fields.Many2One(
            'stock.location', "Warehouse",
            states={
                'invisible': ~Eval('movable'),
                }),
        'on_change_with_warehouse')
    from_location = fields.Function(fields.Many2One(
            'stock.location', "From Location",
            states={
                'invisible': ~Eval('movable'),
                }),
        'get_from_location')
    to_location = fields.Function(fields.Many2One(
            'stock.location', "To Location",
            states={
                'invisible': ~Eval('movable'),
                }),
        'get_to_location')
    movable = fields.Function(
        fields.Boolean("Movable"), 'on_change_with_movable')

    shipping_date = fields.Function(fields.Date('Shipping Date',
            states={
                'invisible': Eval('type') != 'line',
                }),
        'on_change_with_shipping_date')
    sale_state = fields.Function(
        fields.Selection('get_sale_states', "Sale State"),
        'on_change_with_sale_state', searcher='search_sale_state')
    company = fields.Function(
        fields.Many2One('company.company', "Company"),
        'on_change_with_company')
    customer = fields.Function(
        fields.Many2One(
            'party.party', "Customer",
            context={
                'company': Eval('company', -1),
                }),
        'on_change_with_customer', searcher='search_customer')
    sale_date = fields.Function(
        fields.Date("Sale Date"),
        'on_change_with_sale_date', searcher='search_sale_date')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('sale')
        cls._order.insert(0, ('sale.sale_date', 'DESC NULLS FIRST'))
        cls._order.insert(1, ('sale.id', 'DESC'))

    @staticmethod
    def default_type():
        return 'line'

    @fields.depends('type', 'taxes')
    def on_change_type(self):
        if self.type != 'line':
            self.product = None
            self.unit = None
            self.taxes = None

    @property
    def _invoice_remaining_quantity(self):
        "Compute the remaining quantity to be paid"
        pool = Pool()
        UoM = pool.get('product.uom')
        if self.type != 'line':
            return
        skips = set(self.sale.invoices_ignored)
        quantity = self.quantity
        if self.sale.invoice_method == 'shipment':
            moves_ignored = set(self.moves_ignored)
            for move in self.moves:
                if move in moves_ignored:
                    quantity -= UoM.compute_qty(
                        move.unit, math.copysign(move.quantity, self.quantity),
                        self.unit)
        for invoice_line in self.invoice_lines:
            if invoice_line.type != 'line':
                continue
            if (invoice_line.invoice
                    and (invoice_line.invoice.state == 'paid'
                        or invoice_line.invoice in skips)):
                quantity -= UoM.compute_qty(
                    invoice_line.unit or self.unit, invoice_line.quantity,
                    self.unit)
        return quantity

    def get_invoice_progress(self, name):
        progress = None
        quantity = self._invoice_remaining_quantity
        if quantity is not None and self.quantity:
            progress = round((self.quantity - quantity) / self.quantity, 4)
            progress = max(0., min(1., progress))
        return progress

    @property
    def _move_remaining_quantity(self):
        "Compute the remaining quantity to ship"
        pool = Pool()
        Uom = pool.get('product.uom')
        if self.type != 'line' or not self.product:
            return
        if self.product.type == 'service':
            return
        skips = set(self.moves_ignored)
        quantity = abs(self.quantity)
        if self.sale.shipment_method == 'invoice':
            invoices_ignored = set(self.sale.invoices_ignored)
            for invoice_line in self.invoice_lines:
                if invoice_line.type != 'line':
                    continue
                if invoice_line.invoice in invoices_ignored:
                    quantity -= Uom.compute_qty(
                        invoice_line.unit or self.unit, invoice_line.quantity,
                        self.unit)
        for move in self.moves:
            if move.state == 'done' or move in skips:
                quantity -= Uom.compute_qty(
                    move.unit, move.quantity, self.unit)
        return quantity

    def get_moves_exception(self, name):
        skips = set(self.moves_ignored)
        skips.update(self.moves_recreated)
        return any(
            m.state == 'cancelled' for m in self.moves if m not in skips)

    def get_moves_progress(self, name):
        progress = None
        quantity = self._move_remaining_quantity
        if quantity is not None and self.quantity:
            progress = round(
                (abs(self.quantity) - quantity) / abs(self.quantity), 4)
            progress = max(0., min(1., progress))
        return progress

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

    @fields.depends(
        'sale', 'taxes', '_parent_sale.party', '_parent_sale.invoice_party',
        methods=['compute_taxes', 'on_change_with_amount'])
    def on_change_sale(self):
        party = None
        if self.sale:
            party = self.sale.invoice_party or self.sale.party
        self.taxes = self.compute_taxes(party)
        self.amount = self.on_change_with_amount()

    @fields.depends(
        'product', 'unit', 'sale', 'taxes',
        '_parent_sale.party', '_parent_sale.invoice_party',
        methods=['compute_taxes', 'compute_unit_price',
            'on_change_with_amount'])
    def on_change_product(self):
        party = None
        if self.sale:
            party = self.sale.invoice_party or self.sale.party

        # Set taxes before unit_price to have taxes in context of sale price
        self.taxes = self.compute_taxes(party)

        if self.product:
            category = self.product.sale_uom.category
            if not self.unit or self.unit.category != category:
                self.unit = self.product.sale_uom

            self.unit_price = self.compute_unit_price()

        self.amount = self.on_change_with_amount()

    @cached_property
    def product_name(self):
        return self.product.rec_name if self.product else ''

    @fields.depends(
        'type', 'product',
        methods=['on_change_with_company', '_get_tax_rule_pattern'])
    def compute_taxes(self, party):
        pool = Pool()
        AccountConfiguration = pool.get('account.configuration')

        if self.type != 'line':
            return []

        company = self.on_change_with_company()
        taxes = set()
        pattern = self._get_tax_rule_pattern()
        taxes_used = []
        if self.product:
            taxes_used = self.product.customer_taxes_used
        elif company:
            account_config = AccountConfiguration(1)
            account = account_config.get_multivalue(
                'default_category_account_revenue', company=company.id)
            if account:
                taxes_used = account.taxes
        for tax in taxes_used:
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

    @fields.depends(
        'product', 'quantity', 'unit_price',
        methods=['_get_context_sale_price'])
    def compute_unit_price(self):
        pool = Pool()
        Product = pool.get('product.product')

        if not self.product:
            return self.unit_price

        with Transaction().set_context(
                self._get_context_sale_price()):
            return Product.get_sale_price(
                [self.product], abs(self.quantity or 0))[self.product.id]

    @fields.depends('product')
    def on_change_with_product_uom_category(self, name=None):
        return self.product.default_uom_category if self.product else None

    @fields.depends(methods=['compute_unit_price'])
    def on_change_quantity(self):
        self.unit_price = self.compute_unit_price()

    @fields.depends(methods=['on_change_quantity', 'on_change_with_amount'])
    def on_change_unit(self):
        self.on_change_quantity()
        self.amount = self.on_change_with_amount()

    @fields.depends(methods=['on_change_quantity', 'on_change_with_amount'])
    def on_change_taxes(self):
        self.on_change_quantity()
        self.amount = self.on_change_with_amount()

    @fields.depends('description')
    def on_change_with_summary(self, name=None):
        return firstline(self.description or '')

    @classmethod
    def search_summary(cls, name, clause):
        return [('description', *clause[1:])]

    @fields.depends(
        'type', 'quantity', 'unit_price',
        'sale', '_parent_sale.currency')
    def on_change_with_amount(self):
        if self.type == 'line':
            currency = self.sale.currency if self.sale else None
            amount = Decimal(str(self.quantity or 0)) * \
                (self.unit_price or Decimal(0))
            if currency:
                return currency.round(amount)
            return amount
        return Decimal(0)

    def get_amount(self, name):
        if self.type == 'line':
            return self.on_change_with_amount()
        elif self.type == 'subtotal':
            amount = Decimal(0)
            for line2 in self.sale.lines:
                if line2.type == 'line':
                    amount += line2.sale.currency.round(
                        Decimal(str(line2.quantity)) * line2.unit_price)
                elif line2.type == 'subtotal':
                    if self == line2:
                        break
                    amount = Decimal(0)
            return amount
        return Decimal(0)

    @fields.depends('sale', '_parent_sale.warehouse')
    def on_change_with_warehouse(self, name=None):
        return self.sale.warehouse if self.sale else None

    def get_from_location(self, name):
        if (self.quantity or 0) >= 0:
            if self.warehouse:
                return self.warehouse.output_location
        else:
            party = self.sale.shipment_party or self.sale.party
            return party.customer_location

    def get_to_location(self, name):
        if (self.quantity or 0) >= 0:
            party = self.sale.shipment_party or self.sale.party
            return party.customer_location
        else:
            if self.warehouse:
                return self.warehouse.input_location

    @classmethod
    def movable_types(cls):
        pool = Pool()
        Move = pool.get('stock.move')
        return Move.get_product_types()

    @fields.depends('product')
    def on_change_with_movable(self, name=None):
        if self.product:
            return self.product.type in self.movable_types()

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
        if self.product and self.quantity is not None and self.quantity > 0:
            date = self.sale.sale_date if self.sale else None
            shipping_date = self.product.compute_shipping_date(date=date)
            if shipping_date == datetime.date.max:
                shipping_date = None
            elif self.sale and self.sale.shipping_date:
                shipping_date = max(shipping_date, self.sale.shipping_date)
            return shipping_date

    @fields.depends('sale', '_parent_sale.currency')
    def on_change_with_currency(self, name=None):
        return self.sale.currency if self.sale else None

    @classmethod
    def get_sale_states(cls):
        pool = Pool()
        Sale = pool.get('sale.sale')
        return Sale.fields_get(['state'])['state']['selection']

    @fields.depends('sale', '_parent_sale.state')
    def on_change_with_sale_state(self, name=None):
        if self.sale:
            return self.sale.state

    @classmethod
    def search_sale_state(cls, name, clause):
        return [('sale.state', *clause[1:])]

    @fields.depends('sale', '_parent_sale.company')
    def on_change_with_company(self, name=None):
        return self.sale.company if self.sale else None

    @fields.depends('sale', '_parent_sale.party')
    def on_change_with_customer(self, name=None):
        return self.sale.party if self.sale else None

    @classmethod
    def search_customer(cls, name, clause):
        return [('sale.party' + clause[0][len(name):], *clause[1:])]

    @fields.depends('sale', '_parent_sale.sale_date')
    def on_change_with_sale_date(self, name=None):
        if self.sale:
            return self.sale.sale_date

    @classmethod
    def search_sale_date(cls, name, clause):
        return [('sale.sale_date', *clause[1:])]

    @classmethod
    def order_sale_date(cls, tables):
        return cls.sale.convert_order('sale.sale_date', tables, cls)

    def get_invoice_line(self):
        'Return a list of invoice lines for sale line'
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        AccountConfiguration = pool.get('account.configuration')
        account_config = AccountConfiguration(1)

        if self.type != 'line':
            return []

        invoice_line = InvoiceLine()
        invoice_line.type = self.type
        invoice_line.currency = self.currency
        invoice_line.company = self.company
        invoice_line.description = self.description
        invoice_line.note = self.note
        invoice_line.origin = self

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
        invoice_line.stock_moves = self._get_invoice_line_moves(
            invoice_line.quantity)
        return [invoice_line]

    def _get_invoice_line_quantity(self):
        'Return the quantity that should be invoiced'
        pool = Pool()
        Uom = pool.get('product.uom')

        if (self.sale.invoice_method in {'order', 'manual'}
                or not self.product
                or self.product.type == 'service'):
            return self.quantity
        elif self.sale.invoice_method == 'shipment':
            quantity = 0.0
            for move in self.moves:
                if move.state != 'done':
                    continue
                qty = Uom.compute_qty(move.unit, move.quantity, self.unit)
                # Test only against to_location
                # as it is what matters for sale
                dest_type = 'customer'
                if (move.to_location.type == dest_type
                        and move.from_location.type != dest_type):
                    quantity += qty
                elif (move.from_location.type == dest_type
                        and move.to_location.type != dest_type):
                    quantity -= qty
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
                if self.unit:
                    quantity += Uom.compute_qty(
                        invoice_line.unit or self.unit, invoice_line.quantity,
                        self.unit)
                else:
                    quantity += invoice_line.quantity
        return quantity

    def _get_invoice_line_moves(self, quantity):
        'Return the stock moves that should be invoiced'
        moves = []
        if self.sale.invoice_method in {'order', 'manual'}:
            if self.sale.shipment_method not in {'order', 'manual'}:
                moves.extend(self.moves)
        elif (self.sale.invoice_method == 'shipment'
                and samesign(self.quantity, quantity)):
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

        with Transaction().set_context(company=self.sale.company.id):
            today = Date.today()

        move = Move()
        move.quantity = quantity
        move.unit = self.unit
        move.product = self.product
        move.from_location = self.from_location
        move.to_location = self.to_location
        move.state = 'draft'
        move.company = self.sale.company
        if move.on_change_with_unit_price_required():
            move.unit_price = self.unit_price
            move.currency = self.sale.currency
        move.planned_date = max(self.planned_shipping_date or today, today)
        move.invoice_lines = self._get_move_invoice_lines(shipment_type)
        move.origin = self
        move.origin_planned_date = move.planned_date
        return move

    def _get_move_quantity(self, shipment_type):
        'Return the quantity that should be shipped'
        pool = Pool()
        Uom = pool.get('product.uom')

        if self.sale.shipment_method in {'order', 'manual'}:
            return abs(self.quantity)
        elif self.sale.shipment_method == 'invoice':
            quantity = 0.0
            for invoice_line in self.invoice_lines:
                if (invoice_line.invoice
                        and invoice_line.invoice.state == 'paid'):
                    quantity += Uom.compute_qty(
                        invoice_line.unit or self.unit, invoice_line.quantity,
                        self.unit)
            return quantity

    def _get_shipped_quantity(self, shipment_type):
        'Return the quantity already shipped'
        pool = Pool()
        Uom = pool.get('product.uom')

        quantity = 0
        skips = set(m for m in self.moves_recreated)
        for move in self.moves:
            if move not in skips:
                quantity += Uom.compute_qty(
                    move.unit, move.quantity, self.unit)
        return quantity

    def check_move_quantity(self):
        pool = Pool()
        Lang = pool.get('ir.lang')
        Warning = pool.get('res.user.warning')
        lang = Lang.get()
        move_type = 'in' if self.quantity >= 0 else 'return'
        quantity = (
            self._get_move_quantity(move_type)
            - self._get_shipped_quantity(move_type))
        if quantity < 0:
            warning_name = Warning.format(
                'check_move_quantity', [self])
            if Warning.check(warning_name):
                raise SaleMoveQuantity(warning_name, gettext(
                        'sale.msg_sale_line_move_quantity',
                        line=self.rec_name,
                        extra=lang.format_number_symbol(
                            -quantity, self.unit),
                        quantity=lang.format_number_symbol(
                            self.quantity, self.unit)))

    def _get_move_invoice_lines(self, shipment_type):
        'Return the invoice lines that should be shipped'
        invoice_lines = []
        if self.sale.shipment_method in {'order', 'manual'}:
            if self.sale.invoice_method in {'order', 'manual'}:
                invoice_lines.extend(self.invoice_lines)
        elif self.sale.shipment_method == 'invoice':
            for invoice_line in self.invoice_lines:
                if (invoice_line.invoice
                        and invoice_line.invoice.state == 'paid'
                        and samesign(self.quantity, invoice_line.quantity)):
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
                    move.unit, move.quantity, self.unit, round=False)
        if self.quantity < 0:
            moved_quantity *= -1
        invoiced_quantity = 0
        for invoice_line in self.invoice_lines:
            if (not invoice_line.invoice
                    or invoice_line.invoice.state != 'cancelled'):
                if self.unit:
                    invoiced_quantity += Uom.compute_qty(
                        invoice_line.unit or self.unit, invoice_line.quantity,
                        self.unit, round=False)
                else:
                    invoiced_quantity += invoice_line.quantity
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
        _, operator, value = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('sale.rec_name', *clause[1:]),
            ('product.rec_name', *clause[1:]),
            ]

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('/form//field[@name="note"]|/form//field[@name="description"]',
                'spell', Eval('_parent_sale', {}).get('party_lang'))]

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Sale = pool.get('sale.sale')
        sale_ids = filter(None, {v.get('sale') for v in vlist})
        for sale in Sale.browse(list(sale_ids)):
            if sale.state != 'draft':
                raise AccessError(
                    gettext('sale.msg_sale_line_create_draft',
                        sale=sale.rec_name))
        return super().create(vlist)

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
    line = fields.Many2One(
        'sale.line', "Sale Line", ondelete='CASCADE', required=True)
    tax = fields.Many2One(
        'account.tax', "Tax", ondelete='RESTRICT', required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('line_tax_unique', Unique(t, t.line, t.tax),
                'sale.msg_sale_line_tax_unique'),
            ]

    @classmethod
    def __register__(cls, module):
        # Migration from 7.0: rename to standard name
        backend.TableHandler.table_rename('sale_line_account_tax', cls._table)
        super().__register__(module)


class SaleLineIgnoredMove(ModelSQL):
    'Sale Line - Ignored Move'
    __name__ = 'sale.line-ignored-stock.move'
    sale_line = fields.Many2One(
        'sale.line', "Sale Line", ondelete='CASCADE', required=True)
    move = fields.Many2One(
        'stock.move', "Stock Move", ondelete='RESTRICT', required=True,
        domain=[
            ('origin.id', '=', Eval('sale_line', -1), 'sale.line'),
            ('state', '=', 'cancelled'),
            ])

    @classmethod
    def __register__(cls, module):
        # Migration from 7.0: rename to standard name
        backend.TableHandler.table_rename(
            'sale_line_moves_ignored_rel', cls._table)
        super().__register__(module)


class SaleLineRecreatedMove(ModelSQL):
    'Sale Line - Recreated Move'
    __name__ = 'sale.line-recreated-stock.move'
    sale_line = fields.Many2One(
        'sale.line', "Sale Line", ondelete='CASCADE', required=True)
    move = fields.Many2One(
        'stock.move', "Stock Move", ondelete='RESTRICT', required=True,
        domain=[
            ('origin.id', '=', Eval('sale_line', -1), 'sale.line'),
            ('state', '=', 'cancelled'),
            ])

    @classmethod
    def __register__(cls, module):
        # Migration from 7.0: rename to standard name
        backend.TableHandler.table_rename(
            'sale_line_moves_recreated_rel', cls._table)
        super().__register__(module)


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
        company = header.get('company')
        with Transaction().set_context(
                company=company.id if company else None):
            context['today'] = Date.today()
        return context


class HandleShipmentExceptionAsk(ModelView):
    'Handle Shipment Exception'
    __name__ = 'sale.handle.shipment.exception.ask'
    recreate_moves = fields.Many2Many(
        'stock.move', None, None, "Stock Moves to Recreate",
        domain=[
            ('id', 'in', Eval('domain_moves', [])),
            ('id', 'not in', Eval('ignore_moves', [])),
            ],
        help="The selected cancelled stock moves will be recreated.")
    ignore_moves = fields.Many2Many(
        'stock.move', None, None, "Stock Moves to Ignore",
        domain=[
            ('id', 'in', Eval('domain_moves', [])),
            ('id', 'not in', Eval('recreate_moves', [])),
            ],
        help="The selected cancelled stock moves will be ignored.")
    domain_moves = fields.Many2Many(
        'stock.move', None, None, 'Domain Stock Moves')


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
                elif move in self.ask.ignore_moves:
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
        'account.invoice', None, None, "Invoices to Recreate",
        domain=[
            ('id', 'in', Eval('domain_invoices', [])),
            ('id', 'not in', Eval('ignore_invoices', []))
            ],
        help="The selected cancelled invoices will be recreated.")
    ignore_invoices = fields.Many2Many(
        'account.invoice', None, None, "Invoices to Ignore",
        domain=[
            ('id', 'in', Eval('domain_invoices', [])),
            ('id', 'not in', Eval('recreate_invoices', []))
            ],
        help="The selected cancelled invoices will be ignored.")
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
            'domain_invoices': invoices,
            }

    def transition_handle(self):
        invoices_ignored = []
        invoices_recreated = []
        for invoice in self.ask.domain_invoices:
            if invoice in self.ask.recreate_invoices:
                invoices_recreated.append(invoice.id)
            elif invoice in self.ask.ignore_invoices:
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
        return_sales = self.model.copy(sales, default={
                'origin': lambda data: (
                    '%s,%s' % (self.model.__name__, data['id'])),
                'lines.quantity': lambda data: (
                    data['quantity'] * -1 if data['type'] == 'line'
                    else data['quantity']),
                })

        data = {'res_id': [s.id for s in return_sales]}
        if len(return_sales) == 1:
            action['views'].reverse()
        return action, data


class ModifyHeaderStateView(StateView):
    def get_view(self, wizard, state_name):
        with Transaction().set_context(modify_header=True):
            return super(ModifyHeaderStateView, self).get_view(
                wizard, state_name)

    def get_defaults(self, wizard, state_name, fields):
        return {}


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

    def value_start(self, fields):
        sale = self.get_sale()
        values = {}
        for fieldname in fields:
            value = getattr(sale, fieldname)
            if isinstance(value, Model):
                if getattr(sale.__class__, fieldname)._type == 'reference':
                    value = str(value)
                else:
                    value = value.id
            elif (value and isinstance(value, (list, tuple))
                    and isinstance(value[0], Model)):
                value = [r.id for r in value]
            values[fieldname] = value

        # Mimic an empty sale in draft state to get the fields' states right
        values['lines'] = []
        return values

    def transition_modify(self):
        pool = Pool()
        Line = pool.get('sale.line')

        sale = self.get_sale()
        values = self.start._save_values()
        self.model.write([sale], values)
        self.model.log([sale], 'write', ','.join(sorted(values.keys())))

        # Call on_change after the save to ensure parent sale
        # has the modified values
        for line in sale.lines:
            line.on_change_product()
        Line.save(sale.lines)

        return 'end'
