# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool, PoolMeta

__all__ = ['Invoice', 'InvoiceLine']


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    def get_sales(self, name):
        pool = Pool()
        AdvancePaymentCondition = pool.get('sale.advance_payment.condition')

        sales = set(super(Invoice, self).get_sales(name))
        for line in self.lines:
            if isinstance(line.origin, AdvancePaymentCondition):
                sales.add(line.origin.sale.id)
        return list(sales)


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @classmethod
    def _get_origin(cls):
        return (super(InvoiceLine, cls)._get_origin()
            + ['sale.advance_payment.condition'])
