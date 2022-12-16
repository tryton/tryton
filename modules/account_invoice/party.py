#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields


class Address(ModelSQL, ModelView):
    _name = 'party.address'
    invoice = fields.Boolean('Invoice')

Address()


class Party(ModelSQL, ModelView):
    _name = 'party.party'
    payment_term = fields.Property(fields.Many2One(
        'account.invoice.payment_term', string='Invoice Payment Term'))
    supplier_payment_term = fields.Property(fields.Many2One(
        'account.invoice.payment_term', string='Supplier Payment Term'))

Party()
