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

from trytond import backend
from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, MatchMixin, ModelSQL, ModelView, fields,
    sequence_ordered)
from trytond.modules.currency.fields import Monetary
from trytond.modules.product import price_digits, round_price
from trytond.pool import Pool
from trytond.pyson import Bool, Eval, Id, If
from trytond.tools import (
    decistmt, grouped_slice, reduce_ids, sqlite_apply_types)
from trytond.transaction import Transaction, check_access
from trytond.wizard import Button, StateAction, StateView, Wizard

from .exceptions import FormulaError


class Agent(DeactivableMixin, ModelSQL, ModelView):
    'Commission Agent'
    __name__ = 'commission.agent'
    party = fields.Many2One('party.party', "Party", required=True,
        context={
            'company': Eval('company', -1),
            },
        depends={'company'},
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
        'commission.agent.selection', 'agent', "Selections",
        domain=[
            If(~Eval('active', True),
                ('end_date', '!=', None),
                ()),
            ],
        states={
            'invisible': Eval('type_') != 'agent',
            })
    products = fields.Many2Many(
        'product.template-commission.agent', 'agent', 'template', "Products",
        states={
            'invisible': Eval('type_') != 'principal',
            },
        context={
            'company': Eval('company', -1),
            })

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

    @fields.depends('active', 'selections', 'company')
    def on_change_active(self):
        pool = Pool()
        Date = pool.get('ir.date')
        with Transaction().set_context(
                company=self.company.id if self.company else None):
            today = Date.today()
        if not self.active and self.selections:
            for selection in self.selections:
                start_date = getattr(selection, 'start_date') or today
                end_date = getattr(selection, 'end_date')
                if not end_date:
                    selection.end_date = max(today, start_date)
            self.selections = self.selections

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
        if company is not None and company >= 0:
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
            query = commission.select(
                commission.agent, Sum(commission.amount).as_('pending_amount'),
                where=where,
                group_by=commission.agent)
            if backend.name == 'sqlite':
                sqlite_apply_types(query, [None, 'NUMERIC'])
            cursor.execute(*query)
            amounts.update(dict(cursor))
        if backend.name == 'sqlite':
            for agent_id, amount in amounts.items():
                if amount is not None:
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
    agent = fields.Many2One(
        'commission.agent', "Agent", required=True,
        domain=[
            ('type_', '=', 'agent'),
            ])
    start_date = fields.Date(
        "Start Date",
        domain=[
            If(Eval('start_date') & Eval('end_date'),
                ('start_date', '<=', Eval('end_date')),
                ()),
            ],
        help="The first date that the agent will be considered for selection.")
    end_date = fields.Date(
        "End Date",
        domain=[
            If(Eval('start_date') & Eval('end_date'),
                ('end_date', '>=', Eval('start_date')),
                ()),
            ],
        help="The last date that the agent will be considered for selection.")
    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE',
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    company = fields.Function(fields.Many2One('company.company', "Company"),
        'on_change_with_company', searcher='search_company')
    employee = fields.Many2One(
        'company.employee', "Employee",
        domain=[
            ('company', '=', Eval('company', -1)),
            ])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('agent')
        cls._order.insert(0, ('party', 'ASC NULLS LAST'))
        cls._order.insert(1, ('employee', 'ASC NULLS LAST'))

    @fields.depends('agent', '_parent_agent.company')
    def on_change_with_company(self, name=None):
        return self.agent.company if self.agent else None

    @classmethod
    def search_company(cls, name, clause):
        return [('agent.' + clause[0],) + tuple(clause[1:])]

    def match(self, pattern):
        pool = Pool()
        Date = pool.get('ir.date')

        pattern = pattern.copy()
        if 'company' in pattern:
            pattern.pop('company')
        with Transaction().set_context(company=self.company.id):
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

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('plan')

    @staticmethod
    def default_formula():
        return 'amount'

    @classmethod
    def validate_fields(cls, lines, field_names):
        super().validate_fields(lines, field_names)
        cls.check_formula(lines, field_names)

    @classmethod
    def check_formula(cls, lines, field_names=None):
        if field_names and 'formula' not in field_names:
            return
        for line in lines:
            context = line.plan.get_context_formula(Decimal(0), None)
            try:
                if not isinstance(line.get_amount(**context), Decimal):
                    raise ValueError
            except Exception as exception:
                raise FormulaError(
                    gettext('commission.msg_plan_line_invalid_formula',
                        formula=line.formula,
                        line=line.rec_name,
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
    origin = fields.Reference(
        "Origin", selection='get_origin', states=_readonly_states,
        help="The source of the commission.")
    date = fields.Date(
        "Date", states=_readonly_states,
        help="When the commission is due.")
    agent = fields.Many2One('commission.agent', 'Agent', required=True,
        states=_readonly_states)
    product = fields.Many2One('product.product', 'Product', required=True,
        states=_readonly_states,
        help="The product that is used on the invoice line.")
    base_amount = Monetary(
        "Base Amount", currency='currency', digits=price_digits,
        states=_readonly_states)
    amount = Monetary(
        "Amount", currency='currency', required=True, digits=price_digits,
        domain=[('amount', '!=', 0)],
        states=_readonly_states)
    currency = fields.Function(fields.Many2One('currency.currency',
            'Currency'), 'on_change_with_currency')
    type_ = fields.Function(fields.Selection([
                ('in', 'Incoming'),
                ('out', 'Outgoing'),
                ], 'Type'), 'on_change_with_type_')
    invoice_line = fields.Many2One('account.invoice.line', 'Invoice Line',
        readonly=True)
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
        cls.__access__.add('agent')
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
        get_name = Model.get_name
        models = cls._get_origin()
        return [(None, '')] + [(m, get_name(m)) for m in models]

    @fields.depends('agent', 'origin', 'base_amount')
    def on_change_with_base_amount(self):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        Currency = pool.get('currency.currency')
        if (self.agent
                and isinstance(self.origin, InvoiceLine)
                and self.origin.id is not None
                and self.origin.id >= 0
                and self.base_amount is None):
            return Currency.compute(
                self.origin.invoice.currency, self.origin.amount,
                self.agent.currency, round=False)

    @fields.depends('agent')
    def on_change_with_currency(self, name=None):
        return self.agent.currency if self.agent else None

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
        InvoiceLine = pool.get('account.invoice.line')
        try:
            Move = pool.get('stock.move')
        except KeyError:
            Move = None

        def invoice_key(c):
            return c._group_to_invoice_key()

        def line_key(c):
            return c._group_to_invoice_line_key()
        commissions.sort(key=invoice_key)
        invoices = []
        invoice_lines = []
        to_save = []
        for key, commissions in groupby(commissions, key=invoice_key):
            commissions = list(commissions)
            key = dict(key)
            invoice = cls._get_invoice(key)
            invoices.append(invoice)

            commissions.sort(key=line_key)
            for key, commissions in groupby(commissions, key=line_key):
                commissions = [c for c in commissions if not c.invoice_line]
                key = dict(key)
                invoice_line = cls._get_invoice_line(key, invoice, commissions)
                invoice_lines.append(invoice_line)
                for commission in commissions:
                    commission.invoice_line = invoice_line
                    to_save.append(commission)
        Invoice.save(invoices)
        InvoiceLine.save(invoice_lines)
        Invoice.update_taxes(invoices)
        cls.save(to_save)

        if Move and hasattr(Move, 'update_unit_price'):
            moves = list(set().union(*(c.stock_moves for c in commissions)))
            if moves:
                Move.__queue__.update_unit_price(moves)

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
        invoice_line.currency = invoice.currency
        invoice_line.company = invoice.company
        invoice_line.type = 'line'
        # Use product.id to instantiate it with the correct context
        invoice_line.product = product.id
        invoice_line.quantity = 1

        invoice_line.on_change_product()

        invoice_line.unit_price = amount
        return invoice_line

    @property
    def stock_moves(self):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        stock_moves = set()
        if (isinstance(self.origin, InvoiceLine)
                and hasattr(InvoiceLine, 'stock_moves')):
            stock_moves.update(self.origin.stock_moves)
        return stock_moves


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
        if self.ask.agents:
            agents = [agent.id for agent in self.ask.agents]
            domain.append(('agent', 'in', agents))
        return domain

    def do_create_(self, action):
        pool = Pool()
        Commission = pool.get('commission')
        with check_access():
            commissions = Commission.search(self.get_domain(),
                order=[('agent', 'DESC'), ('date', 'DESC')])
        commissions = Commission.browse(commissions)
        Commission.invoice(commissions)
        invoice_ids = list({c.invoice_line.invoice.id for c in commissions})
        return action, {'res_id': invoice_ids}


class CreateInvoiceAsk(ModelView):
    'Create Commission Invoice'
    __name__ = 'commission.create_invoice.ask'
    from_ = fields.Date('From',
        domain=[
            If(Eval('to') & Eval('from_'), [('from_', '<=', Eval('to'))],
                []),
            ],
        help="Limit to commissions from this date.")
    to = fields.Date('To',
        domain=[
            If(Eval('from_') & Eval('to'), [('to', '>=', Eval('from_'))],
                []),
            ],
        help="Limit to commissions to this date.")
    type_ = fields.Selection([
            ('in', 'Incoming'),
            ('out', 'Outgoing'),
            ('both', 'Both'),
            ], 'Type',
        help="Limit to commissions of this type.")
    agents = fields.Many2Many(
        'commission.agent', None, None, "Agents",
        domain=[
            If(Eval('type_') == 'in',
                ('type_', '=', 'principal'), ()),
            If(Eval('type_') == 'out',
                ('type_', '=', 'agent'), ()),
        ],
        help="Limit to commissions for these agents.\n"
        "If empty all agents of the selected type are used.")

    @staticmethod
    def default_type_():
        return 'both'
