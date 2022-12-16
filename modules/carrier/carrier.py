#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.pool import Pool

__all__ = ['Carrier']


class Carrier(ModelSQL, ModelView):
    'Carrier'
    __name__ = 'carrier'
    party = fields.Many2One('party.party', 'Party', required=True,
            ondelete='CASCADE')
    carrier_product = fields.Many2One('product.product', 'Carrier Product',
            required=True, domain=[
                ('type', '=', 'service'),
            ])
    carrier_cost_method = fields.Selection([
        ('product', 'Product Price'),
        ], 'Carrier Cost Method', required=True,
        help='Method to compute carrier cost')

    @staticmethod
    def default_carrier_cost_method():
        return 'product'

    def get_rec_name(self, name):
        return '%s - %s' % (self.party.rec_name, self.carrier_product.rec_name)

    def get_sale_price(self):
        'Compute carrier sale price with currency'
        User = Pool().get('res.user')
        if self.carrier_cost_method == 'product':
            user = User(Transaction().user
                or Transaction().context.get('user'))
            return self.carrier_product.list_price, user.company.currency.id
        return 0, None

    def get_purchase_price(self):
        'Compute carrier purchase price with currency'
        User = Pool().get('res.user')
        if self.carrier_cost_method == 'product':
            user = User(Transaction().user)
            return self.carrier_product.cost_price, user.company.currency.id
        return 0, None
