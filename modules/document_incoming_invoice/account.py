# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import PoolMeta


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    documents_incoming = fields.One2Many(
        'document.incoming', 'result', "Incoming Documents", readonly=True)

    @classmethod
    def copy(cls, invoices, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('documents_incoming')
        return super().copy(invoices, default=default)
