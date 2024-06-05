# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from itertools import groupby

from trytond.pool import PoolMeta
from trytond.transaction import Transaction


class InvoiceGroupingMixin:
    __slots__ = ()

    @property
    def invoice_grouping_method(self):
        party = self.invoice_party or self.party
        return party.sale_invoice_grouping_method

    @property
    def _invoice_grouping_origins(self):
        return ['sale.line', 'sale.rental.line']

    def _get_invoice_grouping_fields(self, invoice):
        return {'state', 'company', 'type', 'journal', 'party',
            'invoice_address', 'currency', 'account', 'payment_term'}

    def _get_grouped_invoice_order(self):
        "Returns the order clause used to find invoice that should be grouped"
        return None

    def _get_grouped_invoice_domain(self, invoice):
        "Returns a domain that will find invoices that should be grouped"
        Invoice = invoice.__class__
        invoice_domain = [
            ['OR'] + [
                ('lines.origin', 'like', f'{o},%')
                for o in self._invoice_grouping_origins],
            ]
        fields = self._get_invoice_grouping_fields(invoice)
        defaults = Invoice.default_get(fields, with_rec_name=False)
        for field in fields:
            invoice_domain.append(
                (field, '=', getattr(invoice, field, defaults.get(field)))
                )
        return invoice_domain

    def _get_invoice(self):
        transaction = Transaction()
        context = transaction.context
        invoice = super()._get_invoice()
        if (not context.get('skip_grouping', False)
                and self.invoice_grouping_method):
            with transaction.set_context(skip_grouping=True):
                invoice = self._get_invoice()
            Invoice = invoice.__class__
            domain = self._get_grouped_invoice_domain(invoice)
            order = self._get_grouped_invoice_order()
            grouped_invoices = Invoice.search(domain, order=order, limit=1)
            if grouped_invoices:
                invoice, = grouped_invoices
        return invoice


class Sale(InvoiceGroupingMixin, metaclass=PoolMeta):
    __name__ = 'sale.sale'

    @classmethod
    def _process_invoice(cls, sales):
        for method, sales in groupby(
                sales, lambda s: s.invoice_grouping_method):
            if method:
                for sale in sales:
                    super()._process_invoice([sale])
            else:
                super()._process_invoice(list(sales))


class Rental(InvoiceGroupingMixin, metaclass=PoolMeta):
    __name__ = 'sale.rental'

    @classmethod
    def invoice(cls, rentals):
        for method, rentals in groupby(
                rentals, lambda r: r.invoice_grouping_method):
            if method:
                for rental in rentals:
                    super().invoice([rental])
            else:
                super().invoice(list(rentals))
