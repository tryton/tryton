# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt
from decimal import Decimal
from functools import partial

from trytond.i18n import gettext
from trytond.ir.attachment import AttachmentCopyMixin
from trytond.ir.note import NoteCopyMixin
from trytond.model import (
    ChatMixin, Index, ModelSQL, ModelView, Unique, Workflow, dualmethod,
    fields, sequence_ordered)
from trytond.model.exceptions import AccessError, ValidationError
from trytond.model.fields.date import FormatMixin
from trytond.modules.account.tax import TaxableMixin
from trytond.modules.company.model import (
    employee_field, reset_employee, set_employee)
from trytond.modules.currency.fields import Monetary
from trytond.modules.product import price_digits, round_price
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Date, DateTime, Eval, Id, If
from trytond.report import Report
from trytond.tools import timezone as tz
from trytond.transaction import Transaction
from trytond.wizard import Button, StateTransition, StateView, Wizard

_datetime_format = '%H:%M'
_time_min = dt.datetime.strptime(
    dt.time.min.strftime(_datetime_format), _datetime_format).time()
_time_max = dt.datetime.strptime(
    dt.time.max.strftime(_datetime_format), _datetime_format).time()


class DateOrDateTime(FormatMixin, fields.Date):

    def __init__(self, *args, **kwargs):
        self.format = kwargs.pop('format')
        super().__init__(*args, **kwargs)

    def definition(self, model, language):
        definition = super().definition(model, language)
        definition['type'] = 'datetime'
        return definition


def to_datetime(value, company=None, time=None):
    if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        if time is None:
            time = _time_min
        if company and company.timezone:
            timezone = tz.ZoneInfo(company.timezone)
        else:
            timezone = None
        value = (dt.datetime.combine(value, time, timezone)
            .astimezone(tz.UTC)
            .replace(tzinfo=None))
    return value


def to_date(value, company=None):
    if isinstance(value, dt.datetime):
        if company and company.timezone:
            timezone = tz.ZoneInfo(company.timezone)
        else:
            timezone = None
        value = (value
            .replace(tzinfo=tz.UTC)
            .astimezone(timezone)
            .replace(tzinfo=None)
            .date())
    return value


class Configuration(metaclass=PoolMeta):
    __name__ = 'sale.configuration'

    rental_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Rental Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('sequence_type', '=',
                    Id('sale_rental', 'sequence_type_rental')),
                ]))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'rental_sequence':
            return pool.get('sale.configuration.sequence')
        return super().multivalue_model(field)

    @classmethod
    def default_rental_sequence(cls, **pattern):
        return cls.multivalue_model(
            'rental_sequence').default_rental_sequence()


class ConfigurationSequence(metaclass=PoolMeta):
    __name__ = 'sale.configuration.sequence'

    rental_sequence = fields.Many2One(
        'ir.sequence', "Rental Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('sequence_type', '=',
                Id('sale_rental', 'sequence_type_rental')),
            ])

    @classmethod
    def default_rental_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id(
                'sale_rental', 'sequence_rental')
        except KeyError:
            return None


