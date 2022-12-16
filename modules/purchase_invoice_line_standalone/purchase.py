# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields
from trytond.pool import Pool, PoolMeta


class Purchase(metaclass=PoolMeta):
    __name__ = 'purchase.purchase'
    invoice_lines = fields.Function(fields.Many2Many(
            'account.invoice.line', None, None, "Invoice Lines"),
        'get_invoice_lines', searcher='search_invoice_lines')
    invoice_lines_ignored = fields.Many2Many(
            'purchase.purchase-ignored-account.invoice.line',
            'purchase', 'invoice', 'Invoice Lines Ignored', readonly=True)

    def get_invoice_lines(self, name):
        return list({il.id for l in self.lines for il in l.invoice_lines})

    @classmethod
    def search_invoice_lines(cls, name, clause):
        return [('lines.' + clause[0],) + tuple(clause[1:])]

    @classmethod
    def _save_invoice(cls, invoices):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')

        lines = []
        for invoice in invoices.values():
            for line in invoice.lines:
                if line.type == 'line':
                    line.invoice = None
                    line.party = invoice.party
                    lines.append(line)
        InvoiceLine.save(lines)

        super()._save_invoice({})

    def get_invoice_state(self):
        state = super(Purchase, self).get_invoice_state()
        skips = set(x.id for x in self.invoice_lines_ignored)
        invoice_lines = [l for l in self.invoice_lines if l.id not in skips]
        if invoice_lines:
            if any(l.invoice and l.invoice.state == 'cancelled'
                    for l in invoice_lines):
                return 'exception'
            elif (state == 'paid'
                    and all(l.invoice for l in invoice_lines)
                    and all(l.invoice.state == 'paid' for l in invoice_lines)):
                return 'paid'
            else:
                return 'waiting'
        return state

    @classmethod
    def copy(cls, purchases, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('invoice_lines_ignored', None)
        return super(Purchase, cls).copy(purchases, default=default)


class PurchaseIgnoredInvoiceLine(ModelSQL):
    'Purchase - Ignored Invoice Line'
    __name__ = 'purchase.purchase-ignored-account.invoice.line'
    _table = 'purchase_invoice_line_ignored_rel'
    purchase = fields.Many2One('purchase.purchase', 'Purchase',
            ondelete='CASCADE', select=True, required=True)
    invoice = fields.Many2One('account.invoice.line', 'Invoice Line',
            ondelete='RESTRICT', select=True, required=True)


class HandleInvoiceException(metaclass=PoolMeta):
    __name__ = 'purchase.handle.invoice.exception'

    def transition_handle(self):
        state = super(HandleInvoiceException, self).transition_handle()

        invoice_lines = []
        for invoice_line in self.record.invoice_lines:
            if (invoice_line.invoice
                    and invoice_line.invoice.state == 'cancelled'):
                invoice_lines.append(invoice_line.id)
        if invoice_lines:
            self.model.write([self.record], {
                    'invoice_lines_ignored': [('add', invoice_lines)],
                    })
        self.model.__queue__.process([self.record])
        return state
