# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal
from itertools import groupby

from simpleeval import simple_eval
try:
    from sql import Null
except ImportError:
    Null = None
from sql.aggregate import Sum

from trytond.i18n import gettext
from trytond.model import ModelView, ModelSQL, MatchMixin, fields, \
    sequence_ordered
from trytond.pyson import Eval, Bool, If, Id, PYSONEncoder
from trytond.tools import decistmt, grouped_slice, reduce_ids
from trytond.pool import Pool
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.transaction import Transaction

from trytond.modules.product import price_digits, round_price

from .exceptions import FormulaError


class Agent(ModelSQL, ModelView):
    'Commission Agent'
    __name__ = 'commission.agent'
    party = fields.Many2One('party.party', "Party", required=True,
        help="The party for whom the commission is calculated.")
    type_ = fields.Selection([
            ('agent', 'Agent Of'),
            ('principal', 'Principal Of'),
            ], 'Type')
    company = fields.Many2One('company.company', 'Company', required=True)
    plan = fields.Many2One('commission.plan', "Plan",
        help="The plan used to calculate the commission.")
    currency = fields.Many2One('currency.currency', "Currency", required=True)
    pending_amount = fields.Function(fields.Numeric('Pending Amount',
            digits=price_digits), 'get_pending_amount')
    selections = fields.One2Many(
        'commission.agent.selection', 'agent', "Selections")

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Company = pool.get('company.company')
        sql_table = cls.__table__()
        company = Company.__table__()

        super().__register__(module_name)
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        table = cls.__table_handler__(module_name)

        # Migration from 5.4: Ensure currency is set
        # Don't use UPDATE FROM because SQLite does not support it
        cursor.execute(*sql_table.update(
                columns=[sql_table.currency],
                values=[company.select(
                        company.currency,
                        where=company.id == sql_table.company)],
                where=(sql_table.currency == Null)))

        # Migration from 5.4: Add not null on currency
        table.not_null_action('currency', 'add')

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_type_():
        return 'agent'

    @classmethod
    def default_currency(cls):
        pool = Pool()
        Company = pool.get('company.company')
        company = cls.default_company()
        if company:
            return Company(company).currency.id

    @fields.depends('company', 'currency')
    def on_change_company(self):
        if self.company and not self.currency:
            self.currency = self.company.currency

    def get_rec_name(self, name):
        if self.plan:
            return '%s - %s' % (self.party.rec_name, self.plan.rec_name)
        else:
            return self.party.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('party.rec_name',) + tuple(clause[1:]),
            ('plan.rec_name',) + tuple(clause[1:]),
            ]

    @classmethod
    def get_pending_amount(cls, agents, name):
        pool = Pool()
        Commission = pool.get('commission')
        commission = Commission.__table__()
        cursor = Transaction().connection.cursor()

        ids = [a.id for a in agents]
        amounts = dict.fromkeys(ids, None)
        for sub_ids in grouped_slice(ids):
            where = reduce_ids(commission.agent, sub_ids)
            where &= commission.invoice_line == Null
            query = commission.select(commission.agent, Sum(commission.amount),
                where=where,
                group_by=commission.agent)
            cursor.execute(*query)
            amounts.update(dict(cursor.fetchall()))
        for agent_id, amount in amounts.items():
            if amount:
                # SQLite uses float for SUM
                if not isinstance(amount, Decimal):
                    amount = Decimal(str(amount))
                amounts[agent_id] = round_price(amount)
        return amounts

    @property
    def account(self):
        if self.type_ == 'agent':
            return self.party.account_payable_used
        elif self.type_ == 'principal':
            return self.party.account_receivable_used


