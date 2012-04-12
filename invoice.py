#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime
import copy
from trytond.model import Model, fields


class Invoice(Model):
    _name = 'account.invoice'
    open_date = fields.DateTime('Open Date')

    def __init__(self):
        super(Invoice, self).__init__()
        self.party = copy.copy(self.party)
        self.party.datetime_field = 'open_date'
        if 'open_date' not in self.party.depends:
            self.party.depends = copy.copy(self.party.depends)
            self.party.depends.append('open_date')
        self.invoice_address = copy.copy(self.invoice_address)
        self.invoice_address.datetime_field = 'open_date'
        if 'open_date' not in self.invoice_address.depends:
            self.invoice_address.depends = copy.copy(
                    self.invoice_address.depends)
            self.invoice_address.depends.append('open_date')
        self.payment_term = copy.copy(self.payment_term)
        self.payment_term.datetime_field = 'open_date'
        if 'open_date' not in self.payment_term.depends:
            self.payment_term.depends = copy.copy(
                    self.payment_term.depends)
            self.payment_term.depends.append('open_date')
        self._reset_columns()

    def set_number(self, invoice):
        res = super(Invoice, self).set_number(invoice)
        self.write(invoice.id, {
            'open_date': datetime.datetime.now(),
            })
        return res

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['open_date'] = None
        return super(Invoice, self).copy(ids, default=default)

Invoice()
