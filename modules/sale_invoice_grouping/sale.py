# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool, PoolMeta

__all__ = ['Sale']


class Sale:
    __metaclass__ = PoolMeta
    __name__ = 'sale.sale'

    @property
    def invoice_grouping_method(self):
        return self.party.sale_invoice_grouping_method

    @property
    def _invoice_grouping_fields(self):
        return ('state', 'company', 'type', 'journal', 'party',
            'invoice_address', 'currency', 'account', 'payment_term')

    def _get_grouped_invoice_order(self):
        "Returns the order clause used to find invoice that should be grouped"
        return None

    def _get_grouped_invoice_domain(self, invoice):
        "Returns a domain that will find invoices that should be grouped"
        Invoice = Pool().get('account.invoice')
        invoice_domain = [
            ('lines.origin', 'like', 'sale.line,%'),
            ]
        defaults = Invoice.default_get(self._invoice_grouping_fields,
            with_rec_name=False)
        for field in self._invoice_grouping_fields:
            invoice_domain.append(
                (field, '=', getattr(invoice, field, defaults.get(field)))
                )
        return invoice_domain

    def _get_invoice_sale(self):
        Invoice = Pool().get('account.invoice')
        invoice = super(Sale, self)._get_invoice_sale()
        if self.invoice_grouping_method:
            domain = self._get_grouped_invoice_domain(invoice)
            order = self._get_grouped_invoice_order()
            grouped_invoices = Invoice.search(domain, order=order, limit=1)
            if grouped_invoices:
                invoice, = grouped_invoices
        return invoice
