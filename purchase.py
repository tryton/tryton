#This file is part of Tryton.  The COPYRIGHT file at the top level
#of this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.pool import Pool


class Purchase(ModelSQL, ModelView):
    _name = 'purchase.purchase'

    invoice_lines = fields.Many2Many('purchase.purchase-account.invoice.line',
            'purchase', 'line', 'Invoice Lines', readonly=True)
    invoice_lines_ignored = fields.Many2Many(
            'purchase.purchase-ignored-account.invoice.line',
            'purchase', 'invoice', 'Invoice Lines Ignored', readonly=True)

    def init(self, module_name):
        cursor = Transaction().cursor
        # Migration from 1.2: packing renamed into shipment
        cursor.execute("UPDATE ir_model_data "\
                "SET fs_id = REPLACE(fs_id, 'packing', 'shipment') "\
                "WHERE fs_id like '%%packing%%' "\
                    "AND module = %s", (module_name,))

        super(Purchase, self).init(module_name)

    def create_invoice(self, purchase):
        invoice_obj = Pool().get('account.invoice')
        invoice_line_obj = Pool().get('account.invoice.line')

        invoice_id = super(Purchase, self).create_invoice(purchase)

        if invoice_id:
            invoice = invoice_obj.browse(invoice_id)
            line_ids = [x.id for x in invoice.lines]
            with Transaction().set_user(0, set_context=True):
                invoice_line_obj.write(line_ids, {
                    'invoice': None,
                    'invoice_type': invoice.type,
                    'party': invoice.party,
                    'currency': invoice.currency.id,
                    'company': invoice.company.id,
                    })
            self.write(purchase.id, {
                'invoices': [('unlink', invoice_id)],
                'invoice_lines': [('add', line_ids)],
                })
            with Transaction().set_user(0, set_context=True):
                invoice_obj.cancel([invoice_id])
                invoice_obj.delete(invoice_id)
            return None
        return invoice_id

    def get_invoice_state(self, purchase):
        state = super(Purchase, self).get_invoice_state(purchase)
        skip_ids = set(x.id for x in purchase.invoice_lines_ignored)
        invoice_lines = [l for l in purchase.invoice_lines
            if l.id not in skip_ids]
        if invoice_lines:
            if any(l.invoice and l.invoice.state == 'cancel'
                    for l in invoice_lines):
                return 'exception'
            elif (state == 'paid'
                    and all(l.invoice for l in invoice_lines)
                    and all(l.invoice.state == 'paid' for l in invoice_lines)):
                return 'paid'
        return state

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['invoice_lines'] = None
        default['invoice_lines_ignored'] = None
        return super(Purchase, self).copy(ids, default=default)

    def ignore_invoice_exception(self, purchase_id):
        super(Purchase, self).ignore_invoice_exception(purchase_id)
        purchase = self.browse(purchase_id)
        invoice_line_ids = []
        for invoice_line in purchase.invoice_lines:
            if invoice_line.invoice \
                    and invoice_line.invoice.state == 'cancel':
                invoice_line_ids.append(invoice_line.id)
        if invoice_line_ids:
            self.write(purchase_id, {
                    'invoice_lines_ignored': [
                        ('add', x) for x in invoice_line_ids],
                    })

Purchase()


class PurchaseInvoiceLine(ModelSQL):
    'Purchase - Invoice Line'
    _name = 'purchase.purchase-account.invoice.line'
    _table = 'purchase_invoice_line_rel'
    _description = __doc__
    purchase = fields.Many2One('purchase.purchase', 'Purchase',
            ondelete='CASCADE', select=True, required=True)
    line = fields.Many2One('account.invoice.line', 'Invoice Line',
            ondelete='RESTRICT', select=True, required=True)

PurchaseInvoiceLine()


class PurchaseIgnoredInvoiceLine(ModelSQL):
    'Purchase - Ignored Invoice Line'
    _name = 'purchase.purchase-ignored-account.invoice.line'
    _table = 'purchase_invoice_line_ignored_rel'
    _description = __doc__
    purchase = fields.Many2One('purchase.purchase', 'Purchase',
            ondelete='CASCADE', select=True, required=True)
    invoice = fields.Many2One('account.invoice.line', 'Invoice Line',
            ondelete='RESTRICT', select=True, required=True)

PurchaseIgnoredInvoiceLine()