class AgentSelection(sequence_ordered(), MatchMixin, ModelSQL, ModelView):
    "Agent Selection"
    __name__ = 'commission.agent.selection'
    agent = fields.Many2One('commission.agent', "Agent", required=True)
    start_date = fields.Date(
        "Start Date",
        domain=[
            If(Eval('start_date') & Eval('end_date'),
                ('start_date', '<=', Eval('end_date')),
                ()),
            ],
        depends=['end_date'],
        help="The first date that the agent will be considered for selection.")
    end_date = fields.Date(
        "End Date",
        domain=[
            If(Eval('start_date') & Eval('end_date'),
                ('end_date', '>=', Eval('start_date')),
                ()),
            ],
        depends=['start_date'],
        help="The last date that the agent will be considered for selection.")
    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE', select=True)
    company = fields.Function(fields.Many2One('company.company', "Company"),
        'on_change_with_company')
    employee = fields.Many2One(
        'company.employee', "Employee", select=True,
        domain=[
            ('company', '=', Eval('company')),
            ],
        depends=['company'])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('party', 'ASC NULLS LAST'))
        cls._order.insert(1, ('employee', 'ASC NULLS LAST'))

    @fields.depends('agent', '_parent_agent.company')
    def on_change_with_company(self, name=None):
        if self.agent:
            return self.agent.company.id

    def match(self, pattern):
        pool = Pool()
        Date = pool.get('ir.date')

        pattern = pattern.copy()
        if 'company' in pattern:
            pattern.pop('company')
        date = pattern.pop('date', None) or Date.today()
        if self.start_date and self.start_date > date:
            return False
        if self.end_date and self.end_date < date:
            return False
        return super().match(pattern)


class Plan(ModelSQL, ModelView):
    'Commission Plan'
    __name__ = 'commission.plan'
    name = fields.Char('Name', required=True, translate=True)
    commission_product = fields.Many2One('product.product',
        'Commission Product', required=True,
        domain=[
            ('type', '=', 'service'),
            ('default_uom', '=', Id('product', 'uom_unit')),
            ('template.type', '=', 'service'),
            ('template.default_uom', '=', Id('product', 'uom_unit')),
            ],
        help="The product that is used on the invoice lines.")
    commission_method = fields.Selection([
            ('posting', 'On Posting'),
            ('payment', 'On Payment'),
            ], 'Commission Method',
        help="When the commission is due.")
    lines = fields.One2Many('commission.plan.line', 'plan', "Lines",
        help="The formulas used to calculate the commission for different "
        "criteria.")

    @staticmethod
    def default_commission_method():
        return 'posting'

    def get_context_formula(self, amount, product):
        return {
            'names': {
                'amount': amount,
                },
            }

    def compute(self, amount, product, pattern=None):
        'Compute commission amount for the amount'
        def parents(categories):
            for category in categories:
                while category:
                    yield category
                    category = category.parent

        if pattern is None:
            pattern = {}
        if product:
            pattern['categories'] = [
                c.id for c in parents(product.categories_all)]
            pattern['product'] = product.id
        else:
            pattern['categories'] = []
            pattern['product'] = None
        context = self.get_context_formula(amount, product)
        for line in self.lines:
            if line.match(pattern):
                return line.get_amount(**context)