class Rental(
        Workflow, ModelSQL, ModelView, TaxableMixin,
        AttachmentCopyMixin, NoteCopyMixin, ChatMixin):
    __name__ = 'sale.rental'
    _rec_name = 'number'

    company = fields.Many2One(
        'company.company', "Company", required=True,
        states={
            'readonly': (Eval('state') != 'draft') | Eval('party', True),
            },
        help="Make the sale rental belong to the company.")

    number = fields.Char(
        "Number", readonly=True,
        help="The main identification of the sale rental.")
    reference = fields.Char(
        "Reference",
        help="The identification of an external origin.")
    description = fields.Char(
        "Description",
        states={
            'readonly': Eval('state') != 'draft',
            })

    party = fields.Many2One(
        'party.party', "Party", required=True,
        states={
            'readonly': (
                (Eval('state') != 'draft')
                | (Eval('lines', [0]) & Eval('party'))),
            },
        context={
            'company': Eval('company', -1),
            },
        depends=['company'],
        help="The party who is renting.")
    contact = fields.Many2One(
        'party.contact_mechanism', "Contact",
        context={
            'company': Eval('company', -1),
            },
        search_context={
            'related_party': Eval('party'),
            },
        depends={'company', 'party'})
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
        depends={'company', 'party'})
    invoice_address = fields.Many2One(
        'party.address', "Invoice Address",
        domain=[
            ('party', '=', If(Eval('invoice_party'),
                    Eval('invoice_party', -1), Eval('party', -1))),
            ],
        states={
            'readonly': Eval('state') != 'draft',
            'required': ~Eval('state').in_(['draft', 'cancelled']),
            })
    payment_term = fields.Many2One(
        'account.invoice.payment_term', "Payment Term",
        states={
            'readonly': Eval('state') != 'draft',
            })

    warehouse = fields.Many2One(
        'stock.location', "Warehouse",
        domain=[
            ('type', '=', 'warehouse'),
            ],
        states={
            'readonly': Eval('state') != 'draft',
            'required': ~Eval('state').in_(['draft', 'cancelled']),
            })
    currency = fields.Many2One(
        'currency.currency', "Currency", required=True,
        states={
            'readonly': ((Eval('state') != 'draft')
                | (Eval('lines', [0]) & Eval('currency', 0))),
            })

    start = fields.Function(
        DateOrDateTime("Start", format=_datetime_format),
        'on_change_with_start')
    end = fields.Function(
        DateOrDateTime("End", format=_datetime_format),
        'on_change_with_end')
    lines = fields.One2Many(
        'sale.rental.line', 'rental', "Lines",
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['start', 'end'])

    outgoing_moves = fields.One2Many(
        'stock.move', 'origin', "Outgoing Moves", readonly=True,
        filter=[
            ('to_location.type', '=', 'rental'),
            ])
    incoming_moves = fields.One2Many(
        'stock.move', 'origin', "Incoming Moves", readonly=True,
        filter=[
            ('from_location.type', '=', 'rental'),
            ])

    has_returnable_lines = fields.Function(
        fields.Boolean("Has Returnable Lines"),
        'get_has_returnable_lines')
    has_lines_to_invoice = fields.Function(
        fields.Boolean("Has Lines to Invoice"),
        'get_has_lines_to_invoice')

    untaxed_amount = fields.Function(
        Monetary("Untaxed", digits='currency', currency='currency'),
        'get_amount')
    untaxed_amount_cache = fields.Numeric(
        "Untaxed Cache", digits='currency', readonly=True)
    tax_amount = fields.Function(
        Monetary("Tax", digits='currency', currency='currency'),
        'get_amount')
    tax_amount_cache = fields.Numeric(
        "Tax Cache", digits='currency', readonly=True)
    total_amount = fields.Function(
        Monetary("Total", digits='currency', currency='currency'),
        'get_amount')
    total_amount_cache = fields.Numeric(
        "Total Cache", digits='currency', readonly=True)

    quoted_by = employee_field(
        "Quoted By", states=['quotation', 'confirmed', 'done', 'cancelled'])
    confirmed_by = employee_field(
        "Confirmed By", states=['confirmed', 'done', 'cancelled'])
    state = fields.Selection([
            ('draft', "Draft"),
            ('quotation', "Quotation"),
            ('confirmed', "Confirmed"),
            ('picked up', "Picked up"),
            ('done', "Done"),
            ('cancelled', "Cancelled"),
            ], "State", readonly=True, required=True, sort=False,
        help="The current state of the sale rental.")

    @classmethod
    def __setup__(cls):
        cls.number.search_unaccented = False
        cls.reference.search_unaccented = False
        super().__setup__()
        t = cls.__table__()
        cls._sql_indexes.update({
                Index(t, (t.reference, Index.Similarity())),
                Index(t, (t.party, Index.Equality())),
                Index(
                    t,
                    (t.state, Index.Equality()),
                    where=t.state.in_([
                            'draft', 'quotation', 'confirmed', 'picked up'])),
                })
        cls._transitions |= {
            ('draft', 'quotation'),
            ('draft', 'cancelled'),
            ('quotation', 'confirmed'),
            ('quotation', 'draft'),
            ('quotation', 'cancelled'),
            ('confirmed', 'picked up'),
            ('confirmed', 'draft'),
            ('picked up', 'done'),
            ('picked up', 'draft'),
            ('cancelled', 'draft'),
            }
        cls._buttons.update({
                'cancel': {
                    'invisible': ~Eval('state').in_(['draft', 'quotation']),
                    'icon': 'tryton-cancel',
                    'depends': ['state'],
                    },
                'draft': {
                    'invisible': ~Eval('state').in_(
                        ['quotation', 'confirmed', 'picked up', 'cancelled']),
                    'icon': If(Eval('state') == 'cancelled',
                        'tryton-undo', 'tryton-back'),
                    'depends': ['state'],
                    },
                'quote': {
                    'invisible': Eval('state') != 'draft',
                    'readonly': ~Eval('lines', []),
                    'icon': 'tryton-forward',
                    'depends': ['state'],
                    },
                'confirm': {
                    'invisible': Eval('state') != 'quotation',
                    'icon': 'tryton-forward',
                    'depends': ['state'],
                    },
                'pickup': {
                    'invisible': Eval('state') != 'confirmed',
                    'icon': 'tryton-shipment-out',
                    'depends': ['state'],
                    },
                'return_': {
                    'invisible': (
                        Eval('state').in_(['draft', 'quote'])
                        | ~Eval('has_returnable_lines')),
                    'icon': 'tryton-shipment-in',
                    'depends': ['state', 'has_returnable_lines'],
                    },
                'invoice': {
                    'invisible': (
                        Eval('state').in_(['draft', 'quote'])
                        | ~Eval('has_lines_to_invoice')),
                    'icon': 'tryton-invoice',
                    'depends': ['has_lines_to_invoice'],
                    },
                })
        cls._states_cached = {'confirmed', 'picked up', 'done', 'cancelled'}

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_warehouse(cls):
        Location = Pool().get('stock.location')
        return Location.get_default_warehouse()

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
    def default_state(cls):
        return 'draft'

    @fields.depends('company', 'party', 'invoice_party', 'currency', 'lines')
    def on_change_party(self):
        if not self.invoice_party:
            self.invoice_address = None
        if not self.lines:
            self.currency = self.default_currency(
                company=self.company.id if self.company else None)
        if self.party:
            if not self.invoice_party:
                self.invoice_address = self.party.address_get(type='invoice')
            self.payment_term = self.party.customer_payment_term
            if not self.lines and self.party.customer_currency:
                self.currency = self.party.customer_currency

    @fields.depends('party', 'invoice_party')
    def on_change_invoice_party(self):
        if self.invoice_party:
            self.invoice_address = self.invoice_party.address_get(
                type='invoice')
        elif self.party:
            self.invoice_address = self.party.address_get(type='invoice')

    @classmethod
    def default_start(cls):
        now = dt.datetime.now().replace(second=0, microsecond=0)
        now += dt.timedelta(minutes=30 - now.minute % 30)
        return now

    @fields.depends('company', 'lines')
    def on_change_with_start(self, name=None):
        return min(map(partial(to_datetime, company=self.company), filter(
                    None,
                    (getattr(l, 'start', None) for l in (self.lines or [])))),
            default=self.default_start())

    @fields.depends('company', 'lines')
    def on_change_with_end(self, name=None):
        return max(map(partial(
                    to_datetime, company=self.company, time=_time_max),
                filter(
                    None,
                    (getattr(l, 'end', None) for l in (self.lines or [])))),
            default=None)

    @fields.depends('lines', 'currency', methods=['get_tax_amount'])
    def on_change_lines(self):
        self.untaxed_amount = Decimal(0)
        self.tax_amount = Decimal(0)
        self.total_amount = Decimal(0)

        for line in self.lines or []:
            self.untaxed_amount += getattr(line, 'amount', None) or 0
        self.tax_amount = self.get_tax_amount()

        if self.currency:
            self.untaxed_amount = self.currency.round(self.untaxed_amount)
            self.tax_amount = self.currency.round(self.tax_amount)
        self.total_amount = self.untaxed_amount + self.tax_amount
        if self.currency:
            self.total_amount = self.currency.round(self.total_amount)

    def get_has_returnable_lines(self, name):
        return any(l.rental_state == 'picked up' for l in self.lines)

    def get_has_lines_to_invoice(self, name):
        return any(l.to_invoice for l in self.lines)

    @fields.depends(methods=['_get_taxes'])
    def get_tax_amount(self):
        return sum(
            (t.amount for t in self._get_taxes().values()), Decimal(0))

    @property
    def taxable_lines(self):
        taxable_lines = []
        for line in self.lines:
            taxable_lines.extend(line.taxable_lines)
        return taxable_lines

    @fields.depends('party', 'company')
    def _get_tax_context(self):
        context = {}
        if self.party and self.party.lang:
            context['language'] = self.party.lang.code
        if self.company:
            context['company'] = self.company.id
        return context

    @classmethod
    def get_amount(cls, rentals, names):
        untaxed_amount = {}
        tax_amount = {}
        total_amount = {}

        if {'tax_amount', 'total_amount'} & set(names):
            compute_taxes = True
        else:
            compute_taxes = False
        # Sort cached first and re-instanciate to optimize cache management
        rentals = sorted(
            rentals, key=lambda s: s.state in cls._states_cached, reverse=True)
        for rental in cls.browse(rentals):
            if (rental.state in cls._states_cached
                    and rental.untaxed_amount_cache is not None
                    and rental.tax_amount_cache is not None
                    and rental.total_amount_cache is not None):
                untaxed_amount[rental.id] = rental.untaxed_amount_cache
                if compute_taxes:
                    tax_amount[rental.id] = rental.tax_amount_cache
                    total_amount[rental.id] = rental.total_amount_cache
            else:
                untaxed_amount[rental.id] = sum(
                    (line.amount for line in rental.lines), Decimal(0))
                if compute_taxes:
                    tax_amount[rental.id] = rental.get_tax_amount()
                    total_amount[rental.id] = (
                        untaxed_amount[rental.id] + tax_amount[rental.id])

        amounts = {}
        if 'untaxed_amount' in names:
            amounts['untaxed_amount'] = untaxed_amount
        if 'tax_amount' in names:
            amounts['tax_amount'] = tax_amount
        if 'total_amount' in names:
            amounts['total_amount'] = total_amount
        return amounts

    @classmethod
    def set_number(cls, rentals):
        pool = Pool()
        Config = pool.get('sale.configuration')

        config = Config(1)
        for rental in rentals:
            if rental.number:
                continue
            rental.number = config.get_multivalue(
                'rental_sequence',
                company=rental.company.id).get()
        cls.save(rentals)

    @classmethod
    def set_moves(cls, rentals):
        pool = Pool()
        Line = pool.get('sale.rental.line')
        Move = pool.get('stock.move')

        lines, moves = [], set()
        for rental in rentals:
            for line in rental.lines:
                line.outgoing_moves = line.get_moves('out')
                moves.update(line.outgoing_moves)
                line.incoming_moves = line.get_moves('in')
                moves.update(line.incoming_moves)
                lines.append(line)
        Move.save(moves)
        Line.save(lines)

    @classmethod
    def delete_moves(cls, rentals, all_=False):
        pool = Pool()
        Line = pool.get('sale.rental.line')
        Move = pool.get('stock.move')

        lines, moves = [], set()
        for rental in rentals:
            for line in rental.lines:
                moves.update(line.outgoing_moves)
                line.outgoing_moves = []
                moves.update(line.incoming_moves)
                line.incoming_moves = []
                lines.append(line)
        Line.save(lines)
        moves = Move.browse(moves)
        Move.draft(moves)
        Move.delete([
                m for m in moves if all_ or m.state in {'draft', 'cancelled'}])

    @classmethod
    def store_cache(cls, rentals):
        for rental in rentals:
            rental.untaxed_amount_cache = rental.untaxed_amount
            rental.tax_amount_cache = rental.tax_amount
            rental.total_amount_cache = rental.total_amount
        cls.save(rentals)

    def create_invoice(self):
        invoice_lines = []

        for line in self.lines:
            if line.to_invoice:
                invoice_lines.extend(line.get_invoice_lines())
        if not invoice_lines:
            return

        invoice = self._get_invoice()
        if getattr(invoice, 'lines', None):
            invoice_lines = list(invoice.lines) + invoice_lines
        invoice.lines = invoice_lines
        return invoice

    def _get_invoice(self):
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

    def chat_language(self, audience='internal'):
        language = super().chat_language(audience=audience)
        if audience == 'public':
            language = self.party.lang.code if self.party.lang else None
        return language

    @classmethod
    def copy(cls, rentals, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('number', None)
        default.setdefault('quoted_by')
        default.setdefault('confirmed_by')
        default.setdefault('lines.outgoing_moves', None)
        default.setdefault('lines.incoming_moves', None)
        return super().copy(rentals, default=default)

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('/tree', 'visual',
                If(Eval('state') == 'cancelled', 'muted', '')),
            ]

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, rentals):
        cls.delete_moves(rentals, all_=True)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    @reset_employee('quoted_by', 'confirmed_by')
    def draft(cls, rentals):
        pool = Pool()
        Line = pool.get('sale.rental.line')

        # Set actual period as planned period
        lines = []
        for rental in rentals:
            for line in rental.lines:
                if line.per_day:
                    if line.actual_start:
                        line.planned_start_day = to_date(
                            line.actual_start, line.company)
                    if line.actual_end:
                        line.planned_end_day = to_date(
                            line.actual_end, line.company)
                    if line.planned_end_day < line.planned_start_day:
                        line.planned_end_day = line.planned_start_day
                else:
                    if line.actual_start:
                        line.planned_start = line.actual_start
                    if line.actual_end:
                        line.planned_end = line.actual_end
                    if line.planned_end < line.planned_start:
                        line.planned_end = line.planned_start
                lines.append(line)
        Line.save(lines)
        cls.delete_moves(rentals)

    @classmethod
    @ModelView.button
    @Workflow.transition('quotation')
    @set_employee('quoted_by')
    def quote(cls, rentals):
        cls.set_number(rentals)
        cls.set_moves(rentals)

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    @set_employee('confirmed_by')
    def confirm(cls, rentals):
        cls.store_cache(rentals)
        cls.write(rentals, {'state': 'confirmed'})
        cls.try_picked_up(rentals)

    @classmethod
    @ModelView.button_action('sale_rental.wizard_sale_rental_pickup')
    def pickup(cls, rentals):
        pass

    @dualmethod
    def try_picked_up(cls, rentals):
        to_picked_up = []
        for rental in rentals:
            if all(
                    l.rental_state in {'picked up', 'done'}
                    for l in rental.lines):
                to_picked_up.append(rental)
        if to_picked_up:
            cls.picked_up(to_picked_up)

    @classmethod
    @Workflow.transition('picked up')
    def picked_up(cls, rentals):
        cls.write(rentals, {'state': 'picked up'})
        cls.try_done(rentals)

    @classmethod
    @ModelView.button_action('sale_rental.wizard_sale_rental_return')
    def return_(cls, rentals):
        pass

    @classmethod
    @ModelView.button
    def invoice(cls, rentals):
        pool = Pool()
        Invoice = pool.get('account.invoice')

        invoices = {}
        for rental in rentals:
            invoice = rental.create_invoice()
            if invoice:
                invoices[rental] = invoice

        Invoice.save(invoices.values())
        Invoice.update_taxes(invoices.values())
        for sale, invoice in invoices.items():
            sale.copy_resources_to(invoice)

    @dualmethod
    def try_done(cls, rentals):
        to_do = []
        for rental in rentals:
            if all(l.rental_state == 'done' for l in rental.lines):
                to_do.append(rental)
        if to_do:
            cls.do(to_do)

    @classmethod
    @Workflow.transition('done')
    def do(cls, rentals):
        cls.invoice(rentals)


