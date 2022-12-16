#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields


class Invoice(ModelSQL, ModelView):
    _name = 'account.invoice'

    sales = fields.Many2Many('sale.sale-account.invoice',
            'invoice', 'sale', 'Sales', readonly=True)

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default.setdefault('sales', False)
        return super(Invoice, self).copy(ids, default=default)

Invoice()


class InvoiceLine(ModelSQL, ModelView):
    _name = 'account.invoice.line'

    sale_lines = fields.Many2Many('sale.line-account.invoice.line',
            'invoice_line', 'sale_line', 'Sale Lines', readonly=True)

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default.setdefault('sale_lines', False)
        return super(InvoiceLine, self).copy(ids, default=default)

InvoiceLine()
