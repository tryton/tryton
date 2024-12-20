# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, ValueMixin, fields
from trytond.modules.sale.sale import (
    get_shipments_returns, search_shipments_returns)
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

sale_drop_location = fields.Many2One(
    'stock.location', "Sale Drop Location", domain=[('type', '=', 'drop')])


class Configuration(metaclass=PoolMeta):
    __name__ = 'sale.configuration'

    sale_drop_location = fields.MultiValue(sale_drop_location)

    @classmethod
    def default_sale_drop_location(cls, **pattern):
        return cls.multivalue_model(
            'sale_drop_location').default_sale_drop_location()


class ConfigurationSaleDropLocation(ModelSQL, ValueMixin):
    __name__ = 'sale.configuration.sale_drop_location'
    sale_drop_location = sale_drop_location

    @classmethod
    def default_sale_drop_location(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id(
                'sale_supply_drop_shipment', 'location_drop')
        except KeyError:
            return None


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    drop_shipments = fields.Function(fields.Many2Many(
            'stock.shipment.drop', None, None, 'Drop Shipments',
            states={
                'invisible': ~Eval('drop_shipments'),
                }),
        'get_drop_shipments', searcher='search_drop_shipments')
    drop_location = fields.Many2One('stock.location', 'Drop Location',
        domain=[('type', '=', 'drop')])

    @staticmethod
    def default_drop_location():
        pool = Pool()
        Config = pool.get('sale.configuration')

        config = Config(1)
        if config.sale_drop_location:
            return config.sale_drop_location.id

    get_drop_shipments = get_shipments_returns('stock.shipment.drop')
    search_drop_shipments = search_shipments_returns('stock.shipment.drop')

    @classmethod
    def _process_supply(cls, sales, product_quantities):
        pool = Pool()
        Move = pool.get('stock.move')
        super()._process_supply(sales, product_quantities)
        moves = []
        for sale in sales:
            moves.extend(sale.create_drop_shipment_moves())
        Move.save(moves)

    def create_drop_shipment_moves(self):
        moves = []
        for line in self.lines:
            moves += line.get_drop_moves()
        return moves


class Line(metaclass=PoolMeta):
    __name__ = 'sale.line'

    @property
    def supply_on_sale(self):
        supply_on_sale = super().supply_on_sale
        return bool(supply_on_sale
            or (self.moves and all(m.from_location.type == 'drop'
                    for m in self.moves)))

    @property
    def supply_on_sale_drop_move(self):
        "Return True if the sale line can have drop move"
        if not self.supply_on_sale:
            return False
        if self.purchase_request and not self.purchase_request.customer:
            return False
        if self.supply_state == 'cancelled':
            return False
        if self.purchase_request:
            purchase_line = self.purchase_request.purchase_line
            if purchase_line and purchase_line.moves_progress >= 1:
                return False
        return True

    def get_move(self, shipment_type):
        move = super().get_move(shipment_type)
        if self.supply_on_sale_drop_move and not self.purchase_request:
            move = None
        return move

    def get_purchase_request(self, product_quantities):
        request = super().get_purchase_request(product_quantities)
        if request and request.party:
            if self.product and self.product.type in ('goods', 'assets'):
                pattern = self._get_purchase_request_product_supplier_pattern()
                pattern['party'] = request.party.id
                product_supplier = request.find_best_product_supplier(
                    self.product, self.shipping_date, **pattern)
                if product_supplier and product_supplier.drop_shipment:
                    request.customer = (
                        self.sale.shipment_party or self.sale.party)
                    request.delivery_address = self.sale.shipment_address
        return request

    def get_drop_moves(self):
        if (self.type != 'line'
                or not self.product):
            return []
        moves = []
        if self.supply_on_sale_drop_move:
            move = self.get_move('out')
            if move is not None:
                move.from_location = self.sale.drop_location
                moves.append(move)
        return moves


class Amendment(metaclass=PoolMeta):
    __name__ = 'sale.amendment'

    @classmethod
    def _clear_sale(cls, sales):
        pool = Pool()
        Shipment = pool.get('stock.shipment.drop')
        shipments = set()
        for sale in sales:
            for shipment in sale.drop_shipments:
                if shipment.state == 'waiting':
                    shipments.add(shipment)

        super()._clear_sale(sales)

        Shipment.wait(Shipment.browse(list(shipments)))
