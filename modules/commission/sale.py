# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.


from trytond.pool import PoolMeta, Pool
from trytond.model import ModelView, Workflow, fields
from trytond.pyson import Eval
from trytond.transaction import Transaction


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'
    agent = fields.Many2One('commission.agent', 'Commission Agent',
        domain=[
            ('type_', '=', 'agent'),
            ('company', '=', Eval('company', -1)),
            ],
        states={
            'readonly': ~Eval('state').in_(['draft', 'quotation']),
            },
        depends=['state', 'company'],
        help="The agent who receives a commission for the sale.")

    def create_invoice(self):
        invoice = super(Sale, self).create_invoice()
        if invoice:
            invoice.agent = self.agent
            invoice.save()
        return invoice

    @classmethod
    @ModelView.button
    @Workflow.transition('quotation')
    def quote(cls, sales):
        cls.set_agent(sales)
        super().quote(sales)

    def _get_agent_pattern(self):
        pattern = {}
        pattern['date'] = self.sale_date
        pattern['company'] = self.company.id
        pattern['party'] = self.party.id
        if self.quoted_by:
            pattern['employee'] = self.quoted_by.id
        else:
            pattern['employee'] = Transaction().context.get('employee')
        return pattern

    @classmethod
    def _get_agent_selection_domain(cls, pattern):
        domain = []
        if 'company' in pattern:
            domain.append(('agent.company', '=', pattern['company']))
        if 'party' in pattern:
            domain.append(('party', 'in', [None, pattern['party']]))
        if 'employee' in pattern:
            domain.append(('employee', 'in', [None, pattern['employee']]))
        return domain

    @classmethod
    def set_agent(cls, sales):
        pool = Pool()
        AgentSelection = pool.get('commission.agent.selection')

        for sale in sales:
            if sale.agent:
                continue
            pattern = sale._get_agent_pattern()
            for selection in AgentSelection.search(
                    cls._get_agent_selection_domain(pattern)):
                if selection.match(pattern):
                    sale.agent = selection.agent
                    break
        cls.save(sales)


class Line(metaclass=PoolMeta):
    __name__ = 'sale.line'
    principal = fields.Many2One('commission.agent', 'Commission Principal',
        domain=[
            ('type_', '=', 'principal'),
            ('company', '=', Eval('_parent_sale', {}).get('company', -1)),
            ],
        help="The principal who pays a commission for the line.")

    def get_invoice_line(self):
        lines = super().get_invoice_line()
        if self.principal:
            for line in lines:
                if line.product == self.product:
                    line.principal = self.principal
        return lines

    @fields.depends('product', 'principal')
    def on_change_product(self):
        super().on_change_product()
        if self.product:
            if self.product.principals:
                if self.principal not in self.product.principals:
                    self.principal = self.product.principal
            elif self.principal:
                self.principal = None

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('//page[@id="commissions"]', 'states', {
                    'invisible': Eval('type') != 'line',
                    })]
