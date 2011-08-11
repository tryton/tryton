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

    def create_invoice(self, purchase_id):
        invoice_obj = Pool().get('account.invoice')
        invoice_line_obj = Pool().get('account.invoice.line')

        res = super(Purchase, self).create_invoice(purchase_id)

        if res:
            invoice = invoice_obj.browse(res)
            line_ids = [x.id for x in invoice.lines]
            with Transaction().set_user(0, set_context=True):
                invoice_line_obj.write(line_ids, {
                    'invoice': False,
                    'invoice_type': invoice.type,
                    'party': invoice.party,
                    'currency': invoice.currency.id,
                    'company': invoice.company.id,
                    })
            self.write(purchase_id, {
                'invoices': [('unlink', res)],
                'invoice_lines': [('add', line_ids)],
                })
            with Transaction().set_user(0, set_context=True):
                invoice_obj.workflow_trigger_validate(res, 'cancel')
                invoice_obj.delete(res)
            res = None
        return res

    def get_invoice_paid(self, purchases):
        res = super(Purchase, self).get_invoice_paid(purchases)
        for purchase in purchases:
            val = True
            ignored_ids = [x.id for x in purchase.invoice_lines_ignored]
            for invoice_line in purchase.invoice_lines:
                if not invoice_line.invoice:
                    val = False
                    break
                if invoice_line.invoice.state != 'paid' \
                        and invoice_line.id not in ignored_ids:
                    val = False
                    break
            res[purchase.id] = val
        return res

    def get_invoice_exception(self, purchases):
        res = super(Purchase, self).get_invoice_exception(purchases)

        for purchase in purchases:
            val = False
            ignored_ids = [x.id for x in purchase.invoice_lines_ignored]
            for invoice_line in purchase.invoice_lines:
                if invoice_line.invoice \
                        and invoice_line.invoice.state == 'cancel' \
                        and invoice_line.id not in ignored_ids:
                    val = True
                    break
            res[purchase.id] = val
        return res

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['invoice_lines'] = False
        default['invoice_lines_ignored'] = False
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
                'invoice_lines_ignored': [('add', x) for x in invoice_line_ids],
                })

    def wkf_triggered_invoice_lines(self, purchase):
        return [x.id for x in purchase.invoice_lines]

Purchase()


class PurchaseInvoiceLine(ModelSQL):
    'Purchase - Invoice Line'
    _name = 'purchase.purchase-account.invoice.line'
    _table = 'purchase_invoice_line_rel'
    _description = __doc__
    purchase = fields.Many2One('purchase.purchase', 'Purchase',
            ondelete='CASCADE', select=1, required=True)
    line = fields.Many2One('account.invoice.line', 'Invoice Line',
            ondelete='RESTRICT', select=1, required=True)

PurchaseInvoiceLine()


class PurchaseIgnoredInvoiceLine(ModelSQL):
    'Purchase - Ignored Invoice Line'
    _name = 'purchase.purchase-ignored-account.invoice.line'
    _table = 'purchase_invoice_line_ignored_rel'
    _description = __doc__
    purchase = fields.Many2One('purchase.purchase', 'Purchase',
            ondelete='CASCADE', select=1, required=True)
    invoice = fields.Many2One('account.invoice.line', 'Invoice Line',
            ondelete='RESTRICT', select=1, required=True)

PurchaseIgnoredInvoiceLine()
