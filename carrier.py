#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.pool import Pool


class Carrier(ModelSQL, ModelView):
    'Carrier'
    _name = 'carrier'
    _inherits = {'party.party': 'party'}

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

    def default_carrier_cost_method(self):
        return 'product'

    def get_rec_name(self, ids, name):
        if not ids:
            return {}
        names = {}
        for carrier in self.browse(ids):
            names[carrier.id] = '%s - %s' % (carrier.party.rec_name,
                carrier.carrier_product.rec_name)
        return names

    def copy(self, ids, default=None):
        party_obj = Pool().get('party.party')

        int_id = False
        if isinstance(ids, (int, long)):
            int_id = True
            ids = [ids]
        if default is None:
            default = {}
        default = default.copy()
        new_ids = []
        for carrier in self.browse(ids):
            default['party'] = party_obj.copy(carrier.party.id)
            new_id = super(Carrier, self).copy(carrier.id, default=default)
            new_ids.append(new_id)
        if int_id:
            return new_ids[0]
        return new_ids

    def get_sale_price(self, carrier):
        'Compute carrier sale price with currency'
        user_obj = Pool().get('res.user')
        if carrier.carrier_cost_method == 'product':
            user = user_obj.browse(Transaction().user
                or Transaction().context.get('user'))
            return carrier.carrier_product.list_price, user.company.currency.id
        return 0, None

    def get_purchase_price(self, carrier):
        'Compute carrier purchase price with currency'
        user_obj = Pool().get('res.user')
        if carrier.carrier_cost_method == 'product':
            user = user_obj.browse(Transaction().user)
            return carrier.carrier_product.cost_price, user.company.currency.id
        return 0, None

Carrier()
