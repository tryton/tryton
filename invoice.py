# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from itertools import groupby

from trytond.model import ModelView, Workflow, fields
from trytond.modules.product import round_price
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, If
from trytond.tools import grouped_slice
from trytond.transaction import Transaction


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'
    agent = fields.Many2One('commission.agent', 'Commission Agent',
        domain=[
            ('type_', '=', 'agent'),
            ('company', '=', Eval('company', -1)),
            ],
        states={
            'invisible': Eval('type') == 'in',
            'readonly': Eval('state', '') != 'draft',
            },
        help="The agent who receives a commission for the invoice.")

    @classmethod
    def _journal_types(cls, invoice_type):
        return super()._journal_types(invoice_type) + ['commission']

    @classmethod
    def _post(cls, invoices):
        # Create commission only the first time the invoice is posted
        to_commission = [i for i in invoices
            if i.state not in ['posted', 'paid']]
        super()._post(invoices)
        cls.create_commissions(to_commission)

    @classmethod
    def create_commissions(cls, invoices):
        pool = Pool()
        Commission = pool.get('commission')
        all_commissions = []
        for invoice in invoices:
            for line in invoice.lines:
                commissions = line.get_commissions()
                if commissions:
                    all_commissions.extend(commissions)

        Commission.save(all_commissions)
        return all_commissions

    @classmethod
    @Workflow.transition('paid')
    def paid(cls, invoices):
        pool = Pool()
        Date = pool.get('ir.date')
        Commission = pool.get('commission')

        super(Invoice, cls).paid(invoices)

        date2commissions = defaultdict(list)
        for company, c_invoices in groupby(invoices, key=lambda i: i.company):
            with Transaction().set_context(company=company.id):
                today = Date.today()
            for sub_invoices in grouped_slice(list(c_invoices)):
                ids = [i.id for i in sub_invoices]
                for commission in Commission.search([
                            ('date', '=', None),
                            ('origin.invoice', 'in', ids,
                                'account.invoice.line'),
                            ]):
                    date = commission.origin.invoice.reconciled or today
                    date2commissions[date].append(commission)
        to_write = []
        for date, commissions in date2commissions.items():
            to_write.append(commissions)
            to_write.append({
                'date': date,
                })
        if to_write:
            Commission.write(*to_write)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, invoices):
        pool = Pool()
        Commission = pool.get('commission')

        invoices_to_revert_commission = [x for x in invoices if not x.move]

        super(Invoice, cls).cancel(invoices)

        to_delete = []
        to_save = []
        for sub_invoices in grouped_slice(invoices_to_revert_commission):
            ids = [i.id for i in sub_invoices]
            to_delete += Commission.search([
                    ('invoice_line', '=', None),
                    ('origin.invoice', 'in', ids, 'account.invoice.line'),
                    ])
            to_cancel = Commission.search([
                    ('invoice_line', '!=', None),
                    ('origin.invoice', 'in', ids, 'account.invoice.line'),
                    ])
            for commission in Commission.copy(to_cancel):
                commission.amount *= -1
                to_save.append(commission)

        Commission.delete(to_delete)
        Commission.save(to_save)

    def _credit(self, **values):
        values.setdefault('agent', self.agent)
        return super()._credit(**values)


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'
    principal = fields.Many2One('commission.agent', 'Commission Principal',
        domain=[
            ('type_', '=', 'principal'),
            ('company', '=', Eval('_parent_invoice', {}).get('company',
                    Eval('company', -1))),
            ],
        states={
            'invisible': If(Bool(Eval('_parent_invoice')),
                Eval('_parent_invoice', {}).get('type') == 'in',
                Eval('invoice_type') == 'in'),
            },
        help="The principal who pays a commission for the invoice line.")
    commissions = fields.One2Many('commission', 'origin', 'Commissions',
        readonly=True,
        states={
            'invisible': ~Eval('commissions'),
            })
    from_commissions = fields.One2Many('commission', 'invoice_line',
        'From Commissions', readonly=True,
        states={
            'invisible': ~Eval('from_commissions'),
            })

    @property
    def agent_plans_used(self):
        "List of agent, plan tuple"
        used = []
        if self.invoice.agent:
            used.append((self.invoice.agent, self.invoice.agent.plan))
        if self.principal:
            used.append((self.principal, self.principal.plan))
        return used

    def get_commissions(self):
        pool = Pool()
        Commission = pool.get('commission')
        Currency = pool.get('currency.currency')
        Date = pool.get('ir.date')

        if self.type != 'line':
            return []

        with Transaction().set_context(company=self.invoice.company.id):
            today = Date.today()
        commissions = []
        for agent, plan in self.agent_plans_used:
            if not plan:
                continue
            with Transaction().set_context(date=self.invoice.currency_date):
                base_amount = Currency.compute(self.invoice.currency,
                    self.amount, agent.currency, round=False)
            amount = self._get_commission_amount(base_amount, plan)
            if amount:
                amount = round_price(amount)
            if not amount:
                continue

            commission = Commission()
            commission.origin = self
            if plan.commission_method == 'posting':
                commission.date = self.invoice.invoice_date or today
            elif (plan.commission_method == 'payment'
                    and self.invoice.state == 'paid'):
                commission.date = self.invoice.reconciled or today
            commission.agent = agent
            commission.product = plan.commission_product
            commission.base_amount = base_amount
            commission.amount = amount
            commissions.append(commission)
        return commissions

    def _get_commission_amount(self, amount, plan, pattern=None):
        return plan.compute(amount, self.product, pattern=pattern)

    @fields.depends('product', 'principal')
    def on_change_product(self):
        super(InvoiceLine, self).on_change_product()
        if self.product:
            if self.product.principals:
                if self.principal not in self.product.principals:
                    self.principal = self.product.principal
            elif self.principal:
                self.principal = None

    @classmethod
    def view_attributes(cls):
        return super(InvoiceLine, cls).view_attributes() + [
            ('//page[@id="commissions"]', 'states', {
                    'invisible': Eval('type') != 'line',
                    })]

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('commissions', None)
        default.setdefault('from_commissions', None)
        return super(InvoiceLine, cls).copy(lines, default=default)


class CreditInvoiceStart(metaclass=PoolMeta):
    __name__ = 'account.invoice.credit.start'
    with_agent = fields.Boolean(
        "With Agent",
        help="Check to keep the original invoice's agent.")

    @classmethod
    def default_with_agent(cls):
        return True


class CreditInvoice(metaclass=PoolMeta):
    __name__ = 'account.invoice.credit'

    @property
    def _credit_options(self):
        options = super()._credit_options
        if not self.start.with_agent:
            options['agent'] = None
        return options
