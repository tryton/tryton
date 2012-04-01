#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool


class Address(ModelSQL, ModelView):
    _name = 'party.address'
    invoice = fields.Boolean('Invoice')

Address()


class Party(ModelSQL, ModelView):
    _name = 'party.party'
    customer_payment_term = fields.Property(fields.Many2One(
        'account.invoice.payment_term', string='Customer Payment Term'))
    supplier_payment_term = fields.Property(fields.Many2One(
        'account.invoice.payment_term', string='Supplier Payment Term'))

    def init(self, module_name):
        ir_model_field_obj = Pool().get('ir.model.field')

        # Migration from 2.2: property field payment_term renamed
        # to customer_payment_term
        field_ids = ir_model_field_obj.search([
                ('name', '=', 'payment_term'),
                ('model.model', '=', 'party.party')
                ])
        if field_ids:
            ir_model_field_obj.write(field_ids, {
                    'name': 'customer_payment_term',
                    })

        super(Party, self).init(module_name)

Party()
