# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.tools import grouped_slice


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @classmethod
    def copy(cls, lines, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('project_invoice_works')
        default.setdefault('project_invoice_progresses')
        return super().copy(lines, default=default)

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
