# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from functools import wraps

from trytond.i18n import gettext
from trytond.model import ModelView, Workflow, fields
from trytond.model.exceptions import AccessError
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.tools import cached_property
from trytond.transaction import Transaction, without_check_access


def process_purchase(func):
    @wraps(func)
    def wrapper(cls, invoices):
        pool = Pool()
        Purchase = pool.get('purchase.purchase')
        transaction = Transaction()
        context = transaction.context
        with without_check_access():
            purchases = set(
                p for i in cls.browse(invoices) for p in i.purchases)
        result = func(cls, invoices)
        if purchases:
            with transaction.set_context(
                    queue_batch=context.get('queue_batch', True)):
                Purchase.__queue__.process(purchases)
        return result
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
        return [('lines.origin.purchase' + clause[0][len(name):],
                *clause[1:3], 'purchase.line', *clause[3:])]

    @classmethod
    @process_purchase
    def on_delete(cls, invoices):
        return super().on_delete(invoices)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, invoices):
        for invoice in invoices:
            if invoice.purchases and invoice.state == 'cancelled':
                raise AccessError(
                    gettext('purchase.msg_purchase_invoice_reset_draft',
                        invoice=invoice.rec_name))

        return super().draft(invoices)

    @classmethod
    @process_purchase
    def _post(cls, invoices):
        super()._post(invoices)

    @classmethod
    @process_purchase
    def paid(cls, invoices):
        super().paid(invoices)

    @classmethod
    @process_purchase
    def cancel(cls, invoices):
        super().cancel(invoices)


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        if not cls.origin.domain:
            cls.origin.domain = {}
        cls.origin.domain['purchase.line'] = [
            ('type', '=', Eval('type')),
            ]

    @cached_property
    def product_name(self):
        pool = Pool()
        PurchaseLine = pool.get('purchase.line')
        name = super().product_name
        if (isinstance(self.origin, PurchaseLine)
                and self.origin.product_supplier):
            name = self.origin.product_supplier.rec_name
        return name

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
            category = self.origin.unit.category
        return category

    def get_warehouse(self, name):
        pool = Pool()
        PurchaseLine = pool.get('purchase.line')
        warehouse = super().get_warehouse(name)
        if (not warehouse
                and isinstance(self.origin, PurchaseLine)
                and self.origin.purchase.warehouse):
            warehouse = self.origin.purchase.warehouse.id
        return warehouse

    @property
    def origin_name(self):
        pool = Pool()
        PurchaseLine = pool.get('purchase.line')
        name = super().origin_name
        if isinstance(self.origin, PurchaseLine) and self.origin.id >= 0:
            name = self.origin.purchase.rec_name
        return name

    @classmethod
    def _get_origin(cls):
        models = super()._get_origin()
        models.append('purchase.line')
        return models

    @classmethod
    def on_delete(cls, lines):
        pool = Pool()
        Purchase = pool.get('purchase.purchase')
        transaction = Transaction()
        context = transaction.context
        with without_check_access():
            invoices = (l.invoice for l in cls.browse(lines)
                if l.type == 'line' and l.invoice)
            purchases = set(p for i in invoices for p in i.purchases)
        if purchases:
            with transaction.set_context(
                    queue_batch=context.get('queue_batch', True)):
                Purchase.__queue__.process(purchases)
        return super().on_delete(lines)
