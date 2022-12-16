# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from simpleeval import simple_eval
from itertools import chain

from trytond.i18n import gettext
from trytond.pool import Pool, PoolMeta
from trytond.model import (
    ModelSQL, ModelView, Workflow, DeactivableMixin, fields)
from trytond.pyson import Eval, Bool
from trytond.tools import decistmt
from trytond.transaction import Transaction
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)

from .exceptions import FormulaError


class AdvancePaymentTerm(
        DeactivableMixin, ModelSQL, ModelView):
    "Advance Payment Term"
    __name__ = 'sale.advance_payment_term'

    name = fields.Char("Name", required=True, translate=True)
    lines = fields.One2Many(
        'sale.advance_payment_term.line', 'advance_payment_term', "Lines")

    def get_advance_payment_context(self, sale):
        return {
            'total_amount': sale.total_amount,
            'untaxed_amount': sale.untaxed_amount,
            }

    def get_conditions(self, sale):
        conditions = []
        term_context = self.get_advance_payment_context(sale)
        for line in self.lines:
            condition = line.get_condition(sale.currency, **term_context)
            if condition.amount > 0:
                conditions.append(condition)
        return conditions


class AdvancePaymentTermLine(ModelView, ModelSQL, CompanyMultiValueMixin):
    "Advance Payment Term Line"
    __name__ = 'sale.advance_payment_term.line'
    _rec_name = 'description'

    advance_payment_term = fields.Many2One(
        'sale.advance_payment_term', "Advance Payment Term",
        required=True, ondelete='CASCADE', select=True)
    description = fields.Char(
        "Description", required=True, translate=True,
        help="Used as description for the invoice line.")
    account = fields.MultiValue(
        fields.Many2One('account.account', "Account", required=True,
            domain=[
                ('type.unearned_revenue', '=', True),
                ],
            help="Used for the line of advance payment invoice."))
    accounts = fields.One2Many(
        'sale.advance_payment_term.line.account', 'line', "Accounts")
    block_supply = fields.Boolean(
        "Block Supply",
        help="Check to prevent any supply request before advance payment.")
    block_shipping = fields.Boolean(
        "Block Shipping",
        help="Check to prevent the packing of the shipment "
        "before advance payment.")
    invoice_delay = fields.TimeDelta(
        "Invoice Delay",
        help="Delta to apply on the sale date for the date of "
        "the advance payment invoice.")
    formula = fields.Char('Formula', required=True,
        help="A python expression used to compute the advance payment amount "
            "that will be evaluated with:\n"
            "- total_amount: The total amount of the sale.\n"
            "- untaxed_amount: The total untaxed amount of the sale.")

    @fields.depends('formula', 'description')
    def pre_validate(self, **names):
        super(AdvancePaymentTermLine, self).pre_validate()
        names['total_amount'] = names['untaxed_amount'] = 0
        try:
            if not isinstance(self.compute_amount(**names), Decimal):
                raise Exception('The formula does not return a Decimal')
        except Exception as exception:
            raise FormulaError(
                gettext('sale_advance_payment.msg_term_line_invalid_formula',
                    formula=self.formula,
                    term_line=self.description or '',
                    exception=exception)) from exception

    def get_compute_amount_context(self, **names):
        return {
            'names': names,
            'functions': {
                'Decimal': Decimal,
                },
            }

    def compute_amount(self, **names):
        context = self.get_compute_amount_context(**names)
        return simple_eval(decistmt(self.formula), **context)

    def get_condition(self, currency, **context):
        pool = Pool()
        AdvancePaymentCondition = pool.get('sale.advance_payment.condition')

        return AdvancePaymentCondition(
            block_supply=self.block_supply,
            block_shipping=self.block_shipping,
            amount=currency.round(self.compute_amount(**context)),
            account=self.account,
            invoice_delay=self.invoice_delay,
            description=self.description)


class AdvancePaymentTermLineAccount(ModelSQL, CompanyValueMixin):
    "Advance Payment Term Line Account"
    __name__ = 'sale.advance_payment_term.line.account'

    line = fields.Many2One(
        'sale.advance_payment_term.line', 'Line', required=True, select=True,
        ondelete='CASCADE')
    account = fields.Many2One(
        'account.account', "Account", required=True,
        domain=[
            ('type.unearned_revenue', '=', True),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])


