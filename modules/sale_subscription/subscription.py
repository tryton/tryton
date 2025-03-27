# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from itertools import groupby

from sql import Literal, Null, operators
from sql.conditionals import Case, Coalesce
from sql.functions import CharLength

from trytond.i18n import gettext
from trytond.model import (
    Index, ModelSQL, ModelView, Workflow, fields, sequence_ordered)
from trytond.model.exceptions import AccessError
from trytond.modules.company.model import (
    employee_field, reset_employee, set_employee)
from trytond.modules.currency.fields import Monetary
from trytond.modules.product import price_digits
from trytond.pool import Pool
from trytond.pyson import Bool, Eval, If
from trytond.tools import sortable_values
from trytond.transaction import Transaction
from trytond.wizard import (
    Button, StateAction, StateTransition, StateView, Wizard)

from .exceptions import InvalidRecurrence, InvoiceError


class Subscription(Workflow, ModelSQL, ModelView):
    "Subscription"
    __name__ = 'sale.subscription'
    _rec_name = 'number'

    company = fields.Many2One(
        'company.company', "Company", required=True,
        states={
            'readonly': (
                (Eval('state') != 'draft')
                | Eval('lines', [0])
                | Eval('party', True)
                | Eval('invoice_party', True)),
            },
        help="Make the subscription belong to the company.")

    number = fields.Char(
        "Number", readonly=True,
        help="The main identification of the subscription.")
    reference = fields.Char(
        "Reference",
        help="The identification of an external origin.")
    description = fields.Char("Description",
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
        depends={'company'},
        help="The party who subscribes.")
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
            ('party', '=', If(Bool(Eval('invoice_party',)),
                    Eval('invoice_party'), Eval('party'))),
            ],
        states={
            'readonly': Eval('state') != 'draft',
            'required': ~Eval('state').in_(['draft']),
            })
    payment_term = fields.Many2One(
        'account.invoice.payment_term', "Payment Term", ondelete='RESTRICT',
        states={
            'readonly': Eval('state') != 'draft',
            })

    currency = fields.Many2One(
        'currency.currency', "Currency", required=True,
        states={
            'readonly': ((Eval('state') != 'draft')
                | (Eval('lines', [0]) & Eval('currency', 0))),
            })

    start_date = fields.Date(
        "Start Date", required=True,
        states={
            'readonly': ((Eval('state') != 'draft')
                | Eval('next_invoice_date')),
            })
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
            })

    invoice_recurrence = fields.Many2One(
        'sale.subscription.recurrence.rule.set', "Invoice Recurrence",
        required=True,
        states={
            'readonly': Eval('state') != 'draft',
            })
    invoice_start_date = fields.Date("Invoice Start Date",
        states={
            'readonly': ((Eval('state') != 'draft')
                | Eval('next_invoice_date')),
            })
    next_invoice_date = fields.Date(
        "Next Invoice Date", readonly=True,
        states={
            'invisible': Eval('state') != 'running',
            })

    lines = fields.One2Many(
        'sale.subscription.line', 'subscription', "Lines",
        states={
            'readonly': (
                (Eval('state') != 'draft')
                | ~Eval('start_date')
                | ~Eval('company')
                | ~Eval('currency')),
            })

    quoted_by = employee_field(
        "Quoted By", states=['quotation', 'running', 'closed', 'cancelled'])
    run_by = employee_field(
        "Run By", states=['running', 'closed', 'cancelled'])
    state = fields.Selection([
            ('draft', "Draft"),
            ('quotation', "Quotation"),
            ('running', "Running"),
            ('closed', "Closed"),
            ('cancelled', "Cancelled"),
            ], "State", readonly=True, required=True, sort=False,
        help="The current state of the subscription.")

    @classmethod
    def __setup__(cls):
        cls.number.search_unaccented = False
        cls.reference.search_unaccented = False
        super(Subscription, cls).__setup__()
        t = cls.__table__()
        cls._sql_indexes.update({
                Index(t, (t.reference, Index.Similarity())),
                Index(
                    t,
                    (t.state, Index.Equality()),
                    where=t.state.in_(['draft', 'quotation', 'running'])),
                })
        cls._order = [
            ('start_date', 'DESC'),
            ('id', 'DESC'),
            ]
        cls._transitions |= set((
                ('draft', 'cancelled'),
                ('draft', 'quotation'),
                ('quotation', 'cancelled'),
                ('quotation', 'draft'),
                ('quotation', 'running'),
                ('running', 'draft'),
                ('running', 'closed'),
                ('cancelled', 'draft'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': ~Eval('state').in_(['draft', 'quotation']),
                    'icon': 'tryton-cancel',
                    'depends': ['state'],
                    },
                'draft': {
                    'invisible': Eval('state').in_(['draft', 'closed']),
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
                'run': {
                    'invisible': Eval('state') != 'quotation',
                    'icon': 'tryton-forward',
                    'depends': ['state'],
                    },
                })

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        table = cls.__table__()

        super().__register__(module_name)

        # Migration from 5.6: rename state canceled to cancelled
        cursor.execute(*table.update(
                [table.state], ['cancelled'],
                where=table.state == 'canceled'))

    @classmethod
    def order_number(cls, tables):
        table, _ = tables[None]
        return [
            ~((table.state == 'cancelled') & (table.number == Null)),
            CharLength(table.number), table.number]

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

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
    def set_number(cls, subscriptions):
        pool = Pool()
        Config = pool.get('sale.configuration')

        config = Config(1)
        for subscription in subscriptions:
            if subscription.number:
                continue
            subscription.number = config.get_multivalue(
                'subscription_sequence',
                company=subscription.company.id).get()
        cls.save(subscriptions)

    def compute_next_invoice_date(self):
        start_date = self.invoice_start_date or self.start_date
        date = self.next_invoice_date or start_date
        rruleset = self.invoice_recurrence.rruleset(start_date)
        dt = datetime.datetime.combine(date, datetime.time())
        inc = (start_date == date) and not self.next_invoice_date
        next_date = rruleset.after(dt, inc=inc)
        if next_date:
            return next_date.date()

    @classmethod
    def validate_fields(cls, subscriptions, field_names):
        super().validate_fields(subscriptions, field_names)
        cls.validate_invoice_recurrence(subscriptions, field_names)

    @classmethod
    def validate_invoice_recurrence(cls, subscriptions, field_names=None):
        if field_names and not (field_names & {
                    'start_date', 'invoice_start_date', 'invoice_recurrence'}):
            return
        for subscription in subscriptions:
            start_date = (
                subscription.invoice_start_date or subscription.start_date)
            try:
                subscription.invoice_recurrence.rruleset(start_date)[0]
            except IndexError:
                raise InvalidRecurrence(gettext(
                        'sale_subscription.msg_invoice_recurrence_invalid',
                        subscription=subscription.rec_name))

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
    def copy(cls, subscriptions, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('number', None)
        default.setdefault('next_invoice_date', None)
        default.setdefault('quoted_by')
        default.setdefault('run_by')
        return super(Subscription, cls).copy(subscriptions, default=default)

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('/tree', 'visual',
                If(Eval('state') == 'cancelled', 'muted', '')),
            ]

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
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
        company_id = Transaction().context.get('company', -1)

        consumptions = Consumption.search([
                ('invoice_line', '=', None),
                ('line.subscription.next_invoice_date', '<=', date),
                ('line.subscription.state', 'in', ['running', 'closed']),
                ('line.subscription.company', '=', company_id),
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
                ('company', '=', company_id),
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
        invoice.invoice_date = self.next_invoice_date
        invoice.set_journal()
        invoice.payment_term = self.payment_term
        return invoice


class Line(sequence_ordered(), ModelSQL, ModelView):
    "Subscription Line"
    __name__ = 'sale.subscription.line'

    subscription = fields.Many2One(
        'sale.subscription', "Subscription", required=True, ondelete='CASCADE',
        states={
            'readonly': ((Eval('subscription_state') != 'draft')
                & Bool(Eval('subscription'))),
            },
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
        depends={'company'})
    description = fields.Text("Description",
        states={
            'readonly': Eval('subscription_state') != 'draft',
            })

    quantity = fields.Float(
        "Quantity", digits='unit',
        states={
            'readonly': Eval('subscription_state') != 'draft',
            'required': Bool(Eval('consumption_recurrence')),
            })
    unit = fields.Many2One(
        'product.uom', "Unit", required=True,
        states={
            'readonly': Eval('subscription_state') != 'draft',
            },
        domain=[
            If(Bool(Eval('service_unit_category')),
                ('category', '=', Eval('service_unit_category')),
                ('category', '!=', -1)),
            ])
    service_unit_category = fields.Function(
        fields.Many2One('product.uom.category', "Service Unit Category"),
        'on_change_with_service_unit_category')

    unit_price = Monetary(
        "Unit Price", currency='currency', digits=price_digits,
        states={
            'readonly': Eval('subscription_state') != 'draft',
            })
    currency = fields.Function(fields.Many2One('currency.currency',
        'Currency'), 'on_change_with_currency')
    consumption_recurrence = fields.Many2One(
        'sale.subscription.recurrence.rule.set', "Consumption Recurrence",
        states={
            'readonly': Eval('subscription_state') != 'draft',
            })
    consumption_delay = fields.TimeDelta(
        "Consumption Delay",
        states={
            'readonly': Eval('subscription_state') != 'draft',
            'invisible': ~Eval('consumption_recurrence'),
            })
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
            })
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
            })

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('subscription')

    @classmethod
    def __register__(cls, module):
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        table = cls.__table__()

        super(Line, cls).__register__(module)
        table_h = cls.__table_handler__(module)

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
        return self.subscription.company if self.subscription else None

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

    @fields.depends('subscription', '_parent_subscription.currency')
    def on_change_with_currency(self, name=None):
        return self.subscription.currency if self.subscription else None

    @fields.depends('service')
    def on_change_with_service_unit_category(self, name=None):
        if self.service:
            return self.service.product.default_uom_category

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

        with Transaction().set_context(self._get_context_sale_price()):
            self.unit_price = Product.get_sale_price(
                [product], self.quantity or 0)[product.id]

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
        return (lang.format_number_symbol(
                self.quantity or 0, self.unit, digits=self.unit.digits)
            + ' %s @ %s' % (self.service.rec_name, self.subscription.rec_name))

    @classmethod
    def search_rec_name(cls, name, clause):
        _, operator, value = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('subscription.rec_name', *clause[1:]),
            ('service.rec_name', *clause[1:]),
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
        company_id = Transaction().context.get('company', -1)

        remainings = all_lines = cls.search([
                ('consumption_recurrence', '!=', None),
                ('next_consumption_date_delayed', '<=', date),
                ('subscription.state', '=', 'running'),
                ('subscription.company', '=', company_id),
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
        next_date = rruleset.after(dt, inc=inc)
        if next_date:
            next_date = next_date.date()
            for end_date in [self.end_date, self.subscription.end_date]:
                if end_date:
                    if next_date > end_date:
                        return None
            return next_date

    @classmethod
    def validate_fields(cls, lines, field_names):
        super().validate_fields(lines, field_names)
        cls.validate_consumption_recurrence(lines, field_names)

    @classmethod
    def validate_consumption_recurrence(cls, lines, field_names=None):
        if field_names and not (field_names & {
                    'consumption_recurrence', 'start_date'}):
            return
        for line in lines:
            if line.consumption_recurrence:
                try:
                    line.consumption_recurrence.rruleset(line.start_date)[0]
                except IndexError:
                    raise InvalidRecurrence(gettext(
                            'sale_subscription'
                            '.msg_consumption_recurrence_invalid',
                            line=line.rec_name,
                            subscription=line.subscription.rec_name))

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('next_consumption_date', None)
        default.setdefault('consumed_until', None)
        return super(Line, cls).copy(lines, default=default)


class LineConsumption(ModelSQL, ModelView):
    "Subscription Line Consumption"
    __name__ = 'sale.subscription.line.consumption'

    line = fields.Many2One(
        'sale.subscription.line', "Line", required=True, ondelete='RESTRICT')
    quantity = fields.Float("Quantity", digits='unit', required=True)
    unit = fields.Function(fields.Many2One(
            'product.uom', "Unit"), 'on_change_with_unit')
    date = fields.Date("Date", required=True)
    invoice_line = fields.Many2One(
        'account.invoice.line', "Invoice Line", readonly=True)

    @classmethod
    def __setup__(cls):
        super(LineConsumption, cls).__setup__()
        cls.__access__.add('line')
        cls._order.insert(0, ('date', 'DESC'))

    @fields.depends('line')
    def on_change_with_unit(self, name=None):
        return self.line.unit if self.line else None

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
        consumptions = sorted(
            consumptions, key=sortable_values(cls._group_invoice_key))
        for key, sub_consumptions in groupby(
                consumptions, key=cls._group_invoice_key):
            sub_consumptions = list(sub_consumptions)
            line = InvoiceLine(**dict(key))
            line.invoice = invoice
            line.on_change_invoice()
            line.type = 'line'
            line.quantity = sum(c.quantity for c in sub_consumptions)
            line.on_change_product()

            if not line.account:
                raise InvoiceError(
                    gettext('sale_subscription'
                        '.msg_consumption_invoice_missing_account_revenue',
                        product=line.product.rec_name))

            lines.append(line)
            grouped_consumptions.append(sub_consumptions)
        return lines, grouped_consumptions

    @classmethod
    def _group_invoice_key(cls, consumption):
        return (
            ('company', consumption.line.subscription.company),
            ('currency', consumption.line.subscription.currency),
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