class RentalLine(sequence_ordered(), ModelSQL, ModelView, TaxableMixin):
    __name__ = 'sale.rental.line'

    rental = fields.Many2One(
        'sale.rental', "Rental", required=True, ondelete='CASCADE',
        states={
            'readonly': (
                (Eval('rental_state') != 'draft')
                & Eval('rental')),
            },
        help="Add the line below the rental.")

    product = fields.Many2One(
        'product.product', "Product", required=True, ondelete='RESTRICT',
        domain=[
            ('type', 'in', ['assets', 'service']),
            ('rentable', '=', True),
            ],
        states={
            'readonly': Eval('rental_state') != 'draft',
            },
        context={
            'company': Eval('company', -1),
            },
        search_context={
            'locations': If(Eval('_parent_rental', {}).get('warehouse'),
                [Eval('_parent_rental', {}).get('warehouse', -1)], []),
            'stock_date_end': Date(start=Eval('start', DateTime())),
            'stock_skip_warehouse': True,
            'rental_date': Date(start=Eval('start', DateTime())),
            'currency': Eval('_parent_rental', {}).get('currency', -1),
            'customer': Eval('_parent_rental', {}).get('party', -1),
            'uom': Eval('unit', -1),
            'taxes': Eval('taxes', []),
            'quantity': Eval('quantity', 0),
            'duration': Eval('duration', None),
            },
        depends=['company'])
    per_day = fields.Boolean(
        "Per Day",
        states={
            'readonly': Eval('rental_state') != 'draft',
            })
    quantity = fields.Float(
        "Quantity", digits='unit', required=True,
        domain=[
            If(Eval('quantity'),
                ('quantity', '>=', 0),
                ()),
            ],
        states={
            'readonly': Eval('rental_state') != 'draft',
            })
    unit = fields.Many2One(
        'product.uom', "Unit", required=True,
        states={
            'readonly': Eval('rental_state') != 'draft',
            },
        domain=[
            If(Eval('product_uom_category'),
                ('category', '=', Eval('product_uom_category', -1)),
                ('category', '=', -1)),
            ])

    planned_start_day = fields.Date(
        "Planned Start",
        domain=[
            If(Eval('planned_start_day') & Eval('planned_end_day'),
                ('planned_start_day', '<=', Eval('planned_end_day', None)),
                ()),
            If(~Eval('per_day'),
                ('planned_start_day', '=', None),
                ()),
            ],
        states={
            'required': Eval('per_day', False),
            'invisible': ~Eval('per_day'),
            'readonly': Eval('rental_state') != 'draft',
            })
    planned_end_day = fields.Date(
        "Planned End",
        domain=[
            If(Eval('planned_start_day') & Eval('planned_end_day'),
                ('planned_end_day', '>=', Eval('planned_start_day', None)),
                ()),
            If(~Eval('per_day'),
                ('planned_end_day', '=', None),
                ()),
            ],
        states={
            'required': Eval('per_day', False),
            'invisible': ~Eval('per_day'),
            'readonly': Eval('rental_state') != 'draft',
            })
    planned_start = fields.DateTime(
        "Planned Start", format=_datetime_format,
        domain=[
            If(Eval('planned_start') & Eval('planned_end'),
                ('planned_start', '<=', Eval('planned_end')),
                ()),
            If(Eval('per_day', False),
                ('planned_start', '=', None),
                ()),
            ],
        states={
            'required': ~Eval('per_day'),
            'invisible': Eval('per_day', False),
            'readonly': Eval('rental_state') != 'draft',
            })
    planned_end = fields.DateTime(
        "Planned End", format=_datetime_format,
        domain=[
            If(Eval('planned_start') & Eval('planned_end'),
                ('planned_end', '>=', Eval('planned_start')),
                ()),
            If(Eval('per_day', False),
                ('planned_end', '=', None),
                ()),
            ],
        states={
            'required': ~Eval('per_day'),
            'invisible': Eval('per_day', False),
            'readonly': Eval('rental_state') != 'draft',
            })
    planned_duration = fields.Function(
        fields.TimeDelta(
            "Planned Duration",
            states={
                'invisible': ~Eval('planned_duration'),
                }),
        'on_change_with_planned_duration')

    actual_start = fields.DateTime(
        "Actual Start", format=_datetime_format, readonly=True,
        domain=[
            If(Eval('actual_start') & Eval('actual_end'),
                ('actual_start', '<=', Eval('actual_end')),
                ()),
            ],
        states={
            'invisible': ~Eval('actual_start'),
            'required': Eval('rental_state').in_(['picked up', 'done']),
            })
    actual_end = fields.DateTime(
        "Actual End", format=_datetime_format, readonly=True,
        domain=[
            If(Eval('actual_start') & Eval('actual_end'),
                ('actual_end', '>=', Eval('actual_start')),
                ()),
            ],
        states={
            'invisible': ~Eval('actual_end'),
            'required': Eval('rental_state') == 'done',
            })

    start = fields.Function(
        DateOrDateTime("Start", format=_datetime_format),
        'on_change_with_start')
    end = fields.Function(
        DateOrDateTime("End", format=_datetime_format),
        'on_change_with_end')
    duration = fields.Function(
        fields.TimeDelta(
            "Duration",
            states={
                'invisible': ~Eval('duration'),
                }),
        'on_change_with_duration')

    unit_price = Monetary(
        "Unit Price", currency='currency', digits=price_digits, required=True,
        states={
            'readonly': Eval('rental_state') != 'draft',
            })
    unit_price_unit = fields.Many2One(
        'product.uom', "Unit Price Unit", required=True,
        domain=[
            ('category', '=', Id('product', 'uom_cat_time')),
            ],
        states={
            'readonly': Eval('rental_state') != 'draft',
            })
    taxes = fields.Many2Many(
        'sale.rental.line-account.tax', 'line', 'tax', "Taxes",
        order=[('tax.sequence', 'ASC'), ('tax.id', 'ASC')],
        domain=[
            ('parent', '=', None),
            ['OR',
                ('group', '=', None),
                ('group.kind', 'in', ['sale', 'both'])],
            ('company', '=', Eval('company', -1)),
            ],
        states={
            'readonly': Eval('rental_state') != 'draft',
            })
    planned_amount = fields.Function(
        Monetary(
            "Planned Amount", digits='currency', currency='currency',
            states={
                'invisible': ~Eval('planned_duration'),
                }),
        'on_change_with_planned_amount')
    amount = fields.Function(
        Monetary(
            "Amount", digits='currency', currency='currency',
            states={
                'invisible': ~Eval('duration'),
                }),
        'on_change_with_amount')

    outgoing_moves = fields.Many2Many(
        'sale.rental.line-outgoing-stock.move', 'line', 'move',
        "Outgoing Moves",
        states={
            'readonly': True,
            })
    incoming_moves = fields.Many2Many(
        'sale.rental.line-incoming-stock.move', 'line', 'move',
        "Incoming Moves",
        states={
            'readonly': True,
            })

    invoice_lines = fields.One2Many(
        'account.invoice.line', 'origin', "Invoice Lines", readonly=True)

    rental_state = fields.Function(
        fields.Selection('get_rental_states', "Rental State"),
        'on_change_with_rental_state')
    company = fields.Function(
        fields.Many2One('company.company', "Company"),
        'on_change_with_company')
    currency = fields.Function(
        fields.Many2One('currency.currency', "Currency"),
        'on_change_with_currency')
    product_uom_category = fields.Function(
        fields.Many2One('product.uom.category', "Product UoM Category"),
        'on_change_with_product_uom_category')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('rental')

    @fields.depends(
        'rental', 'per_day', '_parent_rental.company',
        '_parent_rental.start', '_parent_rental.end',
        'planned_start_day', 'planned_end_day',
        'planned_start', 'planned_end',
        methods=['on_change_with_duration'])
    def _set_planned(self):
        if self.rental:
            if self.per_day:
                if not self.planned_start_day:
                    self.planned_start_day = to_date(
                        self.rental.start, self.rental.company)
                if not self.planned_end_day:
                    self.planned_end_day = to_date(
                        self.rental.end, self.rental.company)
                self.planned_start = self.planned_end = None
            else:
                self.planned_start_day = self.planned_end_day = None
                if not self.planned_start:
                    self.planned_start = to_datetime(
                        self.rental.start, self.rental.company)
                if not self.planned_end:
                    self.planned_end = to_datetime(
                        self.rental.end, self.rental.company, _time_max)
            self.duration = self.on_change_with_duration()

    @fields.depends(
        'product', 'unit',
        methods=[
            'compute_taxes', 'compute_unit_price', 'on_change_with_amount',
            '_set_planned'])
    def on_change_product(self):
        if not self.product:
            return
        self.per_day = self.product.rental_per_day

        self._set_planned()

        self.taxes = self.compute_taxes()

        if (not self.unit
                or self.unit.category != self.product.default_uom.category):
            self.unit = self.product.default_uom

        self.unit_price_unit = self.product.rental_unit
        self.unit_price = self.compute_unit_price()
        self.amount = self.on_change_with_amount()

    @fields.depends(
        'product',
        'rental', '_parent_rental.invoice_party', '_parent_rental.party',
        methods=['_get_tax_rule_pattern'])
    def compute_taxes(self):
        party = None
        if self.rental:
            party = self.rental.invoice_party or self.rental.party

        taxes = set()
        pattern = self._get_tax_rule_pattern()
        for tax in self.product.customer_rental_taxes_used:
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

    def _get_tax_rule_pattern(self):
        return {}

    @property
    def taxable_lines(self):
        # In case we're called from an on_change
        # we have to use some sensible defaults
        return [(
                getattr(self, 'taxes', None) or [],
                getattr(self, 'unit_price', None) or Decimal(0),
                (getattr(self, 'quantity', None) or 0)
                * (getattr(self, 'duration_unit', None) or 0),
                None,
                )]

    def _get_tax_context(self):
        return self.rental._get_tax_context()

    @fields.depends(
        'product', 'quantity', 'unit_price_unit',
        methods=['on_change_with_duration', '_get_context_rental_price'])
    def compute_unit_price(self):
        pool = Pool()
        Product = pool.get('product.product')
        UoM = pool.get('product.uom')

        if not self.product:
            return

        duration = self.on_change_with_duration()

        with Transaction().set_context(self._get_context_rental_price()):
            unit_price = Product.get_rental_price(
                [self.product],
                quantity=self.quantity or 0,
                duration=duration or dt.timedelta())[self.product.id]
            if unit_price is not None:
                if self.unit_price_unit:
                    unit_price = UoM.compute_price(
                        self.product.rental_unit, unit_price,
                        self.unit_price_unit)
                unit_price = round_price(unit_price)
            return unit_price

    @fields.depends(
        'rental', '_parent_rental.currency', '_parent_rental.party',
        'start', 'company', 'unit', 'product', 'taxes')
    def _get_context_rental_price(self):
        context = {}
        if self.rental:
            if self.rental.currency:
                context['currency'] = self.rental.currency.id
            if self.rental.party:
                context['customer'] = self.rental.party.id
        if self.start:
            context['rental_date'] = self.start
        if self.company:
            context['company'] = self.company.id
        if self.unit:
            context['uom'] = self.unit.id
        elif self.product:
            context['uom'] = self.product.default_uom.id
        context['taxes'] = [t.id for t in self.taxes or []]
        return context

    @fields.depends(methods=['compute_unit_price', 'on_change_with_amount'])
    def on_change_quantity(self):
        self.unit_price = self.compute_unit_price()
        self.amount = self.on_change_with_amount()

    @fields.depends(methods=['on_change_quantity'])
    def on_change_unit(self):
        self.on_change_quantity()

    @fields.depends(methods=['compute_unit_price', 'on_change_with_amount'])
    def _on_change_planned(self):
        self.unit_price = self.compute_unit_price()
        self.amount = self.on_change_with_amount()

    @fields.depends(methods=['_on_change_planned'])
    def on_change_planned_start_day(self):
        self._on_change_planned()

    @fields.depends(methods=['_on_change_planned'])
    def on_change_planned_end_day(self):
        self._on_change_planned()

    @fields.depends(methods=['_on_change_planned'])
    def on_change_planned_start(self):
        self._on_change_planned()

    @fields.depends(methods=['_on_change_planned'])
    def on_change_planned_end(self):
        self._on_change_planned()

    @fields.depends(
        'per_day',
        'planned_start_day', 'planned_end_day',
        'planned_start', 'planned_end')
    def on_change_with_planned_duration(self, name=None):
        if self.per_day:
            if self.planned_start_day and self.planned_end_day:
                return self.planned_end_day - self.planned_start_day
        else:
            if self.planned_start and self.planned_end:
                return self.planned_end - self.planned_start

    @property
    @fields.depends('planned_duration', 'unit_price_unit')
    def planned_duration_unit(self):
        pool = Pool()
        UoM = pool.get('product.uom')
        Data = pool.get('ir.model.data')
        hour = UoM(Data.get_id('product', 'uom_hour'))

        if self.planned_duration:
            duration = self.planned_duration.total_seconds() / 60 / 60
        else:
            duration = 0
        if self.unit_price_unit:
            duration = UoM.compute_qty(
                hour, duration, self.unit_price_unit, round=False)
        return duration

    @fields.depends(
        'per_day', 'company',
        'actual_start', 'planned_start_day', 'planned_start')
    def on_change_with_start(self, name=None):
        if self.per_day:
            return (
                to_date(self.actual_start, self.company)
                or self.planned_start_day)
        else:
            return self.actual_start or self.planned_start

    @fields.depends(
        'per_day', 'company',
        'actual_end', 'planned_end_day', 'planned_end')
    def on_change_with_end(self, name=None):
        if self.per_day:
            return (
                to_date(self.actual_end, self.company) or self.planned_end_day)
        else:
            return self.actual_end or self.planned_end

    @fields.depends(methods=['on_change_with_start', 'on_change_with_end'])
    def on_change_with_duration(self, name=None):
        start = self.on_change_with_start()
        end = self.on_change_with_end()
        if start and end:
            return end - start

    @property
    @fields.depends('duration', 'unit_price_unit')
    def duration_unit(self):
        pool = Pool()
        UoM = pool.get('product.uom')
        Data = pool.get('ir.model.data')
        hour = UoM(Data.get_id('product', 'uom_hour'))

        if self.duration:
            duration = self.duration.total_seconds() / 60 / 60
        else:
            duration = 0
        if self.unit_price_unit:
            duration = UoM.compute_qty(
                hour, duration, self.unit_price_unit, round=False)
        return duration

    @fields.depends(
        'quantity', 'unit_price', 'currency',
        methods=['on_change_with_planned_duration', 'planned_duration_unit'])
    def on_change_with_planned_amount(self, name=None):
        self.planned_duration = self.on_change_with_planned_duration()
        if self.quantity is not None and self.unit_price is not None:
            amount = (
                Decimal(self.quantity)
                * Decimal(self.planned_duration_unit)
                * self.unit_price)
            if self.currency:
                amount = self.currency.round(amount)
            return amount

    @fields.depends(
        'quantity', 'unit_price', 'currency',
        methods=['on_change_with_duration', 'duration_unit'])
    def on_change_with_amount(self, name=None):
        self.duration = self.on_change_with_duration()
        if self.quantity is not None and self.unit_price is not None:
            amount = (
                Decimal(self.quantity)
                * Decimal(self.duration_unit)
                * self.unit_price)
            if self.currency:
                amount = self.currency.round(amount)
            return amount

    @classmethod
    def get_rental_states(cls):
        pool = Pool()
        Rental = pool.get('sale.rental')
        return Rental.fields_get(['state'])['state']['selection']

    @fields.depends(
        'rental', '_parent_rental.state', 'actual_start', 'actual_end')
    def on_change_with_rental_state(self, name=None):
        if self.actual_end:
            return 'done'
        elif self.actual_start:
            return 'picked up'
        elif self.rental:
            return self.rental.state

    @fields.depends('rental', '_parent_rental.company')
    def on_change_with_company(self, name=None):
        if self.rental and self.rental.company:
            return self.rental.company.id

    @fields.depends('rental', '_parent_rental.currency')
    def on_change_with_currency(self, name=None):
        if self.rental and self.rental.currency:
            return self.rental.currency.id

    @fields.depends('product')
    def on_change_with_product_uom_category(self, name=None):
        if self.product:
            return self.product.default_uom_category.id

    @property
    def picking_location(self):
        return (
            self.rental.warehouse.rental_picking_location
            or self.rental.warehouse.storage_location)

    @property
    def return_location(self):
        return (
            self.rental.warehouse.rental_return_location
            or self.rental.warehouse.storage_location)

    @property
    def rental_location(self):
        return self.rental.warehouse.rental_location

    def get_moves(self, type):

        if self.product.type == 'service':
            return []

        if type == 'out' and self.outgoing_moves:
            return self.outgoing_moves
        elif type == 'in' and self.incoming_moves:
            return self.incoming_moves

        move = self.get_move(type)
        move.quantity = self.quantity
        move.unit = self.unit
        return [move]

    def get_move(self, type):
        pool = Pool()
        Move = pool.get('stock.move')

        move = Move()
        move.product = self.product
        if type == 'out':
            move.from_location = self.picking_location
            move.to_location = self.rental_location
            move.planned_date = to_date(self.start, self.company)
        elif type == 'in':
            move.from_location = self.rental_location
            move.to_location = self.return_location
            move.planned_date = to_date(self.end, self.company)
        move.state = 'draft'
        move.company = self.rental.company
        if move.on_change_with_unit_price_required():
            move.unit_price = self.unit_price * self.duration_unit
            move.currency = self.rental.currency
        move.origin = self.rental
        return move

    @property
    def to_invoice(self):
        return self.rental_state == 'done' and not self.invoice_lines

    @property
    def start_invoice(self):
        return self.start

    @property
    def end_invoice(self):
        return self.end

    @property
    def duration_invoice(self):
        return self.duration

    @property
    def duration_unit_invoice(self):
        pool = Pool()
        UoM = pool.get('product.uom')
        Data = pool.get('ir.model.data')
        hour = UoM(Data.get_id('product', 'uom_hour'))

        if duration := self.duration_invoice:
            duration = duration.total_seconds() / 60 / 60
        else:
            duration = 0
        if self.unit_price_unit:
            duration = UoM.compute_qty(
                hour, duration, self.unit_price_unit, round=False)
        return duration

    def get_invoice_lines(self):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')

        if self.rental_state != 'done' or self.invoice_lines:
            return []

        invoice_line = InvoiceLine(invoice_type='out', type='line')
        invoice_line.currency = self.rental.currency
        invoice_line.company = self.rental.company
        invoice_line.origin = self
        invoice_line.quantity = self.quantity
        invoice_line.unit = self.unit
        invoice_line.product = self.product
        invoice_line.unit_price = round_price(
            self.unit_price * Decimal(self.duration_unit_invoice))
        invoice_line.taxes = self.taxes
        invoice_line.account = self.product.account_rental_used
        return [invoice_line]

    def get_rec_name(self, name):
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang = Lang.get()
        converter = self.__class__.duration.converter
        quantity = lang.format_number_symbol(
            self.quantity, self.unit, digits=self.unit.digits)
        duration = Report.format_timedelta(
            self.duration, converter=converter, lang=lang)
        product = self.product.rec_name
        rental = self.rental.rec_name
        return f'{duration} × {quantity} {product} @ {rental}'

    @classmethod
    def search_rec_name(cls, name, clause):
        _, operator, value = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('rental.rec_name', *clause[1:]),
            ('product.rec_name', *clause[1:]),
            ]

    @classmethod
    def copy(cls, lines, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('actual_start')
        default.setdefault('actual_end')
        default.setdefault('invoice_lines')
        return super().copy(lines, default=default)

    @classmethod
    def check_modification(cls, mode, lines, values=None, external=False):
        super().check_modification(
            mode, lines, values=values, external=external)
        if mode == 'delete':
            for line in lines:
                if line.rental_state not in {'cancelled', 'draft'}:
                    raise AccessError(gettext(
                            'sale_rental.msg_rental_line_delete_cancel_draft',
                            line=line.rec_name,
                            rental=line.rental.rec_name))


class RentalLine_Tax(ModelSQL):
    __name__ = 'sale.rental.line-account.tax'

    line = fields.Many2One(
        'sale.rental.line', "Rental Line", ondelete='CASCADE', required=True)
    tax = fields.Many2One(
        'account.tax', "Tax", ondelete='RESTRICT', required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('line_tax_unique', Unique(t, t.line, t.tax),
                'sale_rental.msg_rental_line_tax_unique'),
            ]


class RentalLine_Outgoing_Move(ModelSQL):
    __name__ = 'sale.rental.line-outgoing-stock.move'

    line = fields.Many2One(
        'sale.rental.line', "Rental Line", ondelete='CASCADE', required=True)
    move = fields.Many2One(
        'stock.move', "Move", ondelete='RESTRICT', required=True,
        domain=[
            ('origin', 'like', 'sale.rental,%'),
            ('to_location.type', '=', 'rental'),
            ])


class RentalLine_Incoming_Move(ModelSQL):
    __name__ = 'sale.rental.line-incoming-stock.move'

    line = fields.Many2One(
        'sale.rental.line', "Rental Line", ondelete='CASCADE', required=True)
    move = fields.Many2One(
        'stock.move', "Move", ondelete='RESTRICT', required=True,
        domain=[
            ('origin', 'like', 'sale.rental,%'),
            ('from_location.type', '=', 'rental'),
            ])


class _RentalShowLine(ModelView):

    rental_line = fields.Many2One(
        'sale.rental.line', "Rental Line", readonly=True)
    product = fields.Function(
        fields.Many2One('product.product', "Product"),
        'on_change_with_product')
    quantity = fields.Function(
        fields.Float("Quantity", digits='unit'),
        'on_change_with_quantity')
    unit = fields.Function(
        fields.Many2One('product.uom', "Unit"),
        'on_change_with_unit')

    @classmethod
    def get(cls, rental_line):
        line = cls()
        line.rental_line = rental_line
        line.product = line.on_change_with_product()
        line.quantity = line.on_change_with_quantity()
        line.unit = line.on_change_with_unit()
        return line

    @fields.depends('rental_line')
    def on_change_with_product(self, name=None):
        if self.rental_line and self.rental_line.product:
            return self.rental_line.product.id

    @fields.depends('rental_line')
    def on_change_with_quantity(self, name=None):
        if self.rental_line:
            return self.rental_line.quantity

    @fields.depends('rental_line')
    def on_change_with_unit(self, name=None):
        if self.rental_line and self.rental_line.unit:
            return self.rental_line.unit.id

    def get_moves(self, type, date=None):
        if self.rental_line.product.type == 'service':
            return []

        move = self.rental_line.get_move(type)
        move.unit = self.unit
        move.effective_date = date
        return [move]


class RentalPickup(Wizard):
    __name__ = 'sale.rental.pickup'

    start = StateTransition()
    show = StateView('sale.rental.pickup.show',
        'sale_rental.sale_rental_pickup_show_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Pickup", 'pickup', 'tryton-ok', default=True),
            ])
    pickup = StateTransition()

    @property
    def rental_lines(self):
        for line in self.record.lines:
            if line.rental_state == 'confirmed':
                yield line

    def transition_start(self):
        if any(self.rental_lines):
            return 'show'
        else:
            self.record.try_picked_up()
            return 'end'

    def default_show(self, fields):
        pool = Pool()
        Line = pool.get('sale.rental.pickup.show.line')

        defaults = {}
        if 'start' in fields:
            defaults['start'] = min(
                map(partial(to_datetime, company=self.record.company),
                    (l.planned_start or l.planned_start_day
                        for l in self.rental_lines)),
                default=dt.datetime.now())
        if 'lines' in fields:
            defaults['lines'] = lines = []
            for rental_line in self.rental_lines:
                lines.append(Line.get(rental_line)._changed_values())
        return defaults

    def transition_pickup(self):
        pool = Pool()
        Lang = pool.get('ir.lang')
        Line = pool.get('sale.rental.line')
        Move = pool.get('stock.move')

        lang = Lang.get()
        rental_lines = []
        moves_to_delete = []
        outgoing_moves, incoming_moves = [], []
        for line in self.show.lines:
            rental_line = line.rental_line
            if rental_line in rental_lines:
                raise ValidationError(gettext(
                        'sale_rental.msg_rental_pickup_once',
                        line=rental_line.rec_name))
            rental_lines.append(rental_line)
            quantity = line.quantity_picked
            unit = rental_line.unit
            if not quantity:
                continue
            if not (0 <= quantity <= rental_line.quantity):
                raise ValidationError(gettext(
                        'sale_rental.msg_rental_pickup_quantity',
                        line=rental_line.rec_name,
                        quantity=lang.format_number_symbol(
                            rental_line.quantity, unit),
                        picked=lang.format_number_symbol(quantity, unit)))

            remaining = unit.round(rental_line.quantity - quantity)
            if remaining:
                with Transaction().set_context(_sale_rental_line_split=True):
                    Line.copy([rental_line], default={
                            'quantity': remaining,
                            'outgoing_moves': None,
                            'incoming_moves': None,
                            })

            rental_line.actual_start = self.show.start
            rental_line.quantity = quantity

            moves_to_delete.extend(rental_line.outgoing_moves)
            rental_line.outgoing_moves = line.get_moves(
                'out', date=self.show.start.date())
            outgoing_moves.extend(rental_line.outgoing_moves)
            moves_to_delete.extend(rental_line.incoming_moves)
            rental_line.incoming_moves = line.get_moves('in')
            incoming_moves.extend(rental_line.incoming_moves)

        Move.save(outgoing_moves + incoming_moves)
        Line.save(rental_lines)
        Move.delete(moves_to_delete)
        self.model.set_moves([self.record])
        Move.do(outgoing_moves)
        return 'end'


