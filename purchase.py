#This file is part of Tryton.  The COPYRIGHT file at the top level
#of this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

__all__ = ['Purchase', 'PurchaseInvoiceLine', 'PurchaseIgnoredInvoiceLine',
    'HandleInvoiceException']
__metaclass__ = PoolMeta


class Purchase:
    __name__ = 'purchase.purchase'
    invoice_lines = fields.Many2Many('purchase.purchase-account.invoice.line',
            'purchase', 'line', 'Invoice Lines', readonly=True)
    invoice_lines_ignored = fields.Many2Many(
            'purchase.purchase-ignored-account.invoice.line',
            'purchase', 'invoice', 'Invoice Lines Ignored', readonly=True)

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        # Migration from 1.2: packing renamed into shipment
        cursor.execute("UPDATE ir_model_data "
            "SET fs_id = REPLACE(fs_id, 'packing', 'shipment') "
            "WHERE fs_id like '%%packing%%' "
                "AND module = %s", (module_name,))

        super(Purchase, cls).__register__(module_name)

    def create_invoice(self, invoice_type):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        InvoiceLine = pool.get('account.invoice.line')

        invoice = super(Purchase, self).create_invoice(invoice_type)

        if invoice:
            lines_to_delete = [l for l in invoice.lines if l.type != 'line']
            lines = [l for l in invoice.lines if l.type == 'line']
            invoice_line_ids = [l.id for l in lines]
            with Transaction().set_user(0, set_context=True):
                InvoiceLine.write(lines, {
                    'invoice': None,
                    'invoice_type': invoice.type,
                    'party': invoice.party.id,
                    'currency': invoice.currency.id,
                    'company': invoice.company.id,
                    })
                InvoiceLine.delete(lines_to_delete)
            self.write([self], {
                'invoices': [('unlink', [invoice.id])],
                'invoice_lines': [('add', invoice_line_ids)],
                })
            with Transaction().set_user(0, set_context=True):
                Invoice.cancel([invoice])
                Invoice.delete([invoice])
            return None
        return invoice

    def get_invoice_state(self):
        state = super(Purchase, self).get_invoice_state()
        skips = set(x.id for x in self.invoice_lines_ignored)
        invoice_lines = [l for l in self.invoice_lines if l.id not in skips]
        if invoice_lines:
            if any(l.invoice and l.invoice.state == 'cancel'
                    for l in invoice_lines):
                return 'exception'
            elif (state == 'paid'
                    and all(l.invoice for l in invoice_lines)
                    and all(l.invoice.state == 'paid' for l in invoice_lines)):
                return 'paid'
        return state

    @classmethod
    def copy(cls, purchases, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['invoice_lines'] = None
        default['invoice_lines_ignored'] = None
        return super(Purchase, cls).copy(purchases, default=default)


class PurchaseInvoiceLine(ModelSQL):
    'Purchase - Invoice Line'
    __name__ = 'purchase.purchase-account.invoice.line'
    _table = 'purchase_invoice_line_rel'
    purchase = fields.Many2One('purchase.purchase', 'Purchase',
            ondelete='CASCADE', select=True, required=True)
    line = fields.Many2One('account.invoice.line', 'Invoice Line',
            ondelete='RESTRICT', select=True, required=True)


class PurchaseIgnoredInvoiceLine(ModelSQL):
    'Purchase - Ignored Invoice Line'
    __name__ = 'purchase.purchase-ignored-account.invoice.line'
    _table = 'purchase_invoice_line_ignored_rel'
    purchase = fields.Many2One('purchase.purchase', 'Purchase',
            ondelete='CASCADE', select=True, required=True)
    invoice = fields.Many2One('account.invoice.line', 'Invoice Line',
            ondelete='RESTRICT', select=True, required=True)


class HandleInvoiceException:
    __name__ = 'purchase.handle.invoice.exception'

    def transition_handle(self):
        Purchase = Pool().get('purchase.purchase')

        state = super(HandleInvoiceException, self).transition_handle()

        purchase = Purchase(Transaction().context['active_id'])
        invoice_lines = []
        for invoice_line in purchase.invoice_lines:
            if (invoice_line.invoice
                    and invoice_line.invoice.state == 'cancel'):
                invoice_lines.append(invoice_line.id)
        if invoice_lines:
            Purchase.write([purchase], {
                    'invoice_lines_ignored': [('add', invoice_lines)],
                    })
        Purchase.process([purchase])
        return state
