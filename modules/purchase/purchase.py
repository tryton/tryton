# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import math
from collections import defaultdict
from decimal import Decimal
from itertools import chain, groupby

from sql import Literal, Null
from sql.aggregate import Count
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
from trytond.tools import cached_property, firstline
from trytond.transaction import Transaction
from trytond.wizard import (
    Button, StateAction, StateTransition, StateView, Wizard)

from .exceptions import (
    PartyLocationError, PurchaseMoveQuantity, PurchaseQuotationError)


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


class Purchase(
        Workflow, ModelSQL, ModelView, TaxableMixin,
        AttachmentCopyMixin, NoteCopyMixin):
    'Purchase'
    __name__ = 'purchase.purchase'
    _rec_name = 'number'

    _states = {
        'readonly': Eval('state') != 'draft',
        }

    company = fields.Many2One(
        'company.company', "Company", required=True,
        states={
            'readonly': (
                (Eval('state') != 'draft')
                | Eval('lines', [0])
                | Eval('party', True)
                | Eval('invoice_party', True)),
            })
    number = fields.Char("Number", readonly=True)
    reference = fields.Char("Reference")
    description = fields.Char('Description', size=None, states=_states)
    purchase_date = fields.Date('Purchase Date',
        states={
            'readonly': ~Eval('state').in_(['draft', 'quotation']),
            'required': ~Eval('state').in_(
                ['draft', 'quotation', 'cancelled']),
            })
    payment_term = fields.Many2One(
        'account.invoice.payment_term', "Payment Term", ondelete='RESTRICT',
        states={
            'readonly': ~Eval('state').in_(['draft', 'quotation']),
            })
    party = fields.Many2One('party.party', 'Party', required=True,
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
    warehouse = fields.Many2One('stock.location', 'Warehouse',
        domain=[('type', '=', 'warehouse')], states=_states)
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states={
            'readonly': ((Eval('state') != 'draft')
                | (Eval('lines', [0]) & Eval('currency'))),
            })
    lines = fields.One2Many(
        'purchase.line', 'purchase', "Lines",
        states={
            'readonly': (
                (Eval('state') != 'draft')
                | ~Eval('company')
                | ~Eval('currency')),
            })
    line_lines = fields.One2Many(
        'purchase.line', 'purchase', "Line - Lines", readonly=True,
        filter=[
            ('type', '=', 'line'),
            ])
    comment = fields.Text('Comment')
    untaxed_amount = fields.Function(Monetary(
            "Untaxed", currency='currency', digits='currency'),
        'get_amount')
    untaxed_amount_cache = Monetary(
        "Untaxed Cache", currency='currency', digits='currency')
    tax_amount = fields.Function(Monetary(
            "Tax", currency='currency', digits='currency'),
        'get_amount')
    tax_amount_cache = Monetary(
        "Tax Cache", currency='currency', digits='currency')
    total_amount = fields.Function(Monetary(
            "Total", currency='currency', digits='currency'),
        'get_amount')
    total_amount_cache = Monetary(
        "Total Cache", currency='currency', digits='currency')
    invoice_method = fields.Selection([
            ('manual', 'Manual'),
            ('order', 'Based On Order'),
            ('shipment', 'Based On Shipment'),
            ], 'Invoice Method', required=True, states=_states)
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
        'purchase.purchase-ignored-account.invoice',
        'purchase', 'invoice', "Ignored Invoices",
        domain=[
            ('id', 'in', Eval('invoices', [])),
            ('state', '=', 'cancelled'),
            ],
        states={
            'invisible': ~Eval('invoices_ignored', []),
            })
    invoices_recreated = fields.Many2Many(
            'purchase.purchase-recreated-account.invoice',
            'purchase', 'invoice', 'Recreated Invoices', readonly=True)
    origin = fields.Reference(
        "Origin", selection='get_origin',
        states={
            'readonly': Eval('state') != 'draft',
            })
    delivery_date = fields.Date(
        "Delivery Date",
        states={
            'readonly': Eval('state').in_([
                    'processing', 'done', 'cancelled']),
            },
        help="The default delivery date for each line.")
    shipment_state = fields.Selection([
            ('none', 'None'),
            ('waiting', 'Waiting'),
            ('partially shipped', 'Partially Shipped'),
            ('received', 'Received'),
            ('exception', 'Exception'),
            ], 'Shipment State', readonly=True, required=True, sort=False)
    shipments = fields.Function(fields.Many2Many(
            'stock.shipment.in', None, None, "Shipments"),
        'get_shipments', searcher='search_shipments')
    shipment_returns = fields.Function(fields.Many2Many(
            'stock.shipment.in.return', None, None, "Shipment Returns"),
        'get_shipment_returns', searcher='search_shipment_returns')
    moves = fields.Function(
        fields.Many2Many('stock.move', None, None, "Stock Moves"),
        'get_moves', searcher='search_moves')

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

    del _states

    @classmethod
    def __setup__(cls):
        cls.number.search_unaccented = False
        cls.reference.search_unaccented = False
        super(Purchase, cls).__setup__()
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
            ('purchase_date', 'DESC NULLS FIRST'),
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
                    'icon': If(Eval('state') == 'cancelled', 'tryton-undo',
                        'tryton-back'),
                    'depends': ['state'],
                    },
                'quote': {
                    'invisible': Eval('state') != 'draft',
                    'readonly': ~Eval('lines', Eval('untaxed_amount', 0)),
                    'depends': ['state'],
                    },
                'confirm': {
                    'pre_validate': [
                        If(~Eval('invoice_address'),
                            ('invoice_address', '!=', None),
                            ()),
                        ],
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
        cls._states_cached = ['confirmed', 'done', 'cancelled']

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        sql_table = cls.__table__()

        super(Purchase, cls).__register__(module_name)

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
    def default_warehouse(cls):
        Location = Pool().get('stock.location')
        return Location.get_default_warehouse()

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @fields.depends('company')
    def on_change_company(self):
        self.invoice_method = self.default_invoice_method(
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
        Configuration = Pool().get('purchase.configuration')
        configuration = Configuration(1)
        return configuration.get_multivalue(
            'purchase_invoice_method', **pattern)

    @staticmethod
    def default_invoice_state():
        return 'none'

    @staticmethod
    def default_shipment_state():
        return 'none'

    @fields.depends(
        'company', 'party', 'invoice_party', 'payment_term', 'lines')
    def on_change_party(self):
        cursor = Transaction().connection.cursor()
        table = self.__table__()
        if not self.invoice_party:
            self.invoice_address = None
        self.invoice_method = self.default_invoice_method(
            company=self.company.id if self.company else None)
        if not self.lines:
            self.currency = self.default_currency(
                company=self.company.id if self.company else None)
        if self.party:
            if not self.invoice_party:
                self.invoice_address = self.party.address_get(type='invoice')

            if not self.lines:
                invoice_party = (
                    self.invoice_party.id if self.invoice_party else None)
                subquery = table.select(
                    table.currency,
                    table.payment_term,
                    table.invoice_method,
                    where=(table.party == self.party.id)
                    & (table.invoice_party == invoice_party),
                    order_by=table.id.desc,
                    limit=10)
                cursor.execute(*subquery.select(
                        subquery.currency,
                        subquery.payment_term,
                        subquery.invoice_method,
                        group_by=[
                            subquery.currency,
                            subquery.payment_term,
                            subquery.invoice_method,
                            ],
                        order_by=Count(Literal(1)).desc))
                row = cursor.fetchone()
                if row:
                    self.currency, self.payment_term, self.invoice_method = row
                if self.party.supplier_currency:
                    self.currency = self.party.supplier_currency
            if self.party.supplier_payment_term:
                self.payment_term = self.party.supplier_payment_term
        else:
            self.payment_term = None

    @fields.depends('party', 'invoice_party')
    def on_change_invoice_party(self):
        if self.invoice_party:
            self.invoice_address = self.invoice_party.address_get(
                type='invoice')
        elif self.party:
            self.invoice_address = self.party.address_get(type='invoice')

    @fields.depends('party')
    def on_change_with_party_lang(self, name=None):
        Config = Pool().get('ir.configuration')
        if self.party:
            if self.party.lang:
                return self.party.lang.code
        return Config.get_language()

    @fields.depends('party', 'company')
    def _get_tax_context(self):
        context = {}
        if self.party and self.party.lang:
            context['language'] = self.party.lang.code
        if self.company:
            context['company'] = self.company.id
        return context

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
        # In case we're called from an on_change we have to use some sensible
        # defaults
        for line in self.lines:
            if getattr(line, 'type', None) != 'line':
                continue
            taxable_lines.append((
                    getattr(line, 'taxes', None) or [],
                    getattr(line, 'unit_price', None) or Decimal(0),
                    getattr(line, 'quantity', None) or 0,
                    None,
                    ))
        return taxable_lines

    @fields.depends(methods=['_get_taxes'])
    def get_tax_amount(self):
        taxes = iter(self._get_taxes().values())
        return sum((tax['amount'] for tax in taxes), Decimal(0))

    @classmethod
    def get_amount(cls, purchases, names):
        untaxed_amount = {}
        tax_amount = {}
        total_amount = {}

        if {'tax_amount', 'total_amount'} & set(names):
            compute_taxes = True
        else:
            compute_taxes = False
        # Browse separately not cached to limit number of lines read
        cached, not_cached = [], []
        for purchase in purchases:
            if purchase.state in cls._states_cached:
                cached.append(purchase)
            else:
                not_cached.append(purchase)
        for purchase in chain(cached, cls.browse(not_cached)):
            if (purchase.state in cls._states_cached
                    and purchase.untaxed_amount_cache is not None
                    and purchase.tax_amount_cache is not None
                    and purchase.total_amount_cache is not None):
                untaxed_amount[purchase.id] = purchase.untaxed_amount_cache
                if compute_taxes:
                    tax_amount[purchase.id] = purchase.tax_amount_cache
                    total_amount[purchase.id] = purchase.total_amount_cache
            else:
                untaxed_amount[purchase.id] = sum(
                    (line.amount for line in purchase.line_lines
                        if line.amount is not None),
                    Decimal(0))
                if compute_taxes:
                    tax_amount[purchase.id] = purchase.get_tax_amount()
                    total_amount[purchase.id] = (
                        untaxed_amount[purchase.id] + tax_amount[purchase.id])

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
        Return the invoice state for the purchase.
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

    get_shipments = get_shipments_returns('stock.shipment.in')
    get_shipment_returns = get_shipments_returns('stock.shipment.in.return')

    search_shipments = search_shipments_returns('stock.shipment.in')
    search_shipment_returns = search_shipments_returns(
        'stock.shipment.in.return')

    def get_shipment_state(self):
        '''
        Return the shipment state for the purchase.
        '''
        if any(l.moves_exception for l in self.line_lines):
            return 'exception'
        elif any(m.state != 'cancelled' for m in self.moves):
            if all(l.moves_progress >= 1 for l in self.line_lines
                    if l.moves_progress is not None):
                return 'received'
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
        "Return list of Model names for origin Reference"
        return ['purchase.purchase']

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
        if self.warehouse and self.warehouse.address:
            return self.warehouse.address.full_address
        return ''

    @property
    def full_number(self):
        return self.number

    def get_rec_name(self, name):
        items = []
        if self.number:
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
            'stock.shipment.in.return',
            'account.invoice',
            }

    @classmethod
    def copy(cls, purchases, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('number', None)
        default.setdefault('invoice_state', 'none')
        default.setdefault('invoices_ignored', None)
        default.setdefault('shipment_state', 'none')
        default.setdefault('purchase_date', None)
        default.setdefault('quoted_by')
        default.setdefault('confirmed_by')
        default.setdefault('untaxed_amount_cache')
        default.setdefault('tax_amount_cache')
        default.setdefault('total_amount_cache')
        return super(Purchase, cls).copy(purchases, default=default)

    def check_for_quotation(self):
        for line in self.line_lines:
            if (not line.to_location
                    and line.product
                    and line.movable):
                raise PurchaseQuotationError(
                    gettext('purchase.msg_warehouse_required_for_quotation',
                        purchase=self.rec_name))

    @classmethod
    def set_number(cls, purchases):
        '''
        Fill the number field with the purchase sequence
        '''
        pool = Pool()
        Config = pool.get('purchase.configuration')

        config = Config(1)
        for company, c_purchases in groupby(
                purchases, key=lambda p: p.company):
            c_purchases = [p for p in c_purchases if not p.number]
            if c_purchases:
                sequence = config.get_multivalue(
                    'purchase_sequence', company=company.id)
                for purchase, number in zip(
                        c_purchases, sequence.get_many(len(c_purchases))):
                    purchase.number = number
        cls.save(purchases)

    @classmethod
    def set_purchase_date(cls, purchases):
        Date = Pool().get('ir.date')
        for company, purchases in groupby(purchases, key=lambda p: p.company):
            with Transaction().set_context(company=company.id):
                today = Date.today()
            cls.write([p for p in purchases if not p.purchase_date], {
                    'purchase_date': today,
                    })

    @classmethod
    def store_cache(cls, purchases):
        purchases = list(purchases)
        cls.write(purchases, {
                'untaxed_amount_cache': None,
                'tax_amount_cache': None,
                'total_amount_cache': None,
                })
        for purchase in purchases:
            purchase.untaxed_amount_cache = purchase.untaxed_amount
            purchase.tax_amount_cache = purchase.tax_amount
            purchase.total_amount_cache = purchase.total_amount
        cls.save(purchases)

    def _get_invoice_purchase(self):
        'Return invoice'
        pool = Pool()
        Invoice = pool.get('account.invoice')
        party = self.invoice_party or self.party
        invoice = Invoice(
            company=self.company,
            type='in',
            party=party,
            invoice_address=self.invoice_address,
            currency=self.currency,
            account=party.account_payable_used,
            payment_term=self.payment_term,
            )
        invoice.set_journal()
        return invoice

    def create_invoice(self):
        'Create an invoice for the purchase and return it'
        context = Transaction().context
        if (self.invoice_method == 'manual'
                and not context.get('_purchase_manual_invoice', False)):
            return

        invoice_lines = []
        for line in self.lines:
            invoice_lines.append(line.get_invoice_line())
        invoice_lines = list(chain(*invoice_lines))
        if not invoice_lines:
            return

        invoice = self._get_invoice_purchase()
        if getattr(invoice, 'lines', None):
            invoice_lines = list(invoice.lines) + invoice_lines
        invoice.lines = invoice_lines
        return invoice

    def create_move(self, move_type):
        '''
        Create move for each purchase lines
        '''
        pool = Pool()
        Move = pool.get('stock.move')

        moves = []
        for line in self.line_lines:
            move = line.get_move(move_type)
            if move:
                moves.append(move)
        Move.save(moves)
        return moves

    @property
    def return_from_location(self):
        if self.warehouse:
            return (self.warehouse.supplier_return_location
                or self.warehouse.storage_location)

    def _get_return_shipment(self):
        ShipmentInReturn = Pool().get('stock.shipment.in.return')
        return ShipmentInReturn(
            company=self.company,
            from_location=self.return_from_location,
            to_location=self.party.supplier_location,
            supplier=self.party,
            delivery_address=self.party.address_get(type='delivery'),
            )

    def create_return_shipment(self, return_moves):
        '''
        Create return shipment and return the shipment id
        '''
        return_shipment = self._get_return_shipment()
        return_shipment.moves = return_moves
        return return_shipment

    def is_done(self):
        return ((self.invoice_state == 'paid'
                or (self.invoice_state == 'none'
                    and all(
                        l.invoice_progress >= 1
                        for l in self.line_lines
                        if l.invoice_progress is not None)))
            and (self.shipment_state == 'received'
                or (self.shipment_state == 'none'
                    and all(
                        l.moves_progress >= 1
                        for l in self.line_lines
                        if l.moves_progress is not None))))

    @classmethod
    def delete(cls, purchases):
        # Cancel before delete
        cls.cancel(purchases)
        for purchase in purchases:
            if purchase.state != 'cancelled':
                raise AccessError(
                    gettext('purchase.msg_purchase_delete_cancel',
                        purchase=purchase.rec_name))
        super(Purchase, cls).delete(purchases)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, purchases):
        cls.store_cache(purchases)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    @reset_employee('quoted_by', 'confirmed_by')
    def draft(cls, purchases):
        cls.write(purchases, {
                'tax_amount_cache': None,
                'untaxed_amount_cache': None,
                'total_amount_cache': None,
                })

    @classmethod
    @ModelView.button
    @Workflow.transition('quotation')
    @set_employee('quoted_by')
    def quote(cls, purchases):
        for purchase in purchases:
            purchase.check_for_quotation()
        cls.set_number(purchases)

    @property
    def process_after(self):
        pool = Pool()
        Configuration = pool.get('purchase.configuration')
        config = Configuration(1)
        return config.purchase_process_after

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    @set_employee('confirmed_by')
    def confirm(cls, purchases):
        pool = Pool()
        Line = pool.get('purchase.line')
        transaction = Transaction()
        context = transaction.context
        cls.set_purchase_date(purchases)

        cls.write(purchases, {'state': 'confirmed'})
        lines = list(sum((p.lines for p in purchases), ()))
        Line._validate(lines, ['unit_price'])

        cls.store_cache(purchases)
        for process_after, sub_purchases in groupby(
                purchases, lambda p: p.process_after):
            with transaction.set_context(
                    queue_scheduled_at=process_after,
                    queue_batch=context.get('queue_batch', True)):
                cls.__queue__.process(sub_purchases)

    @classmethod
    @Workflow.transition('processing')
    def proceed(cls, purchases):
        pass

    @classmethod
    @Workflow.transition('done')
    def do(cls, purchases):
        pass

    @classmethod
    @ModelView.button_action('purchase.wizard_invoice_handle_exception')
    def handle_invoice_exception(cls, purchases):
        pass

    @classmethod
    @ModelView.button_action('purchase.wizard_shipment_handle_exception')
    def handle_shipment_exception(cls, purchases):
        pass

    @classmethod
    @ModelView.button
    def process(cls, purchases):
        states = {'confirmed', 'processing', 'done'}
        purchases = [p for p in purchases if p.state in states]
        cls.lock(purchases)
        cls._process_invoice(purchases)
        cls._process_shipment(purchases)
        cls._process_invoice_shipment_states(purchases)
        cls._process_state(purchases)

    @classmethod
    def _process_invoice(cls, purchases):
        invoices = {}
        for purchase in purchases:
            invoice = purchase.create_invoice()
            if invoice:
                invoices[purchase] = invoice

        cls._save_invoice(invoices)

    @classmethod
    def _save_invoice(cls, invoices):
        pool = Pool()
        Invoice = pool.get('account.invoice')

        Invoice.save(invoices.values())
        for purchase, invoice in invoices.items():
            purchase.copy_resources_to(invoice)

    @classmethod
    def _process_shipment(cls, purchases):
        pool = Pool()
        Move = pool.get('stock.move')
        ShipmentInReturn = pool.get('stock.shipment.in.return')

        moves, shipments_return = [], {}
        for purchase in purchases:
            moves.extend(purchase.create_move('in'))
            return_moves = purchase.create_move('return')
            if return_moves:
                shipments_return[purchase] = purchase.create_return_shipment(
                    return_moves)

        Move.save(moves)

        ShipmentInReturn.save(shipments_return.values())
        ShipmentInReturn.wait(shipments_return.values())
        for purchase, shipment in shipments_return.items():
            purchase.copy_resources_to(shipment)

    @classmethod
    def _process_invoice_shipment_states(cls, purchases):
        pool = Pool()
        Line = pool.get('purchase.line')
        lines = []
        invoice_states, shipment_states = defaultdict(list), defaultdict(list)
        for purchase in purchases:
            invoice_state = purchase.get_invoice_state()
            if purchase.invoice_state != invoice_state:
                invoice_states[invoice_state].append(purchase)
            shipment_state = purchase.get_shipment_state()
            if purchase.shipment_state != shipment_state:
                shipment_states[shipment_state].append(purchase)

            for line in purchase.line_lines:
                line.set_actual_quantity()
                lines.append(line)

        for invoice_state, purchases in invoice_states.items():
            cls.write(purchases, {'invoice_state': invoice_state})
            cls.log(purchases, 'transition', f'invoice_state:{invoice_state}')
        for shipment_state, purchases in shipment_states.items():
            cls.write(purchases, {'shipment_state': shipment_state})
            cls.log(
                purchases, 'transition', f'shipment_state:{shipment_state}')
        Line.save(lines)

    @classmethod
    def _process_state(cls, purchases):
        process, done = [], []
        for purchase in purchases:
            if purchase.is_done():
                if purchase.state != 'done':
                    if purchase.state == 'confirmed':
                        process.append(purchase)
                    done.append(purchase)
            elif purchase.state != 'processing':
                process.append(purchase)
        if process:
            cls.proceed(process)
        if done:
            cls.do(done)

    @classmethod
    @ModelView.button
    def manual_invoice(cls, purchases):
        purchases = [p for p in purchases if p.invoice_method == 'manual']
        with Transaction().set_context(_purchase_manual_invoice=True):
            cls.process(purchases)

    @classmethod
    @ModelView.button_action('purchase.wizard_modify_header')
    def modify_header(cls, purchases):
        pass


class PurchaseIgnoredInvoice(ModelSQL):
    'Purchase - Ignored Invoice'
    __name__ = 'purchase.purchase-ignored-account.invoice'
    purchase = fields.Many2One(
        'purchase.purchase', "Purchase", ondelete='CASCADE', required=True)
    invoice = fields.Many2One(
        'account.invoice', "Invoice", ondelete='RESTRICT', required=True,
        domain=[
            ('purchases', '=', Eval('purchase', -1)),
            ('state', '=', 'cancelled'),
            ])

    @classmethod
    def __register__(cls, module):
        # Migration from 7.0: rename to standard name
        backend.TableHandler.table_rename(
            'purchase_invoice_ignored_rel', cls._table)
        super().__register__(module)


class PurchaseRecreatedInvoice(ModelSQL):
    'Purchase - Recreated Invoice'
    __name__ = 'purchase.purchase-recreated-account.invoice'
    purchase = fields.Many2One(
        'purchase.purchase', "Purchase", ondelete='CASCADE', required=True)
    invoice = fields.Many2One(
        'account.invoice', "Invoice", ondelete='RESTRICT', required=True,
        domain=[
            ('purchases', '=', Eval('purchase', -1)),
            ('state', '=', 'cancelled'),
            ])

    @classmethod
    def __register__(cls, module):
        # Migration from 7.0: rename to standard name
        backend.TableHandler.table_rename(
            'purchase_invoice_recreated_rel', cls._table)
        super().__register__(module)


class Line(sequence_ordered(), ModelSQL, ModelView):
    'Purchase Line'
    __name__ = 'purchase.line'
    purchase = fields.Many2One(
        'purchase.purchase', "Purchase", ondelete='CASCADE', required=True,
        states={
            'readonly': ((Eval('purchase_state') != 'draft')
                & Bool(Eval('purchase'))),
            })
    type = fields.Selection([
        ('line', 'Line'),
        ('subtotal', 'Subtotal'),
        ('title', 'Title'),
        ('comment', 'Comment'),
        ], "Type", required=True,
        states={
            'readonly': Eval('purchase_state') != 'draft',
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
            'readonly': Eval('purchase_state') != 'draft',
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
    unit = fields.Many2One('product.uom', 'Unit',
        ondelete='RESTRICT',
        states={
            'required': Bool(Eval('product')),
            'invisible': Eval('type') != 'line',
            'readonly': Eval('purchase_state') != 'draft',
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
            If(Eval('purchase_state').in_(['draft', 'quotation'])
                & ~(Eval('quantity', 0) < 0),
                ('purchasable', '=', True),
                ()),
            If(Eval('type') != 'line',
                ('id', '=', None),
                ()),
            ],
        states={
            'invisible': Eval('type') != 'line',
            'readonly': Eval('purchase_state') != 'draft',
            'required': Bool(Eval('product_supplier')),
            },
        context={
            'company': Eval('company', None),
            },
        search_context={
            'locations': If(Bool(Eval('warehouse')),
                [Eval('warehouse', -1)], []),
            'stock_date_end': Eval('purchase_date', None),
            'stock_skip_warehouse': True,
            'currency': Eval('currency', -1),
            'supplier': Eval('supplier', -1),
            'purchase_date': Eval('purchase_date', None),
            'uom': Eval('unit'),
            'taxes': Eval('taxes', []),
            'quantity': Eval('quantity'),
            },
        depends={
            'company', 'warehouse', 'purchase_date', 'currency', 'supplier'})
    product_supplier = fields.Many2One(
        'purchase.product_supplier', "Supplier's Product",
        ondelete='RESTRICT',
        domain=[
            If(Eval('type') != 'line',
                ('id', '=', None),
                ()),
            If(Bool(Eval('product')),
                ['OR',
                    [
                        ('template.products', '=', Eval('product')),
                        ('product', '=', None),
                        ],
                    ('product', '=', Eval('product')),
                    ],
                []),
            ('party', '=', Eval('supplier', -1)),
            ],
        states={
            'invisible': Eval('type') != 'line',
            'readonly': Eval('purchase_state') != 'draft',
            })
    product_uom_category = fields.Function(
        fields.Many2One(
            'product.uom.category', "Product UoM Category",
            help="The category of Unit of Measure for the product."),
        'on_change_with_product_uom_category')
    unit_price = Monetary(
        "Unit Price", currency='currency', digits=price_digits,
        domain=[
            If(Eval('type') != 'line',
                ('unit_price', '=', None),
                ()),
            ],
        states={
            'invisible': Eval('type') != 'line',
            'required': (
                (Eval('type') == 'line')
                & Eval('purchase_state').in_(
                    ['confirmed', 'processing', 'done'])),
            'readonly': Eval('purchase_state') != 'draft',
            })
    amount = fields.Function(Monetary(
            "Amount", currency='currency', digits='currency',
            states={
                'invisible': ~Eval('type').in_(['line', 'subtotal']),
                }),
        'get_amount')
    description = fields.Text('Description', size=None,
        states={
            'readonly': Eval('purchase_state') != 'draft',
            })
    summary = fields.Function(
        fields.Char('Summary'), 'on_change_with_summary',
        searcher='search_summary')
    note = fields.Text('Note')
    taxes = fields.Many2Many('purchase.line-account.tax',
        'line', 'tax', 'Taxes',
        order=[('tax.sequence', 'ASC'), ('tax.id', 'ASC')],
        domain=[
            ('parent', '=', None),
            ['OR',
                ('group', '=', None),
                ('group.kind', 'in', ['purchase', 'both']),
                ],
            ('company', '=', Eval('company', -1)),
            If(Eval('type') != 'line',
                ('id', '=', None),
                ()),
            ],
        states={
            'invisible': Eval('type') != 'line',
            'readonly': Eval('purchase_state') != 'draft',
            })
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
        'purchase.line-ignored-stock.move', 'purchase_line', 'move',
        "Ignored Stock Moves",
        domain=[
            ('id', 'in', Eval('moves', [])),
            ('state', '=', 'cancelled'),
            ],
        states={
            'invisible': ~Eval('moves_ignored'),
            })
    moves_recreated = fields.Many2Many(
        'purchase.line-recreated-stock.move', 'purchase_line', 'move',
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

    delivery_date = fields.Function(fields.Date('Delivery Date',
            states={
                'invisible': Eval('type') != 'line',
                'readonly': (Eval('purchase_state').in_(
                        ['processing', 'done', 'cancelled'])
                    | ~Eval('delivery_date_edit', False)),
                }),
        'on_change_with_delivery_date', setter='set_delivery_date')
    delivery_date_edit = fields.Boolean(
        "Edit Delivery Date",
        domain=[
            If(Eval('type') != 'line',
                ('delivery_date_edit', '=', False),
                ()),
            ],
        states={
            'invisible': (
                (Eval('type') != 'line')
                | Eval('purchase_state').in_(
                    ['processing', 'done', 'cancelled'])),
            'readonly': Eval('purchase_state').in_(
                ['processing', 'done', 'cancelled']),
            },
        help="Check to edit the delivery date.")
    delivery_date_store = fields.Date(
        "Delivery Date", readonly=True,
        domain=[
            If(Eval('type') != 'line',
                ('delivery_date_store', '=', None),
                ()),
            ],
        states={
            'invisible': Eval('type') != 'line',
            })
    purchase_state = fields.Function(
        fields.Selection('get_purchase_states', 'Purchase State'),
        'on_change_with_purchase_state', searcher='search_purchase_state')
    company = fields.Function(
        fields.Many2One('company.company', "Company"),
        'on_change_with_company')
    supplier = fields.Function(
        fields.Many2One(
            'party.party', "Supplier",
            context={
                'company': Eval('company', -1),
                }),
        'on_change_with_supplier', searcher='search_supplier')
    purchase_date = fields.Function(
        fields.Date("Purchase Date"),
        'on_change_with_purchase_date', searcher='search_purchase_date')
    currency = fields.Function(
        fields.Many2One('currency.currency', 'Currency'),
        'on_change_with_currency')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('purchase')
        cls._order.insert(0, ('purchase.purchase_date', 'DESC NULLS FIRST'))
        cls._order.insert(1, ('purchase.id', 'DESC'))

    @staticmethod
    def default_type():
        return 'line'

    @fields.depends('type', 'taxes')
    def on_change_type(self):
        if self.type != 'line':
            self.product = None
            self.product_supplier = None
            self.unit = None
            self.taxes = None

    @classmethod
    def default_delivery_date_edit(cls):
        return False

    @property
    def _invoice_remaining_quantity(self):
        "Compute the remaining quantity to be paid"
        pool = Pool()
        UoM = pool.get('product.uom')
        if self.type != 'line':
            return
        skips = set(self.purchase.invoices_ignored)
        quantity = self.quantity
        if self.purchase.invoice_method == 'shipment':
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
        "Compute the remaining quantity to receive"
        pool = Pool()
        Uom = pool.get('product.uom')
        if self.type != 'line' or not self.product:
            return
        if self.product.type == 'service':
            return
        skips = set(self.moves_ignored)
        quantity = abs(self.quantity)
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

    def _get_tax_rule_pattern(self):
        '''
        Get tax rule pattern
        '''
        return {}

    @fields.depends(
        'purchase', '_parent_purchase.currency', '_parent_purchase.party',
        '_parent_purchase.purchase_date', 'company',
        'unit', 'product', 'product_supplier', 'taxes')
    def _get_context_purchase_price(self):
        context = {}
        if self.purchase:
            if self.purchase.currency:
                context['currency'] = self.purchase.currency.id
            if self.purchase.party:
                context['supplier'] = self.purchase.party.id
            context['purchase_date'] = self.purchase.purchase_date
        if self.company:
            context['company'] = self.company.id
        if self.unit:
            context['uom'] = self.unit.id
        elif self.product:
            context['uom'] = self.product.purchase_uom.id
        if self.product_supplier:
            context['product_supplier'] = self.product_supplier.id
        context['taxes'] = [t.id for t in self.taxes or []]
        return context

    @fields.depends('purchase', 'company', '_parent_purchase.party',)
    def _get_product_supplier_pattern(self):
        return {
            'party': (
                self.purchase.party.id
                if self.purchase and self.purchase.party else -1),
            'company': (self.company.id if self.company else -1),
            }

    @fields.depends(
        'purchase', 'taxes',
        '_parent_purchase.party', '_parent_purchase.invoice_party',
        methods=['compute_taxes', 'on_change_with_amount'])
    def on_change_purchase(self):
        party = None
        if self.purchase:
            party = self.purchase.invoice_party or self.purchase.party
        self.taxes = self.compute_taxes(party)
        self.amount = self.on_change_with_amount()

    @fields.depends(
        'product', 'unit', 'purchase', 'taxes',
        '_parent_purchase.party', '_parent_purchase.invoice_party',
        'product_supplier', methods=['compute_taxes', 'compute_unit_price',
            '_get_product_supplier_pattern'])
    def on_change_product(self):
        party = None
        if self.purchase:
            party = self.purchase.invoice_party or self.purchase.party

        # Set taxes before unit_price to have taxes in context of purchase
        # price
        self.taxes = self.compute_taxes(party)

        if self.product:
            category = self.product.purchase_uom.category
            if not self.unit or self.unit.category != category:
                self.unit = self.product.purchase_uom

            product_suppliers = list(self.product.product_suppliers_used(
                    **self._get_product_supplier_pattern()))
            if len(product_suppliers) == 1:
                self.product_supplier, = product_suppliers
            elif (self.product_supplier
                    and self.product_supplier not in product_suppliers):
                self.product_supplier = None

            self.unit_price = self.compute_unit_price()

        self.amount = self.on_change_with_amount()

    @cached_property
    def product_name(self):
        if self.product_supplier:
            return self.product_supplier.rec_name
        elif self.product:
            return self.product.rec_name
        else:
            return ''

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
            taxes_used = self.product.supplier_taxes_used
        elif company:
            account_config = AccountConfiguration(1)
            account = account_config.get_multivalue(
                'default_category_account_expense', company=company.id)
            if account:
                taxes_used = account.taxes
        for tax in taxes_used:
            if party and party.supplier_tax_rule:
                tax_ids = party.supplier_tax_rule.apply(tax, pattern)
                if tax_ids:
                    taxes.update(tax_ids)
                continue
            taxes.add(tax.id)
        if party and party.supplier_tax_rule:
            tax_ids = party.supplier_tax_rule.apply(None, pattern)
            if tax_ids:
                taxes.update(tax_ids)
        return list(taxes)

    @fields.depends('product', 'quantity', 'unit_price',
        methods=['_get_context_purchase_price'])
    def compute_unit_price(self):
        pool = Pool()
        Product = pool.get('product.product')

        unit_price = None
        if self.product:
            with Transaction().set_context(self._get_context_purchase_price()):
                unit_price = Product.get_purchase_price(
                    [self.product], abs(self.quantity or 0))[self.product.id]
        if unit_price is None:
            unit_price = self.unit_price
        return unit_price

    @fields.depends('product', 'product_supplier',
        methods=['on_change_product'])
    def on_change_product_supplier(self):
        if self.product_supplier:
            if self.product_supplier.product:
                self.product = self.product_supplier.product
            elif not self.product:
                if len(self.product_supplier.template.products) == 1:
                    self.product, = self.product_supplier.template.products
        self.on_change_product()

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
        'purchase', '_parent_purchase.currency')
    def on_change_with_amount(self):
        if (self.type == 'line'
                and self.quantity is not None
                and self.unit_price is not None):
            currency = self.purchase.currency if self.purchase else None
            amount = Decimal(str(self.quantity)) * self.unit_price
            if currency:
                return currency.round(amount)
            return amount

    def get_amount(self, name):
        if self.type == 'line':
            return self.on_change_with_amount()
        elif self.type == 'subtotal':
            amount = Decimal(0)
            for line2 in self.purchase.lines:
                if line2.type == 'line':
                    amount += line2.purchase.currency.round(
                        Decimal(str(line2.quantity)) * line2.unit_price)
                elif line2.type == 'subtotal':
                    if self == line2:
                        break
                    amount = Decimal(0)
            return amount

    @fields.depends('purchase', '_parent_purchase.warehouse')
    def on_change_with_warehouse(self, name=None):
        return self.purchase.warehouse if self.purchase else None

    def get_from_location(self, name):
        if (self.quantity or 0) >= 0:
            if self.purchase.party.supplier_location:
                return self.purchase.party.supplier_location
        elif self.purchase.return_from_location:
            return self.purchase.return_from_location

    def get_to_location(self, name):
        if (self.quantity or 0) >= 0:
            if self.purchase.warehouse:
                return self.purchase.warehouse.input_location
        elif self.purchase.party.supplier_location:
            return self.purchase.party.supplier_location

    @fields.depends('product')
    def on_change_with_movable(self, name=None):
        pool = Pool()
        Move = pool.get('stock.move')
        if self.product:
            return self.product.type in Move.get_product_types()

    @fields.depends('moves', methods=['planned_delivery_date'])
    def on_change_with_delivery_date(self, name=None):
        moves = [m for m in self.moves if m.state != 'cancelled']
        if moves:
            dates = filter(
                None, (m.effective_date or m.planned_date for m in moves))
            return min(dates, default=None)
        return self.planned_delivery_date

    @classmethod
    def set_delivery_date(cls, lines, name, value):
        cls.write([l for l in lines if l.delivery_date_edit], {
                'delivery_date_store': value,
                })

    @fields.depends('delivery_date_edit', 'delivery_date',
        methods=['planned_delivery_date'])
    def on_change_delivery_date_edit(self):
        if not self.delivery_date_edit:
            self.delivery_date = self.planned_delivery_date

    @property
    @fields.depends(
        'product_supplier', 'quantity', 'purchase',
        '_parent_purchase.purchase_date',
        'delivery_date_edit', 'delivery_date_store',
        '_parent_purchase.delivery_date', '_parent_purchase.party',
        '_parent_purchase.company')
    def planned_delivery_date(self):
        pool = Pool()
        ProductSupplier = pool.get('purchase.product_supplier')

        product_supplier = self.product_supplier
        if not product_supplier and self.purchase and self.purchase.company:
            product_supplier = ProductSupplier(
                party=self.purchase.party,
                company=self.purchase.company)
        delivery_date = None
        if self.delivery_date_edit:
            delivery_date = self.delivery_date_store
        elif self.purchase and self.purchase.delivery_date:
            delivery_date = self.purchase.delivery_date
        elif (product_supplier
                and self.quantity is not None
                and self.quantity > 0
                and self.purchase):
            date = self.purchase.purchase_date if self.purchase else None
            delivery_date = product_supplier.compute_supply_date(date=date)
            if delivery_date == datetime.date.max:
                delivery_date = None
        return delivery_date

    @classmethod
    def get_purchase_states(cls):
        pool = Pool()
        Purchase = pool.get('purchase.purchase')
        return Purchase.fields_get(['state'])['state']['selection']

    @fields.depends('purchase', '_parent_purchase.state')
    def on_change_with_purchase_state(self, name=None):
        if self.purchase:
            return self.purchase.state

    @classmethod
    def search_purchase_state(cls, name, clause):
        return [('purchase.state', *clause[1:])]

    @fields.depends('purchase', '_parent_purchase.company')
    def on_change_with_company(self, name=None):
        return self.purchase.company if self.purchase else None

    @fields.depends('purchase', '_parent_purchase.party')
    def on_change_with_supplier(self, name=None):
        return self.purchase.party if self.purchase else None

    @classmethod
    def search_supplier(cls, name, clause):
        return [('purchase.party' + clause[0][len(name):], *clause[1:])]

    @fields.depends('purchase', '_parent_purchase.purchase_date')
    def on_change_with_purchase_date(self, name=None):
        if self.purchase:
            return self.purchase.purchase_date

    @classmethod
    def search_purchase_date(cls, name, clause):
        return [('purchase.purchase_date', *clause[1:])]

    @classmethod
    def order_purchase_date(cls, tables):
        return cls.purchase.convert_order(
            'purchase.purchase_date', tables, cls)

    @fields.depends('purchase', '_parent_purchase.currency')
    def on_change_with_currency(self, name=None):
        return self.purchase.currency if self.purchase else None

    def get_invoice_line(self):
        'Return a list of invoice line for purchase line'
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
        if self.company.purchase_taxes_expense:
            invoice_line.taxes_deductible_rate = 0
        elif self.product:
            invoice_line.taxes_deductible_rate = (
                self.product.supplier_taxes_deductible_rate_used)
        invoice_line.invoice_type = 'in'
        if self.product:
            invoice_line.account = self.product.account_expense_used
            if not invoice_line.account:
                raise AccountError(
                    gettext('purchase'
                        '.msg_purchase_product_missing_account_expense',
                        purchase=self.purchase.rec_name,
                        product=self.product.rec_name))
        else:
            invoice_line.account = account_config.get_multivalue(
                'default_category_account_expense', company=self.company.id)
            if not invoice_line.account:
                raise AccountError(
                    gettext('purchase'
                        '.msg_purchase_missing_account_expense',
                        purchase=self.purchase.rec_name))
        invoice_line.stock_moves = self._get_invoice_line_moves(
            invoice_line.quantity)
        return [invoice_line]

    def _get_invoice_line_quantity(self):
        'Return the quantity that should be invoiced'
        pool = Pool()
        Uom = pool.get('product.uom')

        if (self.purchase.invoice_method in {'order', 'manual'}
                or not self.product
                or self.product.type == 'service'):
            return self.quantity
        elif self.purchase.invoice_method == 'shipment':
            quantity = 0.0
            for move in self.moves:
                if move.state != 'done':
                    continue
                qty = Uom.compute_qty(move.unit, move.quantity, self.unit)
                # Test only against from_location
                # as it is what matters for purchase
                src_type = 'supplier'
                if (move.from_location.type == src_type
                        and move.to_location.type != src_type):
                    quantity += qty
                elif (move.to_location.type == src_type
                        and move.from_location.type != src_type):
                    quantity -= qty
            return quantity

    def _get_invoiced_quantity(self):
        'Return the quantity already invoiced'
        pool = Pool()
        Uom = pool.get('product.uom')

        quantity = 0
        skips = {l for i in self.purchase.invoices_recreated for l in i.lines}
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
        if self.purchase.invoice_method in {'order', 'manual'}:
            moves.extend(self.moves)
        elif (self.purchase.invoice_method == 'shipment'
                and samesign(self.quantity, quantity)):
            for move in self.moves:
                if move.state == 'done':
                    if move.invoiced_quantity < move.quantity:
                        moves.append(move)
        return moves

    def get_move(self, move_type):
        '''
        Return move values for purchase line
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

        if (self.quantity >= 0) != (move_type == 'in'):
            return

        quantity = (self._get_move_quantity(move_type)
            - self._get_shipped_quantity(move_type))

        quantity = self.unit.round(quantity)
        if quantity <= 0:
            return

        if not self.purchase.party.supplier_location:
            raise PartyLocationError(
                gettext('purchase.msg_purchase_supplier_location_required',
                    purchase=self.purchase.rec_name,
                    party=self.purchase.party.rec_name))

        with Transaction().set_context(company=self.purchase.company.id):
            today = Date.today()

        move = Move()
        move.quantity = quantity
        move.unit = self.unit
        move.product = self.product
        move.from_location = self.from_location
        move.to_location = self.to_location
        move.state = 'draft'
        move.company = self.purchase.company
        if move.on_change_with_unit_price_required():
            move.unit_price = self.unit_price
            move.currency = self.purchase.currency
        move.planned_date = self.planned_delivery_date
        if move.planned_date and move.planned_date < today:
            move.planned_date = None
        move.invoice_lines = self._get_move_invoice_lines(move_type)
        move.origin = self
        move.origin_planned_date = move.planned_date
        return move

    def _get_move_quantity(self, move_type):
        'Return the quantity that should be shipped'
        return abs(self.quantity)

    def _get_shipped_quantity(self, move_type):
        'Return the quantity already shipped'
        pool = Pool()
        Uom = pool.get('product.uom')

        quantity = 0
        skip = set(self.moves_recreated)
        for move in self.moves:
            if move not in skip:
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
                raise PurchaseMoveQuantity(warning_name, gettext(
                        'purchase.msg_purchase_line_move_quantity',
                        line=self.rec_name,
                        extra=lang.format_number_symbol(
                            -quantity, self.unit),
                        quantity=lang.format_number_symbol(
                            self.quantity, self.unit)))

    def _get_move_invoice_lines(self, move_type):
        'Return the invoice lines that should be shipped'
        if self.purchase.invoice_method in {'order', 'manual'}:
            lines = self.invoice_lines
        else:
            lines = filter(lambda l: not l.stock_moves, self.invoice_lines)
            lines = filter(
                lambda l: samesign(self.quantity, l.quantity), lines)
        return list(lines)

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
                + ' %s @ %s' % (self.product.rec_name, self.purchase.rec_name))
        else:
            return self.purchase.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        _, operator, value = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('purchase.rec_name', *clause[1:]),
            ('product.rec_name', *clause[1:]),
            ]

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('/form//field[@name="note"]|/form//field[@name="description"]',
                'spell', Eval('_parent_purchase', {}).get('party_lang')),
            ('//label[@id="delivery_date"]', 'states', {
                    'invisible': Eval('type') != 'line',
                    }),
            ]

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Purchase = pool.get('purchase.purchase')
        purchase_ids = filter(None, {v.get('purchase') for v in vlist})
        for purchase in Purchase.browse(list(purchase_ids)):
            if purchase.state != 'draft':
                raise AccessError(
                    gettext('purchase.msg_purchase_line_create_draft',
                        purchase=purchase.rec_name))
        return super().create(vlist)

    @classmethod
    def delete(cls, lines):
        for line in lines:
            if line.purchase_state not in {'cancelled', 'draft'}:
                raise AccessError(
                    gettext('purchase.msg_purchase_line_delete_cancel_draft',
                        line=line.rec_name,
                        purchase=line.purchase.rec_name))
        super().delete(lines)

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
        return super().copy(lines, default=default)


class LineTax(ModelSQL):
    'Purchase Line - Tax'
    __name__ = 'purchase.line-account.tax'
    line = fields.Many2One(
        'purchase.line', "Purchase Line", ondelete='CASCADE', required=True,
        domain=[('type', '=', 'line')])
    tax = fields.Many2One(
        'account.tax', "Tax", ondelete='RESTRICT', required=True,
        domain=[('parent', '=', None)])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('line_tax_unique', Unique(t, t.line, t.tax),
                'purchase.msg_purchase_line_tax_unique'),
            ]

    @classmethod
    def __register__(cls, module):
        # Migration from 7.0: rename to standard name
        backend.TableHandler.table_rename(
            'purchase_line_account_tax', cls._table)
        super().__register__(module)


class LineIgnoredMove(ModelSQL):
    'Purchase Line - Ignored Move'
    __name__ = 'purchase.line-ignored-stock.move'
    purchase_line = fields.Many2One(
        'purchase.line', "Purchase Line", ondelete='CASCADE', required=True)
    move = fields.Many2One(
        'stock.move', "Stock Move", ondelete='RESTRICT', required=True,
        domain=[
            ('origin.id', '=', Eval('purchase_line', -1), 'purchase.line'),
            ('state', '=', 'cancelled'),
            ])

    @classmethod
    def __register__(cls, module):
        # Migration from 7.0: rename to standard name
        backend.TableHandler.table_rename(
            'purchase_line_moves_ignored_rel', cls._table)
        super().__register__(module)


class LineRecreatedMove(ModelSQL):
    'Purchase Line - Ignored Move'
    __name__ = 'purchase.line-recreated-stock.move'
    purchase_line = fields.Many2One(
        'purchase.line', "Purchase Line", ondelete='CASCADE', required=True)
    move = fields.Many2One(
        'stock.move', "Stock Move", ondelete='RESTRICT', required=True,
        domain=[
            ('origin.id', '=', Eval('purchase_line', -1), 'purchase.line'),
            ('state', '=', 'cancelled'),
            ])

    @classmethod
    def __register__(cls, module):
        # Migration from 7.0: rename to standard name
        backend.TableHandler.table_rename(
            'purchase_line_moves_recreated_rel', cls._table)
        super().__register__(module)


class PurchaseReport(CompanyReport):
    __name__ = 'purchase.purchase'

    @classmethod
    def execute(cls, ids, data):
        with Transaction().set_context(address_with_party=True):
            return super(PurchaseReport, cls).execute(ids, data)

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
    __name__ = 'purchase.handle.shipment.exception.ask'
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
    __name__ = 'purchase.handle.shipment.exception'
    start_state = 'ask'
    ask = StateView('purchase.handle.shipment.exception.ask',
        'purchase.handle_shipment_exception_ask_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'handle', 'tryton-ok', default=True),
            ])
    handle = StateTransition()

    def default_ask(self, fields):
        moves = []
        for line in self.record.lines:
            skip = set(line.moves_ignored + line.moves_recreated)
            for move in line.moves:
                if move.state == 'cancelled' and move not in skip:
                    moves.append(move.id)
        return {
            'domain_moves': moves,
            }

    def transition_handle(self):
        pool = Pool()
        PurchaseLine = pool.get('purchase.line')

        for line in self.record.lines:
            moves_ignored = []
            moves_recreated = []
            skip = set(line.moves_ignored)
            skip.update(line.moves_recreated)
            for move in line.moves:
                if move not in self.ask.domain_moves or move in skip:
                    continue
                if move in self.ask.recreate_moves:
                    moves_recreated.append(move.id)
                elif move in self.ask.ignore_moves:
                    moves_ignored.append(move.id)

            PurchaseLine.write([line], {
                'moves_ignored': [('add', moves_ignored)],
                'moves_recreated': [('add', moves_recreated)],
                })

        self.model.__queue__.process([self.record])
        return 'end'


class HandleInvoiceExceptionAsk(ModelView):
    'Handle Invoice Exception'
    __name__ = 'purchase.handle.invoice.exception.ask'
    recreate_invoices = fields.Many2Many(
        'account.invoice', None, None, "Invoices to Recreate",
        domain=[
            ('id', 'in', Eval('domain_invoices', [])),
            ('id', 'not in', Eval('ignore_invoices', [])),
            ],
        help="The selected cancelled invoices will be recreated.")
    ignore_invoices = fields.Many2Many(
        'account.invoice', None, None, "Invoices to Ignore",
        domain=[
            ('id', 'in', Eval('domain_invoices', [])),
            ('id', 'not in', Eval('recreate_invoices', [])),
            ],
        help="The selected cancelled invoices will be ignored.")
    domain_invoices = fields.Many2Many(
        'account.invoice', None, None, 'Domain Invoices')


class HandleInvoiceException(Wizard):
    'Handle Invoice Exception'
    __name__ = 'purchase.handle.invoice.exception'
    start_state = 'ask'
    ask = StateView('purchase.handle.invoice.exception.ask',
        'purchase.handle_invoice_exception_ask_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'handle', 'tryton-ok', default=True),
            ])
    handle = StateTransition()

    def default_ask(self, fields):
        skip = set(self.record.invoices_ignored)
        skip.update(self.record.invoices_recreated)
        invoices = []
        for invoice in self.record.invoices:
            if invoice.state == 'cancelled' and invoice not in skip:
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


class ModifyHeaderStateView(StateView):
    def get_view(self, wizard, state_name):
        with Transaction().set_context(modify_header=True):
            return super(ModifyHeaderStateView, self).get_view(
                wizard, state_name)

    def get_defaults(self, wizard, state_name, fields):
        return {}


class ModifyHeader(Wizard):
    "Modify Header"
    __name__ = 'purchase.modify_header'
    start = ModifyHeaderStateView('purchase.purchase',
        'purchase.modify_header_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Modify", 'modify', 'tryton-ok', default=True),
            ])
    modify = StateTransition()

    def get_purchase(self):
        if self.record.state != 'draft':
            raise AccessError(
                gettext('purchase.msg_purchase_modify_header_draft',
                    purchase=self.record.rec_name))
        return self.record

    def value_start(self, fields):
        purchase = self.get_purchase()
        values = {}
        for fieldname in fields:
            value = getattr(purchase, fieldname)
            if isinstance(value, Model):
                if getattr(purchase.__class__, fieldname)._type == 'reference':
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
        Line = pool.get('purchase.line')

        purchase = self.get_purchase()
        values = self.start._save_values()
        self.model.write([purchase], values)
        self.model.log([purchase], 'write', ','.join(sorted(values.keys())))

        # Call on_change after the save to ensure parent sale
        # has the modified values
        for line in purchase.lines:
            line.on_change_product()
        Line.save(purchase.lines)

        return 'end'


class ReturnPurchaseStart(ModelView):
    "Return Purchase"
    __name__ = 'purchase.return_purchase.start'


class ReturnPurchase(Wizard):
    "Return Purchase"
    __name__ = 'purchase.return_purchase'
    start = StateView('purchase.return_purchase.start',
        'purchase.return_purchase_start_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Return", 'return_', 'tryton-ok', default=True),
            ])
    return_ = StateAction('purchase.act_purchase_form')

    def do_return_(self, action):
        purchases = self.records
        return_purchases = self.model.copy(purchases, default={
                'origin': lambda data: (
                    '%s,%s' % (self.model.__name__, data['id'])),
                'lines.quantity': lambda data: (
                    data['quantity'] * -1 if data['type'] == 'line'
                    else data['quantity']),
                })

        data = {'res_id': [s.id for s in return_purchases]}
        if len(return_purchases) == 1:
            action['views'].reverse()
        return action, data
