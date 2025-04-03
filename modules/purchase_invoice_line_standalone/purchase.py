# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond import backend
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

    @property
    def invoice_line_standalone(self):
        party = self.invoice_party or self.party
        return party.purchase_invoice_line_standalone

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
        non_standalone = {}
        for purchase, invoice in invoices.items():
            if purchase.invoice_line_standalone:
                for line in invoice.lines:
                    if line.type == 'line':
                        line.invoice = None
                        line.party = invoice.party
                        lines.append(line)
            else:
                non_standalone[purchase] = invoice
        InvoiceLine.save(lines)

        super()._save_invoice(non_standalone)

    def get_invoice_state(self):
        state = super().get_invoice_state()
        skips = set(self.invoice_lines_ignored)
        standalone_lines = [
            l for l in self.invoice_lines if l not in skips and not l.invoice]
        if standalone_lines:
            state = {
                'paid': 'partially paid',
                'none': 'pending',
                }.get(state, state)
        return state

    @classmethod
    def copy(cls, purchases, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('invoice_lines_ignored', None)
        return super().copy(purchases, default=default)


class PurchaseIgnoredInvoiceLine(ModelSQL):
    __name__ = 'purchase.purchase-ignored-account.invoice.line'
    purchase = fields.Many2One(
        'purchase.purchase', "Purchase", ondelete='CASCADE', required=True)
    invoice = fields.Many2One(
        'account.invoice.line', "Invoice Line",
        ondelete='RESTRICT', required=True)

    @classmethod
    def __register__(cls, module):
        # Migration from 7.0: rename to standard name
        backend.TableHandler.table_rename(
            'purchase_invoice_line_ignored_rel', cls._table)
        super().__register__(module)


class HandleInvoiceException(metaclass=PoolMeta):
    __name__ = 'purchase.handle.invoice.exception'

    def transition_handle(self):
        state = super().transition_handle()

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
