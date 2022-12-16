# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from functools import wraps

from trytond.i18n import gettext
from trytond.model import ModelView, Workflow, fields
from trytond.model.exceptions import AccessError
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction


def process_purchase(func):
    @wraps(func)
    def wrapper(cls, invoices):
        pool = Pool()
        Purchase = pool.get('purchase.purchase')
        with Transaction().set_context(_check_access=False):
            purchases = set(
                p for i in cls.browse(invoices) for p in i.purchases)
        func(cls, invoices)
        if purchases:
            Purchase.__queue__.process(purchases)
    return wrapper


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'
    purchase_exception_state = fields.Function(fields.Selection([
        ('', ''),
        ('ignored', 'Ignored'),
        ('recreated', 'Recreated'),
        ], 'Exception State'), 'get_purchase_exception_state')
    purchases = fields.Function(fields.Many2Many(
            'purchase.purchase', None, None, "Purchases"),
        'get_purchases', searcher='search_purchases')

    def get_purchase_exception_state(self, name):
        purchases = self.purchases

        recreated = tuple(i for p in purchases for i in p.invoices_recreated)
        ignored = tuple(i for p in purchases for i in p.invoices_ignored)

        if self in recreated:
            return 'recreated'
        elif self in ignored:
            return 'ignored'
        return ''

    def get_purchases(self, name):
        pool = Pool()
        PurchaseLine = pool.get('purchase.line')
        purchases = set()
        for line in self.lines:
            if isinstance(line.origin, PurchaseLine):
                purchases.add(line.origin.purchase.id)
        return list(purchases)

    @classmethod
    def search_purchases(cls, name, clause):
        return [('lines.origin.purchase' + clause[0].lstrip(name),)
            + tuple(clause[1:3]) + ('purchase.line',) + tuple(clause[3:])]

    @classmethod
    @process_purchase
    def delete(cls, invoices):
        super(Invoice, cls).delete(invoices)

    @classmethod
    def copy(cls, invoices, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('purchases', None)
        return super(Invoice, cls).copy(invoices, default=default)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, invoices):
        for invoice in invoices:
            if invoice.purchases and invoice.state == 'cancelled':
                raise AccessError(
                    gettext('purchase.msg_purchase_invoice_reset_draft',
                        invoice=invoice.rec_name))

        return super(Invoice, cls).draft(invoices)

    @classmethod
    @process_purchase
    def post(cls, invoices):
        super(Invoice, cls).post(invoices)

    @classmethod
    @process_purchase
    def paid(cls, invoices):
        super(Invoice, cls).paid(invoices)

    @classmethod
    @process_purchase
    def cancel(cls, invoices):
        super(Invoice, cls).cancel(invoices)


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @fields.depends('origin')
    def on_change_with_product_uom_category(self, name=None):
        pool = Pool()
        PurchaseLine = pool.get('purchase.line')
        category = super().on_change_with_product_uom_category(name=name)
        # Enforce the same unit category as they are used to compute the
        # remaining quantity to invoice and the quantity to receive.
        # Use getattr as reference field can have negative id
        if (isinstance(self.origin, PurchaseLine)
                and getattr(self.origin, 'unit', None)):
            category = self.origin.unit.category.id
        return category

    @property
    def origin_name(self):
        pool = Pool()
        PurchaseLine = pool.get('purchase.line')
        name = super(InvoiceLine, self).origin_name
        if isinstance(self.origin, PurchaseLine):
            name = self.origin.purchase.rec_name
        return name

    @classmethod
    def _get_origin(cls):
        models = super(InvoiceLine, cls)._get_origin()
        models.append('purchase.line')
        return models

    @classmethod
    def delete(cls, lines):
        pool = Pool()
        Purchase = pool.get('purchase.purchase')
        with Transaction().set_context(_check_access=False):
            invoices = (l.invoice for l in cls.browse(lines)
                if l.type == 'line' and l.invoice)
            purchases = set(p for i in invoices for p in i.purchases)
        super(InvoiceLine, cls).delete(lines)
        if purchases:
            Purchase.__queue__.process(purchases)
