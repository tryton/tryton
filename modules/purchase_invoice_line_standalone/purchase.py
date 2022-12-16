# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields
from trytond.transaction import Transaction
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

    def create_invoice(self):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        InvoiceLine = pool.get('account.invoice.line')

        invoice = super(Purchase, self).create_invoice()

        if invoice:
            lines_to_delete = [l for l in invoice.lines if l.type != 'line']
            lines = [l for l in invoice.lines if l.type == 'line']
            InvoiceLine.write(lines, {
                'invoice': None,
                'invoice_type': invoice.type,
                'party': invoice.party.id,
                })
            InvoiceLine.delete(lines_to_delete)
            Invoice.cancel([invoice])
            Invoice.delete([invoice])
            return None
        return invoice

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
