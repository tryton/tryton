# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from functools import wraps

from trytond.i18n import gettext
from trytond.model import Workflow, fields
from trytond.model.exceptions import AccessError
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction


def process_sale(func):
    @wraps(func)
    def wrapper(cls, invoices):
        pool = Pool()
        Sale = pool.get('sale.sale')
        with Transaction().set_context(_check_access=False):
            sales = set(s for i in cls.browse(invoices) for s in i.sales)
        func(cls, invoices)
        if sales:
            Sale.__queue__.process(sales)
    return wrapper


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'
    sale_exception_state = fields.Function(fields.Selection([
        ('', ''),
        ('ignored', 'Ignored'),
        ('recreated', 'Recreated'),
        ], 'Exception State'), 'get_sale_exception_state')
    sales = fields.Function(fields.Many2Many(
            'sale.sale', None, None, "Sales"),
        'get_sales', searcher='search_sales')

    def get_sale_exception_state(self, name):
        sales = self.sales

        recreated = tuple(i for p in sales for i in p.invoices_recreated)
        ignored = tuple(i for p in sales for i in p.invoices_ignored)

        if self in recreated:
            return 'recreated'
        elif self in ignored:
            return 'ignored'
        return ''

    def get_sales(self, name):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        sales = set()
        for line in self.lines:
            if isinstance(line.origin, SaleLine):
                sales.add(line.origin.sale.id)
        return list(sales)

    @classmethod
    def search_sales(cls, name, clause):
        return [('lines.origin.sale' + clause[0].lstrip(name),)
            + tuple(clause[1:3]) + ('sale.line',) + tuple(clause[3:])]

    @classmethod
    def copy(cls, invoices, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('sales', None)
        return super(Invoice, cls).copy(invoices, default=default)

    @classmethod
    @process_sale
    def delete(cls, invoices):
        super(Invoice, cls).delete(invoices)

    @classmethod
    @process_sale
    def post(cls, invoices):
        super(Invoice, cls).post(invoices)

    @classmethod
    @process_sale
    def paid(cls, invoices):
        super(Invoice, cls).paid(invoices)

    @classmethod
    @process_sale
    def cancel(cls, invoices):
        super(Invoice, cls).cancel(invoices)

    @classmethod
    @Workflow.transition('draft')
    def draft(cls, invoices):
        for invoice in invoices:
            if invoice.sales and invoice.state == 'cancelled':
                raise AccessError(
                    gettext('sale.msg_sale_invoice_reset_draft',
                        invoice=invoice.rec_name))

        return super(Invoice, cls).draft(invoices)


class Line(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @fields.depends('origin')
    def on_change_with_product_uom_category(self, name=None):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        category = super().on_change_with_product_uom_category(name=name)
        # Enforce the same unit category as they are used to compute the
        # remaining quantity to invoice and the quantity to ship.
        # Use getattr as reference field can have negative id
        if (isinstance(self.origin, SaleLine)
                and getattr(self.origin, 'unit', None)):
            category = self.origin.unit.category.id
        return category

    @property
    def origin_name(self):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        name = super().origin_name
        if isinstance(self.origin, SaleLine):
            name = self.origin.sale.rec_name
        return name

    @classmethod
    def _get_origin(cls):
        models = super()._get_origin()
        models.append('sale.line')
        return models

    @classmethod
    def delete(cls, lines):
        pool = Pool()
        Sale = pool.get('sale.sale')
        with Transaction().set_context(_check_access=False):
            invoices = (l.invoice for l in cls.browse(lines)
                if l.type == 'line' and l.invoice)
            sales = set(s for i in invoices for s in i.sales)
        super().delete(lines)
        if sales:
            Sale.__queue__.process(sales)