class RentalPickupShow(ModelView):
    __name__ = 'sale.rental.pickup.show'

    start = fields.DateTime("Start", format=_datetime_format, required=True)
    lines = fields.One2Many('sale.rental.pickup.show.line', 'parent', "Lines")


class RentalPickupShowLine(_RentalShowLine):
    __name__ = 'sale.rental.pickup.show.line'

    parent = fields.Many2One(
        'sale.rental.pickup.show', "Parent", readonly=True)

    quantity_picked = fields.Float(
        "Quantity Picked", digits='unit', required=True,
        domain=[
            ('quantity_picked', '<=', Eval('quantity')),
            ('quantity_picked', '>=', 0),
            ])

    @classmethod
    def get(cls, rental_line):
        line = super().get(rental_line)
        line.quantity_picked = 0
        return line

    def get_moves(self, type, date=None):
        moves = super().get_moves(type, date=date)
        for move in moves:
            move.quantity = self.quantity_picked
        return moves


class RentalReturn(Wizard):
    __name__ = 'sale.rental.return'

    start = StateTransition()
    show = StateView('sale.rental.return.show',
        'sale_rental.sale_rental_return_show_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Return", 'return_', 'tryton-ok', default=True),
            ])
    return_ = StateTransition()

    @property
    def rental_lines(self):
        for line in self.record.lines:
            if line.rental_state == 'picked up':
                yield line

    def transition_start(self):
        if any(self.rental_lines):
            return 'show'
        else:
            self.record.try_done()
            return 'end'

    def default_show(self, fields):
        pool = Pool()
        Line = pool.get('sale.rental.return.show.line')

        defaults = {}
        if 'end' in fields:
            defaults['end'] = max(
                map(partial(
                        to_datetime, company=self.record.company,
                        time=_time_max),
                    (l.planned_end or l.planned_end_day
                        for l in self.rental_lines)),
                default=dt.datetime.now())
        if 'lines' in fields:
            defaults['lines'] = lines = []
            for rental_line in self.rental_lines:
                lines.append(Line.get(rental_line)._changed_values())
        return defaults

    def transition_return_(self):
        pool = Pool()
        Lang = pool.get('ir.lang')
        Line = pool.get('sale.rental.line')
        Move = pool.get('stock.move')

        lang = Lang.get()
        rental_lines = []
        moves_to_delete = []
        incoming_moves = []
        for line in self.show.lines:
            rental_line = line.rental_line
            if rental_line in rental_lines:
                raise ValidationError(gettext(
                        'sale_rental.msg_rental_return_once',
                        line=rental_line.rec_name))
            rental_lines.append(rental_line)
            quantity = line.quantity_returned
            unit = rental_line.unit
            if not quantity:
                continue
            if not (0 <= quantity <= rental_line.quantity):
                raise ValidationError(gettext(
                        'sale_rental.msg_rental_return_quantity',
                        line=rental_line.rec_name,
                        quantity=lang.format_number_symbol(
                            rental_line.quantity, unit),
                        returned=lang.format_number_symbol(quantity, unit)))

            remaining = unit.round(rental_line.quantity - quantity)
            if remaining:
                with Transaction().set_context(_sale_rental_line_split=True):
                    Line.copy([rental_line], default={
                            'quantity': remaining,
                            'actual_start': rental_line.actual_start,
                            'incoming_moves': None,
                            })

            rental_line.actual_end = self.show.end
            rental_line.quantity = quantity

            moves_to_delete.extend(rental_line.incoming_moves)
            rental_line.incoming_moves = line.get_moves(
                'in', date=self.show.end.date())
            incoming_moves.extend(rental_line.incoming_moves)

        Move.save(incoming_moves)
        Line.save(rental_lines)
        Move.delete(moves_to_delete)
        self.model.set_moves([self.record])
        Move.do(incoming_moves)
        return 'end'


class RentalReturnShow(ModelView):
    __name__ = 'sale.rental.return.show'

    end = fields.DateTime("End", format=_datetime_format, required=True)
    lines = fields.One2Many('sale.rental.return.show.line', 'parent', "Lines")


class RentalReturnShowLine(_RentalShowLine):
    __name__ = 'sale.rental.return.show.line'

    parent = fields.Many2One(
        'sale.rental.return.show', "Parent", readonly=True)

    quantity_returned = fields.Float(
        "Quantity Returned", digits='unit', required=True,
        domain=[
            ('quantity_returned', '<=', Eval('quantity')),
            ('quantity_returned', '>=', 0),
            ])

    @classmethod
    def get(cls, rental_line):
        line = super().get(rental_line)
        line.quantity_returned = 0
        return line

    def get_moves(self, type, date=None):
        moves = super().get_moves(type, date=date)
        for move in moves:
            move.quantity = self.quantity_returned
        return moves
