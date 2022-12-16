#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import Pool, PoolMeta


__all__ = ['PurchaseRequest', 'Purchase', 'PurchaseLine', 'ProductSupplier',
    'CreatePurchase']
__metaclass__ = PoolMeta


class PurchaseRequest:
    __name__ = 'purchase.request'

    customer = fields.Many2One('party.party', 'Customer', readonly=True,
        states={
            'invisible': ~Eval('customer'),
            })
    delivery_address = fields.Many2One('party.address', 'Delivery Address',
        domain=[('party', '=', Eval('customer'))],
        states={
            'invisible': ~Eval('customer'),
            'readonly': Eval('state') != 'draft',
            },
        depends=['customer', 'state'])


class Purchase:
    __name__ = 'purchase.purchase'

    customer = fields.Many2One('party.party', 'Customer', readonly=True,
        states={
            'invisible': ~Eval('customer'),
            },
        on_change=['customer', 'delivery_address'])
    delivery_address = fields.Many2One('party.address', 'Delivery Address',
        domain=[('party', '=', Eval('customer'))],
        states={
            'readonly': Eval('state') != 'draft',
            'invisible': ~Eval('customer'),
            },
        depends=['state', 'customer'])
    drop_shipments = fields.Function(fields.One2Many('stock.shipment.drop',
            None, 'Drop Shipments',
            states={
                'invisible': ~Eval('customer'),
                },
            depends=['customer']),
        'get_drop_shipments')

    def on_change_customer(self):
        result = {
            'delivery_address': None,
            }
        delivery_address = None
        if self.customer:
            delivery_address = self.customer.address_get(type='delivery')
        if delivery_address:
            result['delivery_address'] = delivery_address.id
            result['delivery_address.rec_name'] = delivery_address.rec_name
        return result

    def get_drop_shipments(self, name):
        DropShipment = Pool().get('stock.shipment.drop')
        return list(set(m.shipment.id for l in self.lines for m in l.moves
                if isinstance(m.shipment, DropShipment)))


class PurchaseLine:
    __name__ = 'purchase.line'

    def get_to_location(self, name):
        result = super(PurchaseLine, self).get_to_location(name)
        # If delivery_address is empty, it is no more a drop shipment
        if self.purchase.customer and self.purchase.delivery_address:
            return self.purchase.customer.customer_location.id
        return result

    def get_move(self):
        move = super(PurchaseLine, self).get_move()
        if move and self.purchase.customer:
            move.cost_price = move.unit_price
        return move


class ProductSupplier:
    __name__ = 'purchase.product_supplier'

    drop_shipment = fields.Boolean('Drop Shipment',
        states={
            'invisible': ~Eval('_parent_product', {}).get('supply_on_sale',
                False),
            })


class CreatePurchase:
    __name__ = 'purchase.request.create_purchase'

    @classmethod
    def _group_purchase_key(cls, requests, request):
        result = super(CreatePurchase, cls)._group_purchase_key(requests,
            request)
        result += (
            ('customer', request.customer.id if request.customer else None),
            ('delivery_address', request.delivery_address.id
                if request.delivery_address else None),
            )
        return result
