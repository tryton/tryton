# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool, PoolMeta

__all__ = ['Address', 'Party']


class Address:
    __metaclass__ = PoolMeta
    __name__ = 'party.address'
    invoice = fields.Boolean('Invoice')


class Party(ModelSQL, ModelView):
    __name__ = 'party.party'
    customer_payment_term = fields.Property(fields.Many2One(
        'account.invoice.payment_term', string='Customer Payment Term'))
    supplier_payment_term = fields.Property(fields.Many2One(
        'account.invoice.payment_term', string='Supplier Payment Term'))

    @classmethod
    def __register__(cls, module_name):
        ModelField = Pool().get('ir.model.field')

        # Migration from 2.2: property field payment_term renamed
        # to customer_payment_term
        fields = ModelField.search([
                ('name', '=', 'payment_term'),
                ('model.model', '=', 'party.party')
                ])
        if fields:
            ModelField.write(fields, {
                    'name': 'customer_payment_term',
                    })

        super(Party, cls).__register__(module_name)
