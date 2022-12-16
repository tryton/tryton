#This file is part of Tryton.  The COPYRIGHT file at the top level
#of this repository contains the full copyright notices and license terms.
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

__all__ = ['InvoiceLine']
__metaclass__ = PoolMeta


class InvoiceLine:
    __name__ = 'account.invoice.line'

    @classmethod
    def __setup__(cls):
        super(InvoiceLine, cls).__setup__()
        cls._error_messages.update({
                'delete_purchase_invoice_line': ('You can not delete '
                    'invoice lines that comes from a purchase.'),
                })

    @classmethod
    def write(cls, lines, vals):
        Purchase = Pool().get('purchase.purchase')

        if 'invoice' in vals:
            with Transaction().set_user(0, set_context=True):
                purchases = Purchase.search([
                        ('invoice_lines', 'in', [l.id for l in lines]),
                        ])
                if vals['invoice']:
                    Purchase.write(purchases, {
                        'invoices': [('add', [vals['invoice']])],
                        })
                else:
                    for purchase in purchases:
                        invoice_ids = list(set([x.invoice.id for x
                                    in purchase.invoice_lines
                                    if x.invoice and x.id in lines])
                            - set([x.invoice.id for x
                                    in purchase.invoice_lines
                                    if x.invoice and x.id not in lines]))
                        Purchase.write([purchase], {
                            'invoices': [('unlink', invoice_ids)],
                            })

        return super(InvoiceLine, cls).write(lines, vals)

    @classmethod
    def delete(cls, lines):
        PurchaseLine = Pool().get('purchase.line')
        if any(l for l in lines
                if isinstance(l.origin, PurchaseLine) and l.type == 'line'):
            cls.raise_user_error('delete_purchase_invoice_line')
        super(InvoiceLine, cls).delete(lines)
