# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction


__all__ = ['PurchaseRequest', 'Purchase', 'PurchaseLine', 'ProductSupplier',
    'CreatePurchase', 'PurchaseHandleShipmentException']
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
            })
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

    @classmethod
    def __setup__(cls):
        super(Purchase, cls).__setup__()
        cls._error_messages.update({
                'delivery_address_required': ('A delivery address must be '
                    'defined for quotation of purchase "%s".'),
                })

    @fields.depends('customer', 'delivery_address')
    def on_change_customer(self):
        self.delivery_address = None
        if self.customer:
            self.delivery_address = self.customer.address_get(type='delivery')

    def get_drop_shipments(self, name):
        DropShipment = Pool().get('stock.shipment.drop')
        return list(set(m.shipment.id for l in self.lines for m in l.moves
                if isinstance(m.shipment, DropShipment)))

    def check_for_quotation(self):
        super(Purchase, self).check_for_quotation()
        if self.customer and not self.delivery_address:
            self.raise_user_error('delivery_address_required', self.rec_name)


class PurchaseLine:
    __name__ = 'purchase.line'

    def get_to_location(self, name):
        result = super(PurchaseLine, self).get_to_location(name)
        if self.purchase.customer:
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


class PurchaseHandleShipmentException:
    __name__ = 'purchase.handle.shipment.exception'

    def transition_handle(self):
        pool = Pool()
        Sale = pool.get('sale.sale')
        SaleLine = pool.get('sale.line')

        super(PurchaseHandleShipmentException, self).transition_handle()

        to_recreate = self.ask.recreate_moves
        domain_moves = self.ask.domain_moves
        sales, saleline_write = set(), []
        sale_lines = SaleLine.search([
                ('purchase_request.purchase_line.purchase', '=',
                    Transaction().context['active_id']),
                ])
        saleline_write = []
        for sale_line in sale_lines:
            moves_ignored = []
            moves_recreated = []
            skip = set(sale_line.moves_ignored)
            skip.update(sale_line.moves_recreated)
            for move in sale_line.moves:
                if move not in domain_moves or move in skip:
                    continue
                if move in to_recreate:
                    moves_recreated.append(move.id)
                else:
                    moves_ignored.append(move.id)
                sales.add(sale_line.sale)
            saleline_write.append([sale_line])
            saleline_write.append({
                    'moves_ignored': [('add', moves_ignored)],
                    'moves_recreated': [('add', moves_recreated)],
                    })

            SaleLine.write(*saleline_write)
            Sale.process(list(sales))
        return 'end'
