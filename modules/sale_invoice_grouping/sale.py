# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta
from trytond.transaction import Transaction


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    @property
    def invoice_grouping_method(self):
        party = self.invoice_party or self.party
        return party.sale_invoice_grouping_method

    @property
    def _invoice_grouping_fields(self):
        return ('state', 'company', 'type', 'journal', 'party',
            'invoice_address', 'currency', 'account', 'payment_term')

    def _get_grouped_invoice_order(self):
        "Returns the order clause used to find invoice that should be grouped"
        return None

    def _get_grouped_invoice_domain(self, invoice):
        "Returns a domain that will find invoices that should be grouped"
        Invoice = invoice.__class__
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
        transaction = Transaction()
        context = transaction.context
        invoice = super(Sale, self)._get_invoice_sale()
        if (not context.get('skip_grouping', False)
                and self.invoice_grouping_method):
            with transaction.set_context(skip_grouping=True):
                invoice = self._get_invoice_sale()
            Invoice = invoice.__class__
            domain = self._get_grouped_invoice_domain(invoice)
            order = self._get_grouped_invoice_order()
            grouped_invoices = Invoice.search(domain, order=order, limit=1)
            if grouped_invoices:
                invoice, = grouped_invoices
        return invoice
