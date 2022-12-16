#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import Model, fields
from trytond.pool import Pool


class Invoice(Model):
    _name = 'account.invoice'

    sales = fields.Many2Many('sale.sale-account.invoice',
            'invoice', 'sale', 'Sales', readonly=True)

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default.setdefault('sales', None)
        return super(Invoice, self).copy(ids, default=default)

    def paid(self, ids):
        pool = Pool()
        sale_obj = pool.get('sale.sale')
        super(Invoice, self).paid(ids)
        invoices = self.browse(ids)
        sale_obj.process([s.id for i in invoices for s in i.sales])

    def cancel(self, ids):
        pool = Pool()
        sale_obj = pool.get('sale.sale')
        super(Invoice, self).cancel(ids)
        invoices = self.browse(ids)
        sale_obj.process([s.id for i in invoices for s in i.sales])

Invoice()


class InvoiceLine(Model):
    _name = 'account.invoice.line'

    sale_lines = fields.Many2Many('sale.line-account.invoice.line',
            'invoice_line', 'sale_line', 'Sale Lines', readonly=True)

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default.setdefault('sale_lines', None)
        return super(InvoiceLine, self).copy(ids, default=default)

InvoiceLine()
