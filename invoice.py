# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.model import ModelView, Workflow, fields
from trytond.pool import PoolMeta

__all__ = ['Invoice']


class Invoice:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice'
    open_date = fields.DateTime('Open Date')

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls.party.datetime_field = 'open_date'
        if 'open_date' not in cls.party.depends:
            cls.party.depends.append('open_date')
        cls.invoice_address.datetime_field = 'open_date'
        if 'open_date' not in cls.invoice_address.depends:
            cls.invoice_address.depends.append('open_date')
        cls.payment_term.datetime_field = 'open_date'
        if 'open_date' not in cls.payment_term.depends:
            cls.payment_term.depends.append('open_date')

    def set_number(self):
        set_open_date = not self.number
        super(Invoice, self).set_number()
        if set_open_date:
            self.write([self], {
                    'open_date': datetime.datetime.now(),
                    })

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, invoices):
        super(Invoice, cls).draft(invoices)
        cls.write(invoices, {
                'open_date': None,
                })

    @classmethod
    def copy(cls, invoices, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['open_date'] = None
        return super(Invoice, cls).copy(invoices, default=default)
