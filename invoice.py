#This file is part of Tryton.  The COPYRIGHT file at the top level
#of this repository contains the full copyright notices and license terms.

from trytond.osv import fields, OSV
from trytond.netsvc import LocalService


class Invoice(OSV):
    _name = 'account.invoice'

    def write(self, cursor, user, ids, vals, context=None):
        workflow_service = LocalService('workflow')
        purchase_obj = self.pool.get('purchase.purchase')
        res = super(Invoice, self).write(cursor, user, ids, vals,
                context=context)
        if 'state' in vals and vals['state'] in ('paid', 'cancel'):
            if isinstance(ids, (int, long)):
                ids = [ids]
            purchase_ids = purchase_obj.search(cursor, user, [
                ('invoices', 'in', ids),
                ], context=context)
            for purchase in purchase_obj.browse(cursor, user, purchase_ids,
                    context=context):
                for invoice_line in purchase.invoice_lines:
                    workflow_service.trg_trigger(user, 'account.invoice.line',
                            invoice_line.id, cursor, context=context)
        return res

Invoice()


class InvoiceLine(OSV):
    _name = 'account.invoice.line'

    def __init__(self):
        super(InvoiceLine, self).__init__()
        self._error_messages.update({
            'delete_purchase_invoice_line': 'You can not delete ' \
                    'invoice lines that comes from a purchase!',
            })

    def write(self, cursor, user, ids, vals, context=None):
        purchase_obj = self.pool.get('purchase.purchase')

        if 'invoice' in vals:
            if isinstance(ids, (int, long)):
                ids = [ids]

            purchase_ids = purchase_obj.search(cursor, user, [
                ('invoice_lines', 'in', ids),
                ], context=context)
            if vals['invoice']:
                purchase_obj.write(cursor, user, purchase_ids, {
                    'invoices': [('add', vals['invoice'])],
                    }, context=context)
            else:
                purchases = purchase_obj.browse(cursor, user, purchase_ids,
                        context=context)
                for purchase in purchases:
                    invoice_ids = list(set([x.invoice.id for x \
                            in purchase.invoice_lines \
                            if x.invoice and x.id in ids]) - \
                            set([x.invoice.id for x \
                            in purchase.invoice_lines \
                            if x.invoice and x.id not in ids]))
                    purchase_obj.write(cursor, user, purchase.id, {
                        'invoices': [('unlink', invoice_ids)],
                        }, context=context)

        return super(InvoiceLine, self).write(cursor, user, ids, vals,
                context=context)

    def delete(self, cursor, user, ids, context=None):
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        cursor.execute('SELECT id FROM purchase_invoice_line_rel ' \
                'WHERE line IN (' + ','.join(['%s' for x in ids]) + ')',
                ids)
        if cursor.rowcount:
            self.raise_user_error(cursor, 'delete_purchase_invoice_line',
                    context=context)
        return super(InvoiceLine, self).delete(cursor, user, ids,
                context=context)

InvoiceLine()
