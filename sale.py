# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

__all__ = ['SaleConfig', 'Sale', 'SaleLine']


class SaleConfig:
    __metaclass__ = PoolMeta
    __name__ = 'sale.configuration'

    sale_drop_location = fields.Property(
        fields.Many2One('stock.location', 'Sale Drop Location',
            domain=[('type', '=', 'drop')]))


class Sale:
    __metaclass__ = PoolMeta
    __name__ = 'sale.sale'

    drop_shipments = fields.Function(fields.One2Many('stock.shipment.drop',
            None, 'Drop Shipments',
            states={
                'invisible': ~Eval('drop_shipments'),
                }),
        'get_drop_shipments')
    drop_location = fields.Many2One('stock.location', 'Drop Location',
        domain=[('type', '=', 'drop')])

    @staticmethod
    def default_drop_location():
        pool = Pool()
        Config = pool.get('sale.configuration')

        config = Config(1)
        return config.sale_drop_location.id

    def get_drop_shipments(self, name):
        DropShipment = Pool().get('stock.shipment.drop')
        return list(set(m.shipment.id for l in self.lines for m in l.moves
                if isinstance(m.shipment, DropShipment)))

    def create_shipment(self, shipment_type):
        shipments = super(Sale, self).create_shipment(shipment_type)
        if shipment_type == 'out':
            with Transaction().set_context(_drop_shipment=True):
                self.create_drop_shipment_moves()
        return shipments

    def create_drop_shipment_moves(self):
        pool = Pool()
        Move = pool.get('stock.move')

        moves = []
        for line in self.lines:
            moves += line.get_drop_moves()
        Move.save(moves)


class SaleLine:
    __metaclass__ = PoolMeta
    __name__ = 'sale.line'

    @property
    def supply_on_sale(self):
        supply_on_sale = super(SaleLine, self).supply_on_sale
        return (supply_on_sale
            or (self.moves and all(m.from_location.type == 'drop'
                    for m in self.moves)))

    def get_move(self, shipment_type):
        result = super(SaleLine, self).get_move(shipment_type)
        if (shipment_type == 'out'
                and not Transaction().context.get('_drop_shipment')
                and self.supply_on_sale):
            if (self.purchase_request and self.purchase_request.customer
                    and self.purchase_request_state != 'cancel'):
                return
        return result

    def get_purchase_request(self):
        request = super(SaleLine, self).get_purchase_request()
        if request and request.party:
            drop_shipment = False
            if self.product and self.product.type in ('goods', 'assets'):
                # FIXME this doesn't ensure to find always the right
                # product_supplier
                for product_supplier in self.product.product_suppliers:
                    if product_supplier.party == request.party:
                        drop_shipment = product_supplier.drop_shipment
                        break
            if drop_shipment:
                request.customer = self.sale.party
                request.delivery_address = self.sale.shipment_address
        return request

    def get_drop_moves(self):
        if (self.type != 'line'
                or not self.product):
            return []
        moves = []
        if self.purchase_request and self.purchase_request.customer:
            move = self.get_move('out')
            if move is not None:
                move.from_location = self.sale.drop_location
                moves.append(move)
        return moves