class AdvancePaymentCondition(ModelSQL, ModelView):
    "Advance Payment Condition"
    __name__ = 'sale.advance_payment.condition'
    _rec_name = 'description'

    _states = {
        'readonly': Eval('sale_state') != 'draft',
        }
    _depends = ['sale_state']

    sale = fields.Many2One('sale.sale', 'Sale', required=True,
        ondelete='CASCADE', select=True,
        states={
            'readonly': ((Eval('sale_state') != 'draft')
                & Bool(Eval('sale'))),
            },
        depends=['sale_state'])
    description = fields.Char(
        "Description", required=True, states=_states, depends=_depends)
    amount = fields.Numeric(
        "Amount",
        digits=(16, Eval('_parent_sale', {}).get('currency_digits', 2)),
        states=_states, depends=_depends)
    account = fields.Many2One(
        'account.account', "Account", required=True,
        domain=[
            ('type.unearned_revenue', '=', True),
            ('company', '=', Eval('sale_company')),
            ],
        states=_states,
        depends=_depends + ['sale_company'])
    block_supply = fields.Boolean(
        "Block Supply", states=_states, depends=_depends)
    block_shipping = fields.Boolean(
        "Block Shipping", states=_states, depends=_depends)
    invoice_delay = fields.TimeDelta(
        "Invoice Delay", states=_states, depends=_depends)

    invoice_lines = fields.One2Many(
        'account.invoice.line', 'origin', "Invoice Lines", readonly=True)
    completed = fields.Function(fields.Boolean("Completed"), 'get_completed')

    sale_state = fields.Function(fields.Selection(
            'get_sale_states', "Sale State"), 'on_change_with_sale_state')
    sale_company = fields.Function(fields.Many2One(
            'company.company', "Company"), 'on_change_with_sale_company')

    del _states
    del _depends

    @classmethod
    def __setup__(cls):
        super(AdvancePaymentCondition, cls).__setup__()
        cls._order.insert(0, ('amount', 'ASC'))

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
    def on_change_with_sale_company(self, name=None):
        if self.sale and self.sale.company:
            return self.sale.company.id

    @classmethod
    def copy(cls, conditions, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('invoice_lines', [])
        return super(AdvancePaymentCondition, cls).copy(conditions, default)

    def create_invoice(self):
        invoice = self.sale._get_invoice_sale()
        invoice.invoice_date = self.sale.sale_date
        if self.invoice_delay:
            invoice.invoice_date += self.invoice_delay
        invoice.payment_term = None

        invoice_lines = self.get_invoice_advance_payment_lines(invoice)
        if not invoice_lines:
            return None
        invoice.lines = invoice_lines
        invoice.save()

        invoice.update_taxes()
        return invoice

    def get_invoice_advance_payment_lines(self, invoice):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')

        advance_amount = self._get_advance_amount()
        advance_amount += self._get_ignored_amount()
        if advance_amount >= self.amount:
            return []

        invoice_line = InvoiceLine()
        invoice_line.invoice = invoice
        invoice_line.type = 'line'
        invoice_line.quantity = 1
        invoice_line.account = self.account
        invoice_line.unit_price = self.amount - advance_amount
        invoice_line.description = self.description
        invoice_line.origin = self
        invoice_line.company = self.sale.company
        invoice_line.currency = self.sale.currency
        # Set taxes
        invoice_line.on_change_account()
        return [invoice_line]

    def _get_advance_amount(self):
        return sum(l.amount for l in self.invoice_lines
            if l.invoice.state != 'cancelled')

    def _get_ignored_amount(self):
        skips = {l for i in self.sale.invoices_recreated for l in i.lines}
        return sum(l.amount for l in self.invoice_lines
            if l.invoice.state == 'cancelled' and l not in skips)

    def get_completed(self, name):
        advance_amount = 0
        lines_ignored = set(l for i in self.sale.invoices_ignored
            for l in i.lines)
        for l in self.invoice_lines:
            if l.invoice.state == 'paid' or l in lines_ignored:
                advance_amount += l.amount
        return advance_amount >= self.amount


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    advance_payment_term = fields.Many2One('sale.advance_payment_term',
        'Advance Payment Term',
        ondelete='RESTRICT', states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])
    advance_payment_conditions = fields.One2Many(
        'sale.advance_payment.condition', 'sale',
        'Advance Payment Conditions',
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])
    advance_payment_invoices = fields.Function(fields.Many2Many(
            'account.invoice', None, None, "Advance Payment Invoices"),
        'get_advance_payment_invoices',
        searcher='search_advance_payment_invoices')

    @classmethod
    @ModelView.button
    @Workflow.transition('quotation')
    def quote(cls, sales):
        pool = Pool()
        AdvancePaymentCondition = pool.get('sale.advance_payment.condition')

        super(Sale, cls).quote(sales)

        AdvancePaymentCondition.delete(
            list(chain(*(s.advance_payment_conditions for s in sales))))

        for sale in sales:
            sale.set_advance_payment_term()
        cls.save(sales)

    @classmethod
    def copy(cls, sales, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('advance_payment_conditions', None)
        return super(Sale, cls).copy(sales, default=default)

    def set_advance_payment_term(self):
        pool = Pool()
        AdvancePaymentTerm = pool.get('sale.advance_payment_term')
        if self.advance_payment_term:
            if self.party and self.party.lang:
                with Transaction().set_context(language=self.party.lang.code):
                    advance_payment_term = AdvancePaymentTerm(
                        self.advance_payment_term.id)
            else:
                advance_payment_term = self.advance_payment_term
            self.advance_payment_conditions = \
                advance_payment_term.get_conditions(self)

    def get_advance_payment_invoices(self, name):
        invoices = set()
        for condition in self.advance_payment_conditions:
            for invoice_line in condition.invoice_lines:
                if invoice_line.invoice:
                    invoices.add(invoice_line.invoice.id)
        return list(invoices)

    @classmethod
    def search_advance_payment_invoices(cls, name, clause):
        return [('advance_payment_conditions.invoice_lines.invoice'
                + clause[0].lstrip(name),)
            + tuple(clause[1:])]

    def get_invoice_state(self):
        state = super(Sale, self).get_invoice_state()
        skip_ids = set(x.id for x in self.invoices_ignored)
        skip_ids.update(x.id for x in self.invoices_recreated)
        invoices = [i
            for i in self.advance_payment_invoices if i.id not in skip_ids]
        if invoices:
            if any(i.state == 'cancelled' for i in invoices):
                return 'exception'
            elif all(i.state == 'paid' for i in invoices):
                return state
            else:
                return 'waiting'
        return state

    def get_recall_lines(self, invoice):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')

        recall_lines = []
        advance_lines = InvoiceLine.search([
                ('origin', 'in', [str(c)
                        for c in self.advance_payment_conditions]),
                ('invoice.state', '=', 'paid'),
                ])
        for advance_line in advance_lines:
            line = InvoiceLine(
                invoice=invoice,
                company=invoice.company,
                type=advance_line.type,
                quantity=advance_line.quantity,
                account=advance_line.account,
                unit_price=-advance_line.amount,
                description=advance_line.description,
                origin=advance_line,
                taxes=advance_line.taxes,
                )
            recall_lines.append(line)

        return recall_lines

    def create_invoice(self):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')

        invoice = super(Sale, self).create_invoice()

        if self.advance_payment_eligible():
            if not self.advance_payment_completed:
                for condition in self.advance_payment_conditions:
                    condition.create_invoice()
            elif invoice is not None:
                recall_lines = self.get_recall_lines(invoice)
                if recall_lines:
                    for line in recall_lines:
                        line.invoice = invoice
                    InvoiceLine.save(recall_lines)
                    invoice.update_taxes()

        return invoice

    def advance_payment_eligible(self, shipment_type=None):
        """
        Returns True when the shipment_type is eligible to further processing
        of the sale's advance payment.
        """
        return bool((shipment_type == 'out' or shipment_type is None)
            and self.advance_payment_conditions)

    @property
    def advance_payment_completed(self):
        """
        Returns True when the advance payment process is completed
        """
        return (bool(self.advance_payment_conditions)
            and all(c.completed for c in self.advance_payment_conditions))

    @property
    def supply_blocked(self):
        for condition in self.advance_payment_conditions:
            if not condition.block_supply:
                continue
            if not condition.completed:
                return True
        return False

    @property
    def shipping_blocked(self):
        for condition in self.advance_payment_conditions:
            if not condition.block_shipping:
                continue
            if not condition.completed:
                return True
        return False


class SaleLine(metaclass=PoolMeta):
    __name__ = 'sale.line'

    def get_move(self, shipment_type):
        move = super(SaleLine, self).get_move(shipment_type)
        if (self.sale.advance_payment_eligible(shipment_type)
                and self.sale.supply_blocked):
            return None
        return move

    def get_purchase_request(self):
        request = super(SaleLine, self).get_purchase_request()
        if (self.sale.advance_payment_eligible()
                and self.sale.supply_blocked):
            return None
        return request

    def get_invoice_line(self):
        lines = super(SaleLine, self).get_invoice_line()
        if (self.sale.advance_payment_eligible()
                and not self.sale.advance_payment_completed):
            return []
        return lines


class HandleInvoiceException(metaclass=PoolMeta):
    __name__ = 'sale.handle.invoice.exception'

    def default_ask(self, fields):
        default = super(HandleInvoiceException, self).default_ask(fields)
        invoices = default['domain_invoices']

        sale = self.record
        skips = set(sale.invoices_ignored)
        skips.update(sale.invoices_recreated)
        for invoice in sale.advance_payment_invoices:
            if invoice.state == 'cancelled' and invoice not in skips:
                invoices.append(invoice.id)
        return default
