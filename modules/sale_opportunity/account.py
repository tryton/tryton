# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


class PaymentTerm(metaclass=PoolMeta):
    __name__ = 'account.invoice.payment_term'
    _history = True


class PaymentTermLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.payment_term.line'
    _history = True
