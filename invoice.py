#This file is part of Tryton.  The COPYRIGHT file at the top level
#of this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.pool import Pool


class Invoice(ModelSQL, ModelView):
    _name = 'account.invoice'

    def write(self, ids, vals):
        invoice_line_obj = Pool().get('account.invoice.line')
        purchase_obj = Pool().get('purchase.purchase')
        res = super(Invoice, self).write(ids, vals)
        if 'state' in vals and vals['state'] in ('paid', 'cancel'):
            if isinstance(ids, (int, long)):
                ids = [ids]
            purchase_ids = purchase_obj.search([
                ('invoices', 'in', ids),
                ])
            for purchase in purchase_obj.browse(purchase_ids):
                invoice_line_obj.workflow_trigger_trigger(
                        [x.id for x in purchase.invoice_lines])
        return res

Invoice()


class InvoiceLine(ModelSQL, ModelView):
    _name = 'account.invoice.line'

    def __init__(self):
        super(InvoiceLine, self).__init__()
        self._error_messages.update({
            'delete_purchase_invoice_line': 'You can not delete ' \
                    'invoice lines that comes from a purchase!',
            })

    def write(self, ids, vals):
        purchase_obj = Pool().get('purchase.purchase')

        if 'invoice' in vals:
            if isinstance(ids, (int, long)):
                ids = [ids]

            purchase_ids = purchase_obj.search([
                ('invoice_lines', 'in', ids),
                ])
            if vals['invoice']:
                purchase_obj.write(purchase_ids, {
                    'invoices': [('add', vals['invoice'])],
                    })
            else:
                purchases = purchase_obj.browse(purchase_ids)
                for purchase in purchases:
                    invoice_ids = list(set([x.invoice.id for x \
                            in purchase.invoice_lines \
                            if x.invoice and x.id in ids]) - \
                            set([x.invoice.id for x \
                            in purchase.invoice_lines \
                            if x.invoice and x.id not in ids]))
                    purchase_obj.write(purchase.id, {
                        'invoices': [('unlink', invoice_ids)],
                        })

        return super(InvoiceLine, self).write(ids, vals)

    def delete(self, ids):
        cursor = Transaction().cursor
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        cursor.execute('SELECT id FROM purchase_invoice_line_rel ' \
                'WHERE line IN (' + ','.join(['%s' for x in ids]) + ')',
                ids)
        if cursor.rowcount:
            self.raise_user_error('delete_purchase_invoice_line')
        return super(InvoiceLine, self).delete(ids)

InvoiceLine()
