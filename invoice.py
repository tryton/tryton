# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.tools import grouped_slice

__all__ = ['InvoiceLine']


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @classmethod
    def delete(cls, lines):
        pool = Pool()
        WorkInvoicedProgress = pool.get('project.work.invoiced_progress')

        # Delete progress using root to skip access rule
        progress = []
        for sub_ids in grouped_slice([l.id for l in lines]):
            progress += WorkInvoicedProgress.search([
                    ('invoice_line', 'in', sub_ids),
                    ])
        if progress:
            with Transaction().set_user(0):
                WorkInvoicedProgress.delete(progress)

        super(InvoiceLine, cls).delete(lines)
