#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import Model, fields
from trytond.pool import Pool


class Invoice(Model):
    _name = 'account.invoice'

    purchases = fields.Many2Many('purchase.purchase-account.invoice',
            'invoice', 'purchase', 'Purchases', readonly=True)

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default.setdefault('purchases', None)
        return super(Invoice, self).copy(ids, default=default)

    def paid(self, ids):
        pool = Pool()
        purchase_obj = pool.get('purchase.purchase')
        super(Invoice, self).paid(ids)
        invoices = self.browse(ids)
        purchase_obj.process([p.id for i in invoices for p in i.purchases])

    def cancel(self, ids):
        pool = Pool()
        purchase_obj = pool.get('purchase.purchase')
        super(Invoice, self).cancel(ids)
        invoices = self.browse(ids)
        purchase_obj.process([p.id for i in invoices for p in i.purchases])

Invoice()


class InvoiceLine(Model):
    _name = 'account.invoice.line'

    purchase_lines = fields.Many2Many('purchase.line-account.invoice.line',
            'invoice_line', 'purchase_line', 'Purchase Lines', readonly=True)

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default.setdefault('purchase_lines', None)
        return super(InvoiceLine, self).copy(ids, default=default)

InvoiceLine()
