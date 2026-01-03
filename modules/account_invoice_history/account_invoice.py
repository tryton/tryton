# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql.functions import CurrentTimestamp

from trytond.pool import PoolMeta


class PaymentTerm(metaclass=PoolMeta):
    __name__ = 'account.invoice.payment_term'
    _history = True


class PaymentTermLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.payment_term.line'
    _history = True


class PaymentTermLineRelativeDelta(metaclass=PoolMeta):
    __name__ = 'account.invoice.payment_term.line.delta'
    _history = True


class RefreshInvoiceReport(metaclass=PoolMeta):
    __name__ = 'account.invoice.refresh_invoice_report'

    def transition_archive(self):
        if records := [r for r in self.records if r.numbered_at]:
            self.model.write(records, {
                    'numbered_at': CurrentTimestamp(),
                    })
        return super().transition_archive()