class PlanLines(sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    'Commission Plan Line'
    __name__ = 'commission.plan.line'
    plan = fields.Many2One('commission.plan', 'Plan', required=True,
        ondelete='CASCADE',
        help="The plan to which the line belongs.")
    category = fields.Many2One(
        'product.category', "Category", ondelete='CASCADE',
        help="Apply only to products in the category.")
    product = fields.Many2One('product.product', "Product", ondelete='CASCADE',
        help="Apply only to the product.")
    formula = fields.Char('Formula', required=True,
        help="The python expression used to calculate the amount of "
        "commission for the line.\n"
        "It is evaluated with:\n"
        "- amount: the original amount")

    @staticmethod
    def default_formula():
        return 'amount'

    @classmethod
    def validate(cls, lines):
        super(PlanLines, cls).validate(lines)
        for line in lines:
            line.check_formula()

    def check_formula(self):
        context = self.plan.get_context_formula(Decimal(0), None)

        try:
            if not isinstance(self.get_amount(**context), Decimal):
                raise ValueError
        except Exception as exception:
            raise FormulaError(
                gettext('commission.msg_plan_line_invalid_formula',
                    formula=self.formula,
                    line=self.rec_name,
                    exception=exception)) from exception

    def get_amount(self, **context):
        'Return amount (as Decimal)'
        context.setdefault('functions', {})['Decimal'] = Decimal
        return simple_eval(decistmt(self.formula), **context)

    def match(self, pattern):
        if 'categories' in pattern:
            pattern = pattern.copy()
            categories = pattern.pop('categories')
            if (self.category is not None
                    and self.category.id not in categories):
                return False
        return super(PlanLines, self).match(pattern)


class Commission(ModelSQL, ModelView):
    'Commission'
    __name__ = 'commission'
    _readonly_states = {
        'readonly': Bool(Eval('invoice_line')),
        }
    _readonly_depends = ['invoice_line']
    origin = fields.Reference('Origin', selection='get_origin', select=True,
        readonly=True,
        help="The source of the commission.")
    date = fields.Date('Date', select=True, states=_readonly_states,
        depends=_readonly_depends,
        help="When the commission is due.")
    agent = fields.Many2One('commission.agent', 'Agent', required=True,
        states=_readonly_states, depends=_readonly_depends)
    product = fields.Many2One('product.product', 'Product', required=True,
        states=_readonly_states, depends=_readonly_depends,
        help="The product that is used on the invoice line.")
    amount = fields.Numeric('Amount', required=True, digits=price_digits,
        domain=[('amount', '!=', 0)],
        states=_readonly_states, depends=_readonly_depends)
    currency = fields.Function(fields.Many2One('currency.currency',
            'Currency'), 'on_change_with_currency')
    type_ = fields.Function(fields.Selection([
                ('in', 'Incoming'),
                ('out', 'Outgoing'),
                ], 'Type'), 'on_change_with_type_')
    invoice_line = fields.Many2One('account.invoice.line', 'Invoice Line',
        readonly=True, depends=['amount', 'type_'])
    invoice_state = fields.Function(fields.Selection([
                ('', ''),
                ('invoiced', 'Invoiced'),
                ('paid', 'Paid'),
                ('cancelled', 'Cancelled'),
                ], "Invoice State",
            help="The current state of the invoice "
            "that the commission appears on."),
        'get_invoice_state')

    @classmethod
    def __setup__(cls):
        super(Commission, cls).__setup__()
        cls._buttons.update({
                'invoice': {
                    'invisible': Bool(Eval('invoice_line')),
                    'depends': ['invoice_line'],
                    },
                })

    @classmethod
    def _get_origin(cls):
        'Return list of Model names for origin Reference'
        return ['account.invoice.line']

    @classmethod
    def get_origin(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        models = cls._get_origin()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [(None, '')] + [(m.model, m.name) for m in models]

    @fields.depends('agent')
    def on_change_with_currency(self, name=None):
        if self.agent:
            return self.agent.currency.id

    @fields.depends('agent')
    def on_change_with_type_(self, name=None):
        if self.agent:
            return {
                'agent': 'out',
                'principal': 'in',
                }.get(self.agent.type_)

    @fields.depends('agent', 'product')
    def on_change_agent(self):
        if not self.product and self.agent and self.agent.plan:
            self.product = self.agent.plan.commission_product

    def get_invoice_state(self, name):
        state = ''
        if self.invoice_line:
            state = 'invoiced'
            invoice = self.invoice_line.invoice
            if invoice and invoice.state in {'paid', 'cancelled'}:
                state = invoice.state
        return state

    @classmethod
    def copy(cls, commissions, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('invoice_line', None)
        return super(Commission, cls).copy(commissions, default=default)

    @classmethod
    @ModelView.button
    def invoice(cls, commissions):
        pool = Pool()
        Invoice = pool.get('account.invoice')

        def invoice_key(c):
            return c._group_to_invoice_key()

        def line_key(c):
            return c._group_to_invoice_line_key()
        commissions.sort(key=invoice_key)
        invoices = []
        to_write = []
        for key, commissions in groupby(commissions, key=invoice_key):
            commissions = list(commissions)
            key = dict(key)
            invoice = cls._get_invoice(key)
            invoice.save()
            invoices.append(invoice)

            commissions.sort(key=line_key)
            for key, commissions in groupby(commissions, key=line_key):
                commissions = [c for c in commissions if not c.invoice_line]
                key = dict(key)
                invoice_line = cls._get_invoice_line(key, invoice, commissions)
                invoice_line.save()
                to_write.extend([commissions, {
                            'invoice_line': invoice_line.id,
                            }])
        if to_write:
            cls.write(*to_write)
        Invoice.update_taxes(invoices)

    def _group_to_invoice_key(self):
        direction = {
            'in': 'out',
            'out': 'in',
            }.get(self.type_)
        return (('agent', self.agent), ('type', direction))

    @classmethod
    def get_journal(cls):
        pool = Pool()
        Journal = pool.get('account.journal')

        journals = Journal.search([
                ('type', '=', 'commission'),
                ], limit=1)
        if journals:
            return journals[0]

    @classmethod
    def _get_invoice(cls, key):
        pool = Pool()
        Invoice = pool.get('account.invoice')

        agent = key['agent']
        if key['type'] == 'out':
            payment_term = agent.party.customer_payment_term
        else:
            payment_term = agent.party.supplier_payment_term
        return Invoice(
            company=agent.company,
            type=key['type'],
            journal=cls.get_journal(),
            party=agent.party,
            invoice_address=agent.party.address_get(type='invoice'),
            currency=agent.currency,
            account=agent.account,
            payment_term=payment_term,
            )

    def _group_to_invoice_line_key(self):
        return (('product', self.product),)

    @classmethod
    def _get_invoice_line(cls, key, invoice, commissions):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')

        def sign(commission):
            if invoice.type == commission.type_:
                return -1
            else:
                return 1

        product = key['product']
        amount = invoice.currency.round(
            sum(c.amount * sign(c) for c in commissions))

        invoice_line = InvoiceLine()
        invoice_line.invoice = invoice
        invoice_line.type = 'line'
        invoice_line.product = product
        invoice_line.quantity = 1
        invoice_line.company = invoice.company
        invoice_line.currency = invoice.currency

        invoice_line.on_change_product()

        invoice_line.unit_price = amount
        return invoice_line


class CreateInvoice(Wizard):
    'Create Commission Invoice'
    __name__ = 'commission.create_invoice'
    start_state = 'ask'
    ask = StateView('commission.create_invoice.ask',
        'commission.commission_create_invoice_ask_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'create_', 'tryton-ok', default=True),
            ])
    create_ = StateAction('account_invoice.act_invoice_form')

    def get_domain(self):
        domain = [('invoice_line', '=', None)]
        if self.ask.from_:
            domain.append(('date', '>=', self.ask.from_))
        if self.ask.to:
            domain.append(('date', '<=', self.ask.to))
        if self.ask.type_ == 'in':
            domain.append(('agent.type_', '=', 'principal'))
        elif self.ask.type_ == 'out':
            domain.append(('agent.type_', '=', 'agent'))
        return domain

    def do_create_(self, action):
        pool = Pool()
        Commission = pool.get('commission')
        commissions = Commission.search(self.get_domain(),
            order=[('agent', 'DESC'), ('date', 'DESC')])
        Commission.invoice(commissions)
        invoice_ids = list({c.invoice_line.invoice.id for c in commissions})
        encoder = PYSONEncoder()
        action['pyson_domain'] = encoder.encode(
            [('id', 'in', invoice_ids)])
        action['pyson_search_value'] = encoder.encode([])
        return action, {}


class CreateInvoiceAsk(ModelView):
    'Create Commission Invoice'
    __name__ = 'commission.create_invoice.ask'
    from_ = fields.Date('From',
        domain=[
            If(Eval('to') & Eval('from_'), [('from_', '<=', Eval('to'))],
                []),
            ],
        depends=['to'],
        help="Limit to commissions from this date.")
    to = fields.Date('To',
        domain=[
            If(Eval('from_') & Eval('to'), [('to', '>=', Eval('from_'))],
                []),
            ],
        depends=['from_'],
        help="Limit to commissions to this date.")
    type_ = fields.Selection([
            ('in', 'Incoming'),
            ('out', 'Outgoing'),
            ('both', 'Both'),
            ], 'Type',
        help="Limit to commissions of this type.")

    @staticmethod
    def default_type_():
        return 'both'
