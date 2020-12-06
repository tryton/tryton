# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from itertools import groupby

from sql import operators, Literal, Null
from sql.conditionals import Coalesce, Case

from trytond import backend
from trytond.i18n import gettext
from trytond.model import ModelSQL, ModelView, Workflow, fields, \
        sequence_ordered
from trytond.model.exceptions import AccessError
from trytond.pool import Pool
from trytond.pyson import Eval, If, Bool
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateAction, StateTransition, \
        Button

from trytond.modules.company.model import (
    employee_field, set_employee, reset_employee)
from trytond.modules.product import price_digits, round_price
from .exceptions import InvoiceError


class Subscription(Workflow, ModelSQL, ModelView):
    "Subscription"
    __name__ = 'sale.subscription'
    _rec_name = 'number'

    company = fields.Many2One(
        'company.company', "Company", required=True, select=True,
        states={
            'readonly': Eval('state') != 'draft',
            },
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        depends=['state'],
        help="Make the subscription belong to the company.")

    number = fields.Char(
        "Number", readonly=True, select=True,
        help="The main identification of the subscription.")
    # TODO revision
    reference = fields.Char(
        "Reference", select=True,
        help="The identification of an external origin.")
    description = fields.Char("Description",
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])

    party = fields.Many2One(
        'party.party', "Party", required=True,
        states={
            'readonly': ((Eval('state') != 'draft')
                | (Eval('lines', [0]) & Eval('party'))),
            },
        depends=['state'],
        help="The party who subscribes.")
    contact = fields.Many2One(
        'party.contact_mechanism', "Contact",
        search_context={
            'related_party': Eval('party'),
            })
    invoice_party = fields.Many2One('party.party', "Invoice Party",
        states={
            'readonly': ((Eval('state') != 'draft')
                | Eval('lines', [0])),
            },
        depends=['state'])
    invoice_address = fields.Many2One(
        'party.address', "Invoice Address",
        domain=[
            ('party', '=', If(Bool(Eval('invoice_party',)),
                    Eval('invoice_party'), Eval('party'))),
            ],
        states={
            'readonly': Eval('state') != 'draft',
            'required': ~Eval('state').in_(['draft']),
            },
        depends=['party', 'invoice_party', 'state'])
    payment_term = fields.Many2One(
        'account.invoice.payment_term', "Payment Term",
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])

    currency = fields.Many2One(
        'currency.currency', "Currency", required=True,
        states={
            'readonly': ((Eval('state') != 'draft')
                | (Eval('lines', [0]) & Eval('currency', 0))),
            },
        depends=['state'])

    start_date = fields.Date(
        "Start Date", required=True,
        states={
            'readonly': ((Eval('state') != 'draft')
                | Eval('next_invoice_date')),
            },
        depends=['state', 'next_invoice_date'])
    end_date = fields.Date(
        "End Date",
        domain=['OR',
            ('end_date', '>=', If(
                    Bool(Eval('start_date')),
                    Eval('start_date', datetime.date.min),
                    datetime.date.min)),
            ('end_date', '=', None),
            ],
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['start_date', 'state'])

    invoice_recurrence = fields.Many2One(
        'sale.subscription.recurrence.rule.set', "Invoice Recurrence",
        required=True,
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])
    invoice_start_date = fields.Date("Invoice Start Date",
        states={
            'readonly': ((Eval('state') != 'draft')
                | Eval('next_invoice_date')),
            },
        depends=['state', 'next_invoice_date'])
    next_invoice_date = fields.Date("Next Invoice Date", readonly=True)

    lines = fields.One2Many(
        'sale.subscription.line', 'subscription', "Lines",
        states={
            'readonly': ((Eval('state') != 'draft')
                | ~Eval('start_date')),
            },
        depends=['state'])

    quoted_by = employee_field(
        "Quoted By", states=['quotation', 'running', 'closed', 'canceled'])
    run_by = employee_field(
        "Run By", states=['running', 'closed', 'canceled'])
    state = fields.Selection([
            ('draft', "Draft"),
            ('quotation', "Quotation"),
            ('running', "Running"),
            ('closed', "Closed"),
            ('canceled', "Canceled"),
            ], "State", readonly=True, required=True,
        help="The current state of the subscription.")

    @classmethod
    def __setup__(cls):
        super(Subscription, cls).__setup__()
        cls._order = [
            ('start_date', 'DESC'),
            ('id', 'DESC'),
            ]
        cls._transitions |= set((
                ('draft', 'canceled'),
                ('draft', 'quotation'),
                ('quotation', 'canceled'),
                ('quotation', 'draft'),
                ('quotation', 'running'),
                ('running', 'draft'),
                ('running', 'closed'),
                ('canceled', 'draft'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': ~Eval('state').in_(['draft', 'quotation']),
                    'icon': 'tryton-cancel',
                    'depends': ['state'],
                    },
                'draft': {
                    'invisible': Eval('state').in_(['draft', 'closed']),
                    'icon': If(Eval('state') == 'canceled',
                        'tryton-undo', 'tryton-back'),
                    'depends': ['state'],
                    },
                'quote': {
                    'invisible': Eval('state') != 'draft',
                    'readonly': ~Eval('lines', []),
                    'icon': 'tryton-forward',
                    'depends': ['state'],
                    },
                'run': {
                    'invisible': Eval('state') != 'quotation',
                    'icon': 'tryton-forward',
                    'depends': ['state'],
                    },
                })

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_currency(cls):
        pool = Pool()
        Company = pool.get('company.company')
        company = cls.default_company()
        if company:
            return Company(company).currency.id

    @classmethod
    def default_state(cls):
        return 'draft'

    @fields.depends('party', 'invoice_party')
    def on_change_party(self):
        if not self.invoice_party:
            self.invoice_address = None
        if self.party:
            if not self.invoice_party:
                self.invoice_address = self.party.address_get(type='invoice')
            self.payment_term = self.party.customer_payment_term

    @fields.depends('party', 'invoice_party')
    def on_change_invoice_party(self):
        if self.invoice_party:
            self.invoice_address = self.invoice_party.address_get(
                type='invoice')
        elif self.party:
            self.invoice_address = self.party.address_get(type='invoice')

    @classmethod
    def set_number(cls, subscriptions):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Config = pool.get('sale.configuration')

        config = Config(1)
        for subscription in subscriptions:
            if subscription.number:
                continue
            subscription.number = Sequence.get_id(
                config.subscription_sequence.id)
        cls.save(subscriptions)

    def compute_next_invoice_date(self):
        start_date = self.invoice_start_date or self.start_date
        date = self.next_invoice_date or start_date
        rruleset = self.invoice_recurrence.rruleset(start_date)
        dt = datetime.datetime.combine(date, datetime.time())
        inc = (start_date == date) and not self.next_invoice_date
        next_date = rruleset.after(dt, inc=inc)
        return next_date.date()

    @classmethod
    def copy(cls, subscriptions, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('number', None)
        default.setdefault('next_invoice_date', None)
        return super(Subscription, cls).copy(subscriptions, default=default)

    @classmethod
    def view_attributes(cls):
        return [
            ('/tree', 'visual', If(Eval('state') == 'canceled', 'muted', '')),
            ]

    @classmethod
    @ModelView.button
    @Workflow.transition('canceled')
    def cancel(cls, subscriptions):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    @reset_employee('quoted_by', 'run_by')
    def draft(cls, subscriptions):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('quotation')
    @set_employee('quoted_by')
    def quote(cls, subscriptions):
        cls.set_number(subscriptions)

    @classmethod
    @ModelView.button
    @Workflow.transition('running')
    @set_employee('run_by')
    def run(cls, subscriptions):
        pool = Pool()
        Line = pool.get('sale.subscription.line')
        lines = []
        for subscription in subscriptions:
            if not subscription.next_invoice_date:
                subscription.next_invoice_date = (
                    subscription.compute_next_invoice_date())
            for line in subscription.lines:
                if (line.next_consumption_date is None
                        and not line.consumed_until):
                    line.next_consumption_date = (
                        line.compute_next_consumption_date())
            lines.extend(subscription.lines)
        Line.save(lines)
        cls.save(subscriptions)

    @classmethod
    def process(cls, subscriptions):
        to_close = []
        for subscription in subscriptions:
            if all(l.next_consumption_date is None
                    for l in subscription.lines):
                to_close.append(subscription)
        cls.close(to_close)

    @classmethod
    @Workflow.transition('closed')
    def close(cls, subscriptions):
        for subscription in subscriptions:
            if not subscription.end_date and subscription.lines:
                subscription.end_date = max(
                    l.end_date for l in subscription.lines)
        cls.save(subscriptions)

    @classmethod
    def generate_invoice(cls, date=None):
        pool = Pool()
        Date = pool.get('ir.date')
        Consumption = pool.get('sale.subscription.line.consumption')
        Invoice = pool.get('account.invoice')
        InvoiceLine = pool.get('account.invoice.line')

        if date is None:
            date = Date.today()

        consumptions = Consumption.search([
                ('invoice_line', '=', None),
                ('line.subscription.next_invoice_date', '<=', date),
                ('line.subscription.state', 'in', ['running', 'closed']),
                ('line.subscription.company', '=',
                    Transaction().context.get('company')),
                ],
            order=[
                ('line.subscription.id', 'DESC'),
                ])

        def keyfunc(consumption):
            return consumption.line.subscription
        invoices = {}
        lines = {}
        for subscription, consumptions in groupby(consumptions, key=keyfunc):
            invoices[subscription] = invoice = subscription._get_invoice()
            lines[subscription] = Consumption.get_invoice_lines(
                consumptions, invoice)

        all_invoices = list(invoices.values())
        Invoice.save(all_invoices)

        all_invoice_lines = []
        for subscription, invoice in invoices.items():
            invoice_lines, _ = lines[subscription]
            for line in invoice_lines:
                line.invoice = invoice
            all_invoice_lines.extend(invoice_lines)
        InvoiceLine.save(all_invoice_lines)

        all_consumptions = []
        for values in lines.values():
            for invoice_line, consumptions in zip(*values):
                for consumption in consumptions:
                    assert not consumption.invoice_line
                    consumption.invoice_line = invoice_line
                    all_consumptions.append(consumption)
        Consumption.save(all_consumptions)

        Invoice.update_taxes(all_invoices)

        subscriptions = cls.search([
                ('next_invoice_date', '<=', date),
                ])
        for subscription in subscriptions:
            if subscription.state == 'running':
                while subscription.next_invoice_date <= date:
                    subscription.next_invoice_date = (
                        subscription.compute_next_invoice_date())
            else:
                subscription.next_invoice_date = None
        cls.save(subscriptions)

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
        invoice.on_change_type()
        invoice.payment_term = self.payment_term
        return invoice


class Line(sequence_ordered(), ModelSQL, ModelView):
    "Subscription Line"
    __name__ = 'sale.subscription.line'

    subscription = fields.Many2One(
        'sale.subscription', "Subscription", required=True, select=True,
        ondelete='CASCADE',
        states={
            'readonly': ((Eval('subscription_state') != 'draft')
                & Bool(Eval('subscription'))),
            },
        depends=['subscription_state'],
        help="Add the line below the subscription.")
    subscription_state = fields.Function(
        fields.Selection('get_subscription_states', "Subscription State"),
        'on_change_with_subscription_state')
    subscription_start_date = fields.Function(
        fields.Date("Subscription Start Date"),
        'on_change_with_subscription_start_date')
    subscription_end_date = fields.Function(
        fields.Date("Subscription End Date"),
        'on_change_with_subscription_end_date')
    company = fields.Function(
        fields.Many2One('company.company', "Company"),
        'on_change_with_company')

    service = fields.Many2One(
        'sale.subscription.service', "Service", required=True,
        states={
            'readonly': Eval('subscription_state') != 'draft',
            },
        context={
            'company': Eval('company', None),
            },
        depends=['subscription_state', 'company'])
    description = fields.Text("Description",
        states={
            'readonly': Eval('subscription_state') != 'draft',
            },
        depends=['subscription_state'])

    quantity = fields.Float(
        "Quantity", digits=(16, Eval('unit_digits', 2)),
        states={
            'readonly': Eval('subscription_state') != 'draft',
            'required': Bool(Eval('consumption_recurrence')),
            },
        depends=[
            'unit_digits', 'subscription_state', 'consumption_recurrence'])
    unit = fields.Many2One(
        'product.uom', "Unit", required=True,
        states={
            'readonly': Eval('subscription_state') != 'draft',
            },
        domain=[
            If(Bool(Eval('service_unit_category')),
                ('category', '=', Eval('service_unit_category')),
                ('category', '!=', -1)),
            ],
        depends=['subscription_state', 'service_unit_category'])
    unit_digits = fields.Function(
        fields.Integer("Unit Digits"), 'on_change_with_unit_digits')
    service_unit_category = fields.Function(
        fields.Many2One('product.uom.category', "Service Unit Category"),
        'on_change_with_service_unit_category')

    unit_price = fields.Numeric(
        "Unit Price", digits=price_digits,
        states={
            'readonly': Eval('subscription_state') != 'draft',
            },
        depends=['subscription_state'])

    consumption_recurrence = fields.Many2One(
        'sale.subscription.recurrence.rule.set', "Consumption Recurrence",
        states={
            'readonly': Eval('subscription_state') != 'draft',
            },
        depends=['subscription_state'])
    consumption_delay = fields.TimeDelta(
        "Consumption Delay",
        states={
            'readonly': Eval('subscription_state') != 'draft',
            'invisible': ~Eval('consumption_recurrence'),
            },
        depends=['subscription_state', 'consumption_recurrence'])
    next_consumption_date = fields.Date("Next Consumption Date", readonly=True)
    next_consumption_date_delayed = fields.Function(
        fields.Date("Next Consumption Delayed"),
        'get_next_consumption_date_delayed')
    consumed_until = fields.Date("Consumed until", readonly=True)
    start_date = fields.Date(
        "Start Date", required=True,
        domain=[
            ('start_date', '>=', Eval('subscription_start_date')),
            ],
        states={
            'readonly': ((Eval('subscription_state') != 'draft')
                | Eval('consumed_until')),
            },
        depends=[
            'subscription_start_date', 'subscription_state', 'consumed_until'])
    end_date = fields.Date(
        "End Date",
        domain=['OR', [
                ('end_date', '>=', Eval('start_date')),
                If(Bool(Eval('subscription_end_date')),
                    ('end_date', '<=', Eval('subscription_end_date')),
                    ()),
                If(Bool(Eval('consumed_until')),
                    ('end_date', '>=', Eval('consumed_until')),
                    ()),
                ],
            ('end_date', '=', None),
            ],
        states={
            'readonly': ((Eval('subscription_state') != 'draft')
                | (~Eval('consumed_until') & Eval('consumed_until'))),
            },
        depends=['subscription_end_date', 'start_date',
            'consumed_until', 'subscription_state', 'consumed_until'])

    @classmethod
    def __register__(cls, module):
        pool = Pool()
        Subscription = pool.get('sale.subscription')
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        table = cls.__table__()
        subscription = Subscription.__table__()

        # Migration from 4.8: start_date required
        if backend.TableHandler.table_exist(cls._table):
            table_h = cls.__table_handler__(module)
            if table_h.column_exist('start_date'):
                cursor.execute(*table.update(
                        [table.start_date],
                        subscription.select(
                            subscription.start_date,
                            where=subscription.id == table.subscription),
                        where=table.start_date == Null))

        super(Line, cls).__register__(module)
        table_h = cls.__table_handler__(module)

        # Migration from 4.8: drop required on description
        table_h.not_null_action('description', action='remove')

        # Migration from 5.2: replace consumed by consumed_until
        if table_h.column_exist('consumed'):
            cursor.execute(*table.update(
                    [table.consumed_until],
                    [Case((table.consumed, Coalesce(
                                    table.next_consumption_date,
                                    table.end_date)), else_=Null)]))
            table_h.drop_column('consumed')

    @classmethod
    def get_subscription_states(cls):
        pool = Pool()
        Subscription = pool.get('sale.subscription')
        return Subscription.fields_get(['state'])['state']['selection']

    @fields.depends('subscription', '_parent_subscription.state')
    def on_change_with_subscription_state(self, name=None):
        if self.subscription:
            return self.subscription.state

    @fields.depends('subscription', '_parent_subscription.start_date')
    def on_change_with_subscription_start_date(self, name=None):
        if self.subscription:
            return self.subscription.start_date

    @fields.depends('subscription', '_parent_subscription.end_date')
    def on_change_with_subscription_end_date(self, name=None):
        if self.subscription:
            return self.subscription.end_date

    @fields.depends('subscription', '_parent_subscription.company')
    def on_change_with_company(self, name=None):
        if self.subscription and self.subscription.company:
            return self.subscription.company.id

    @fields.depends('subscription', 'start_date', 'end_date',
        '_parent_subscription.start_date', '_parent_subscription.end_date')
    def on_change_subscription(self):
        if self.subscription:
            if not self.start_date:
                self.start_date = self.subscription.start_date
            if not self.end_date:
                self.end_date = self.subscription.end_date

    @classmethod
    def default_quantity(cls):
        return 1

    @fields.depends('unit')
    def on_change_with_unit_digits(self, name=None):
        if self.unit:
            return self.unit.digits
        return 2

    @fields.depends('service')
    def on_change_with_service_unit_category(self, name=None):
        if self.service:
            return self.service.product.default_uom_category.id

    @fields.depends('service', 'quantity', 'unit',
        'subscription', '_parent_subscription.party',
        methods=['_get_context_sale_price'])
    def on_change_service(self):
        pool = Pool()
        Product = pool.get('product.product')

        if not self.service:
            self.consumption_recurrence = None
            self.consumption_delay = None
            return

        party = None
        party_context = {}
        if self.subscription and self.subscription.party:
            party = self.subscription.party
            if party.lang:
                party_context['language'] = party.lang.code

        product = self.service.product
        category = product.sale_uom.category
        if not self.unit or self.unit.category != category:
            self.unit = product.sale_uom
            self.unit_digits = product.sale_uom.digits

        with Transaction().set_context(self._get_context_sale_price()):
            self.unit_price = Product.get_sale_price(
                [product], self.quantity or 0)[product.id]
            if self.unit_price:
                self.unit_price = round_price(self.unit_price)

        self.consumption_recurrence = self.service.consumption_recurrence
        self.consumption_delay = self.service.consumption_delay

    @fields.depends('subscription', '_parent_subscription.currency',
        '_parent_subscription.party', 'start_date', 'unit', 'service',
        'company')
    def _get_context_sale_price(self):
        context = {}
        if self.subscription:
            if self.subscription.currency:
                context['currency'] = self.subscription.currency.id
            if self.subscription.party:
                context['customer'] = self.subscription.party.id
            if self.start_date:
                context['sale_date'] = self.start_date
        if self.unit:
            context['uom'] = self.unit.id
        elif self.service:
            context['uom'] = self.service.sale_uom.id
        if self.company:
            context['company'] = self.company.id
        # TODO tax
        return context

    def get_next_consumption_date_delayed(self, name=None):
        if self.next_consumption_date and self.consumption_delay:
            return self.next_consumption_date + self.consumption_delay
        return self.next_consumption_date

    def get_rec_name(self, name):
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang = Lang.get()
        return (lang.format(
                '%.*f', (self.unit.digits, self.quantity or 0))
            + '%s %s @ %s' % (
                self.unit.symbol, self.service.rec_name,
                self.subscription.rec_name))

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            ('subscription.rec_name',) + tuple(clause[1:]),
            ('service.rec_name',) + tuple(clause[1:]),
            ]

    @classmethod
    def domain_next_consumption_date_delayed(cls, domain, tables):
        field = cls.next_consumption_date_delayed._field
        table, _ = tables[None]
        name, operator, value = domain
        Operator = fields.SQL_OPERATORS[operator]
        column = (
            table.next_consumption_date + Coalesce(
                table.consumption_delay, datetime.timedelta()))
        expression = Operator(column, field._domain_value(operator, value))
        if isinstance(expression, operators.In) and not expression.right:
            expression = Literal(False)
        elif isinstance(expression, operators.NotIn) and not expression.right:
            expression = Literal(True)
        expression = field._domain_add_null(
            column, operator, value, expression)
        return expression

    @classmethod
    def generate_consumption(cls, date=None):
        pool = Pool()
        Date = pool.get('ir.date')
        Consumption = pool.get('sale.subscription.line.consumption')
        Subscription = pool.get('sale.subscription')

        if date is None:
            date = Date.today()

        remainings = all_lines = cls.search([
                ('consumption_recurrence', '!=', None),
                ('next_consumption_date_delayed', '<=', date),
                ('subscription.state', '=', 'running'),
                ('subscription.company', '=',
                    Transaction().context.get('company')),
                ])

        consumptions = []
        subscription_ids = set()
        while remainings:
            lines, remainings = remainings, []
            for line in lines:
                consumption = line.get_consumption(line.next_consumption_date)
                if consumption:
                    consumptions.append(consumption)
                line.next_consumption_date = (
                    line.compute_next_consumption_date())
                if line.next_consumption_date:
                    line.consumed_until = (
                        line.next_consumption_date - datetime.timedelta(1))
                else:
                    line.consumed_until = line.end_date
                if line.next_consumption_date is None:
                    subscription_ids.add(line.subscription.id)
                elif line.get_next_consumption_date_delayed() <= date:
                    remainings.append(line)

        Consumption.save(consumptions)
        cls.save(all_lines)
        Subscription.process(Subscription.browse(list(subscription_ids)))

    def get_consumption(self, date):
        pool = Pool()
        Consumption = pool.get('sale.subscription.line.consumption')
        end_date = self.end_date or self.subscription.end_date
        if date < (end_date or datetime.date.max):
            return Consumption(line=self, quantity=self.quantity, date=date)

    def compute_next_consumption_date(self):
        if not self.consumption_recurrence:
            return None
        date = self.next_consumption_date or self.start_date
        rruleset = self.consumption_recurrence.rruleset(self.start_date)
        dt = datetime.datetime.combine(date, datetime.time())
        inc = (self.start_date == date) and not self.next_consumption_date
        next_date = rruleset.after(dt, inc=inc).date()
        for end_date in [self.end_date, self.subscription.end_date]:
            if end_date:
                if next_date > end_date:
                    return None
        return next_date

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('next_consumption_date', None)
        default.setdefault('consumed', None)
        default.setdefault('consumed_until', None)
        return super(Line, cls).copy(lines, default=default)


