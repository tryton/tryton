#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelWorkflow, ModelView, ModelSQL, fields
import datetime
import copy


class Invoice(ModelWorkflow, ModelSQL, ModelView):
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

    def set_number(self, cursor, user, invoice_id, context=None):
        res = super(Invoice, self).set_number(cursor, user, invoice_id,
                context=context)
        self.write(cursor, user, invoice_id, {
            'open_date': datetime.datetime.now(),
            }, context=context)
        return res

    def copy(self, cursor, user, ids, default=None, context=None):
        if default is None:
            default = {}

        default = default.copy()
        default['open_date'] = False

        return super(Invoice, self).copy(cursor, user, ids, default=default,
                context=context)

Invoice()
