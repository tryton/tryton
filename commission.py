# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from __future__ import unicode_literals
from decimal import Decimal
from itertools import groupby

from simpleeval import simple_eval
try:
    from sql import Null
except ImportError:
    Null = None
from sql.aggregate import Sum
from sql.conditionals import Case

from trytond.model import ModelView, ModelSQL, MatchMixin, fields
from trytond.pyson import Eval, Bool, If, Id, PYSONEncoder
from trytond.tools import decistmt, grouped_slice, reduce_ids
from trytond.pool import Pool
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.transaction import Transaction

from trytond.modules.product import price_digits

__all__ = ['Agent', 'Plan', 'PlanLines', 'Commission',
    'CreateInvoice', 'CreateInvoiceAsk']


class Agent(ModelSQL, ModelView):
    'Commission Agent'
    __name__ = 'commission.agent'
    party = fields.Many2One('party.party', 'Party', required=True)
    type_ = fields.Selection([
            ('agent', 'Agent Of'),
            ('principal', 'Principal Of'),
            ], 'Type')
    company = fields.Many2One('company.company', 'Company', required=True)
    plan = fields.Many2One('commission.plan', 'Plan')
    currency = fields.Many2One('currency.currency', 'Currency',
        states={
            'required': Bool(Eval('plan')),
            'invisible': ~Eval('plan'),
            },
        depends=['plan'])
    pending_amount = fields.Function(fields.Numeric('Pending Amount',
            digits=price_digits), 'get_pending_amount')

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_type_():
        return 'agent'

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
        digits = cls.pending_amount.digits
        exp = Decimal(str(10.0 ** -digits[1]))
        for agent_id, amount in amounts.iteritems():
            if amount:
                # SQLite uses float for SUM
                if not isinstance(amount, Decimal):
                    amount = Decimal(str(amount))
                amounts[agent_id] = amount.quantize(exp)
        return amounts

    @property
    def account(self):
        if self.type_ == 'agent':
            return self.party.account_payable
        elif self.type_ == 'principal':
            return self.party.account_receivable


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
            ])
    commission_method = fields.Selection([
            ('posting', 'On Posting'),
            ('payment', 'On Payment'),
            ], 'Commission Method',
        help='When the commission is due')
    lines = fields.One2Many('commission.plan.line', 'plan', 'Lines')

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
        if pattern is None:
            pattern = {}
        pattern['product'] = product.id if product else None
        context = self.get_context_formula(amount, product)
        for line in self.lines:
            if line.match(pattern):
                return line.get_amount(**context)


class PlanLines(ModelSQL, ModelView, MatchMixin):
    'Commission Plan Line'
    __name__ = 'commission.plan.line'
    plan = fields.Many2One('commission.plan', 'Plan', required=True,
        ondelete='CASCADE')
    product = fields.Many2One('product.product', 'Product')
    sequence = fields.Integer('Sequence')
    formula = fields.Char('Formula', required=True,
        help=('Python expression that will be evaluated with:\n'
            '- amount: the original amount'))

    @classmethod
    def __setup__(cls):
        super(PlanLines, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))
        cls._error_messages.update({
                'invalid_formula': ('Invalid formula "%(formula)s" in '
                    'commission plan line "%(line)s" with exception '
                    '"%(exception)s".'),
                })

    @staticmethod
    def order_sequence(tables):
        table, _ = tables[None]
        return [Case((table.sequence == Null, 0), else_=1), table.sequence]

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
        except ValueError, exception:
            self.raise_user_error('invalid_formula', {
                    'formula': self.formula,
                    'line': self.rec_name,
                    'exception': exception,
                    })

    def get_amount(self, **context):
        'Return amount (as Decimal)'
        context.setdefault('functions', {})['Decimal'] = Decimal
        return simple_eval(decistmt(self.formula), **context)


class Commission(ModelSQL, ModelView):
    'Commission'
    __name__ = 'commission'
    _readonly_states = {
        'readonly': Bool(Eval('invoice_line')),
        }
    _readonly_depends = ['invoice_line']
    origin = fields.Reference('Origin', selection='get_origin', select=True,
        readonly=True)
    date = fields.Date('Date', select=True, states=_readonly_states,
        depends=_readonly_depends)
    agent = fields.Many2One('commission.agent', 'Agent', required=True,
        states=_readonly_states, depends=_readonly_depends)
    product = fields.Many2One('product.product', 'Product', required=True,
        states=_readonly_states, depends=_readonly_depends)
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
                ('cancel', 'Canceled'),
                ], 'Invoice State'), 'get_invoice_state')

    @classmethod
    def __setup__(cls):
        super(Commission, cls).__setup__()
        cls._buttons.update({
                'invoice': {
                    'invisible': Bool(Eval('invoice_line')),
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
            if invoice:
                if invoice.state == 'paid':
                    state = 'paid'
                elif invoice.state == 'cancel':
                    state = 'cancel'
        return state

    @classmethod
    def copy(cls, commissions, default=None):
        if default is None:
            default = {}
        default.setdefault('invoice_line', None)
        return super(Commission, cls).copy(commissions, default=default)

    @classmethod
    @ModelView.button
    def invoice(cls, commissions):
        pool = Pool()
        Invoice = pool.get('account.invoice')

        key = lambda c: c._group_to_invoice_key()
        commissions.sort(key=key)
        invoices = []
        to_write = []
        for key, commissions in groupby(commissions, key=key):
            commissions = list(commissions)
            key = dict(key)
            invoice = cls._get_invoice(key)
            invoice.save()
            invoices.append(invoice)

            key = lambda c: c._group_to_invoice_line_key()
            commissions.sort(key=key)
            for key, commissions in groupby(commissions, key=key):
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
        depends=['to'])
    to = fields.Date('To',
        domain=[
            If(Eval('from_') & Eval('to'), [('to', '>=', Eval('from_'))],
                []),
            ],
        depends=['from_'])
    type_ = fields.Selection([
            ('in', 'Incoming'),
            ('out', 'Outgoing'),
            ('both', 'Both'),
            ], 'Type')

    @staticmethod
    def default_type_():
        return 'both'
