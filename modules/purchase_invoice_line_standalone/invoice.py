# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta

__all__ = ['InvoiceLine']


class InvoiceLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice.line'

    @classmethod
    def __setup__(cls):
        super(InvoiceLine, cls).__setup__()
        cls._error_messages.update({
                'delete_purchase_invoice_line': ('You can not delete '
                    'invoice lines that comes from a purchase.'),
                })

    @classmethod
    def delete(cls, lines):
        PurchaseLine = Pool().get('purchase.line')
        if any(l for l in lines
                if isinstance(l.origin, PurchaseLine) and l.type == 'line'):
            cls.raise_user_error('delete_purchase_invoice_line')
        super(InvoiceLine, cls).delete(lines)
