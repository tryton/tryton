# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from functools import wraps

from trytond.i18n import gettext
from trytond.model import Workflow, fields
from trytond.model.exceptions import AccessError
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction, without_check_access


def process_sale(func):
    @wraps(func)
    def wrapper(cls, invoices):
        pool = Pool()
        Sale = pool.get('sale.sale')
        transaction = Transaction()
        context = transaction.context
        with without_check_access():
            sales = set(s for i in cls.browse(invoices) for s in i.sales)
        result = func(cls, invoices)
        if sales:
            with transaction.set_context(
                    queue_batch=context.get('queue_batch', True)):
                Sale.__queue__.process(sales)
        return result
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
        return [('lines.origin.sale' + clause[0][len(name):],
                *clause[1:3], 'sale.line', *clause[3:])]

    def get_tax_identifier(self, pattern=None):
        if self.sales:
            pattern = pattern.copy() if pattern is not None else {}
            shipment_countries = {
                s.shipment_address.country for s in self.sales
                if s.shipment_address and s.shipment_address.country}
            if len(shipment_countries) == 1:
                shipment_country, = shipment_countries
                pattern.setdefault('country', shipment_country.id)
        return super().get_tax_identifier(pattern=pattern)

    @classmethod
    @process_sale
    def on_delete(cls, invoices):
        return super().on_delete(invoices)

    @classmethod
    @process_sale
    def _post(cls, invoices):
        super()._post(invoices)

    @classmethod
    @process_sale
    def paid(cls, invoices):
        super().paid(invoices)

    @classmethod
    @process_sale
    def cancel(cls, invoices):
        super().cancel(invoices)

    @classmethod
    @Workflow.transition('draft')
    def draft(cls, invoices):
        for invoice in invoices:
            if invoice.sales and invoice.state == 'cancelled':
                raise AccessError(
                    gettext('sale.msg_sale_invoice_reset_draft',
                        invoice=invoice.rec_name))

        return super().draft(invoices)


class Line(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        if not cls.origin.domain:
            cls.origin.domain = {}
        cls.origin.domain['sale.line'] = [
            ('type', '=', Eval('type')),
            ]

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
            category = self.origin.unit.category
        return category

    def get_warehouse(self, name):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        warehouse = super().get_warehouse(name)
        if (not warehouse
                and isinstance(self.origin, SaleLine)
                and self.origin.warehouse):
            warehouse = self.origin.warehouse.id
        return warehouse

    @property
    def origin_name(self):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        name = super().origin_name
        if isinstance(self.origin, SaleLine) and self.origin.id >= 0:
            name = self.origin.sale.rec_name
        return name

    @classmethod
    def _get_origin(cls):
        models = super()._get_origin()
        models.append('sale.line')
        return models

    @classmethod
    def on_delete(cls, lines):
        pool = Pool()
        Sale = pool.get('sale.sale')
        transaction = Transaction()
        context = transaction.context
        with without_check_access():
            invoices = (l.invoice for l in cls.browse(lines)
                if l.type == 'line' and l.invoice)
            sales = set(s for i in invoices for s in i.sales)
        if sales:
            with transaction.set_context(
                    queue_batch=context.get('queue_batch', True)):
                Sale.__queue__.process(sales)
        return super().on_delete(lines)
