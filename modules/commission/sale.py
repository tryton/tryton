# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from __future__ import unicode_literals

from trytond.pool import PoolMeta
from trytond.model import fields
from trytond.pyson import Eval


__all__ = ['Sale', 'SaleLine']


class Sale:
    __metaclass__ = PoolMeta
    __name__ = 'sale.sale'
    agent = fields.Many2One('commission.agent', 'Commission Agent',
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        states={
            'readonly': Eval('state', '') != 'draft',
            },
        depends=['state', 'company'])

    def create_invoice(self):
        invoice = super(Sale, self).create_invoice()
        if invoice:
            invoice.agent = self.agent
            invoice.save()
        return invoice


class SaleLine:
    __metaclass__ = PoolMeta
    __name__ = 'sale.line'
    principal = fields.Many2One('commission.agent', 'Commission Principal',
        domain=[
            ('type_', '=', 'principal'),
            ('company', '=', Eval('_parent_sale', {}).get('company', -1)),
            ])

    def get_invoice_line(self):
        lines = super(SaleLine, self).get_invoice_line()
        if self.principal:
            for line in lines:
                if line.product == self.product:
                    line.principal = self.principal
        return lines

    @fields.depends('product', 'principal')
    def on_change_product(self):
        super(SaleLine, self).on_change_product()
        if self.product:
            if self.product.principals:
                if self.principal not in self.product.principals:
                    self.principal = self.product.principal
            elif self.principal:
                self.principal = None

    @classmethod
    def view_attributes(cls):
        return super(SaleLine, cls).view_attributes() + [
            ('//page[@id="commissions"]', 'states', {
                    'invisible': Eval('type') != 'line',
                    })]