class LineConsumption(ModelSQL, ModelView):
    "Subscription Line Consumption"
    __name__ = 'sale.subscription.line.consumption'

    line = fields.Many2One(
        'sale.subscription.line', "Line", required=True, select=True,
        ondelete='RESTRICT')
    quantity = fields.Float(
        "Quantity", digits=(16, Eval('unit_digits', 2)),
        depends=['unit_digits'])
    unit_digits = fields.Function(
        fields.Integer("Unit Digits"), 'on_change_with_unit_digits')
    date = fields.Date("Date", required=True)
    invoice_line = fields.Many2One(
        'account.invoice.line', "Invoice Line", readonly=True)

    @classmethod
    def __setup__(cls):
        super(LineConsumption, cls).__setup__()
        cls._order.insert(0, ('date', 'DESC'))

    @fields.depends('line')
    def on_change_with_unit_digits(self, name=None):
        if self.line and self.line.unit:
            return self.line.unit.digits
        return 2

    @classmethod
    def copy(cls, consumptions, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('invoice_line', None)
        return super(LineConsumption, cls).copy(consumptions, default=default)

    @classmethod
    def write(cls, *args):
        for consumptions in args[::2]:
            for consumption in consumptions:
                if consumption.invoice_line:
                    raise AccessError(
                        gettext('sale_subscription'
                            '.msg_consumption_modify_invoiced',
                            consumption=consumption.rec_name))
        super(LineConsumption, cls).write(*args)

    @classmethod
    def delete(cls, consumptions):
        for consumption in consumptions:
            if consumption.invoice_line:
                raise AccessError(
                    gettext('sale_subscription'
                        '.msg_consumption_modify_invoiced',
                        consumption=consumption.rec_name))
        super(LineConsumption, cls).delete(consumptions)

    @classmethod
    def get_invoice_lines(cls, consumptions, invoice):
        "Return a list of lines and a list of consumptions"
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')

        lines, grouped_consumptions = [], []
        consumptions = sorted(consumptions, key=cls._group_invoice_key)
        for key, sub_consumptions in groupby(
                consumptions, key=cls._group_invoice_key):
            sub_consumptions = list(sub_consumptions)
            line = InvoiceLine(**dict(key))
            line.invoice_type = 'out'
            line.type = 'line'
            line.quantity = sum(c.quantity for c in sub_consumptions)

            line.account = line.product.account_revenue_used
            if not line.account:
                raise InvoiceError(
                    gettext('sale_subscription'
                        '.msg_consumption_invoice_missing_account_revenue',
                        product=line.product.rec_name))

            taxes = []
            pattern = line._get_tax_rule_pattern()
            party = invoice.party
            for tax in line.product.customer_taxes_used:
                if party.customer_tax_rule:
                    tax_ids = party.customer_tax_rule.apply(tax, pattern)
                    if tax_ids:
                        taxes.extend(tax_ids)
                    continue
                taxes.append(tax.id)
            if party.customer_tax_rule:
                tax_ids = party.customer_tax_rule.apply(None, pattern)
                if tax_ids:
                    taxes.extend(tax_ids)
            line.taxes = taxes

            lines.append(line)
            grouped_consumptions.append(sub_consumptions)
        return lines, grouped_consumptions

    @classmethod
    def _group_invoice_key(cls, consumption):
        return (
            ('company', consumption.line.subscription.company),
            ('unit', consumption.line.unit),
            ('product', consumption.line.service.product),
            ('unit_price', consumption.line.unit_price),
            ('description', consumption.line.description),
            ('origin', consumption.line),
            )


class CreateLineConsumption(Wizard):
    "Create Subscription Line Consumption"
    __name__ = 'sale.subscription.line.consumption.create'
    start = StateView(
        'sale.subscription.line.consumption.create.start',
        'sale_subscription.line_consumption_create_start_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Create", 'create_', 'tryton-ok', default=True),
            ])
    create_ = StateAction(
        'sale_subscription.act_subscription_line_consumption_form')

    def do_create_(self, action):
        pool = Pool()
        Line = pool.get('sale.subscription.line')
        Line.generate_consumption(date=self.start.date)
        return action, {}

    def transition_create_(self):
        return 'end'


class CreateLineConsumptionStart(ModelView):
    "Create Subscription Line Consumption"
    __name__ = 'sale.subscription.line.consumption.create.start'

    date = fields.Date("Date")

    @classmethod
    def default_date(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()


class CreateSubscriptionInvoice(Wizard):
    "Create Subscription Invoice"
    __name__ = 'sale.subscription.create_invoice'
    start = StateView(
        'sale.subscription.create_invoice.start',
        'sale_subscription.create_invoice_start_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Create", 'create_', 'tryton-ok', default=True),
            ])
    create_ = StateTransition()

    def transition_create_(self):
        pool = Pool()
        Subscription = pool.get('sale.subscription')
        Subscription.generate_invoice(date=self.start.date)
        return 'end'


class CreateSubscriptionInvoiceStart(ModelView):
    "Create Subscription Invoice"
    __name__ = 'sale.subscription.create_invoice.start'

    date = fields.Date("Date")

    @classmethod
    def default_date(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()
