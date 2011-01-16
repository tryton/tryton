#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields


class Invoice(ModelSQL, ModelView):
    _name = 'account.invoice'

    purchases = fields.Many2Many('purchase.purchase-account.invoice',
            'invoice', 'purchase', 'Purchases', readonly=True)

Invoice()


class InvoiceLine(ModelSQL, ModelView):
    _name = 'account.invoice.line'

    purchase_lines = fields.Many2Many('purchase.line-account.invoice.line',
            'invoice_line', 'purchase_line', 'Purchase Lines', readonly=True)

InvoiceLine()
