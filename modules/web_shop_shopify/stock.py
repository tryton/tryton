# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from collections import defaultdict

import shopify
from shopify.resources.fulfillment import FulfillmentV2

from trytond.i18n import gettext, lazy_gettext
from trytond.model import ModelSQL, ModelView, Unique, fields
from trytond.pool import Pool, PoolMeta

from .common import IdentifierMixin
from .exceptions import ShopifyError


class ShipmentOut(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    shopify_identifiers = fields.One2Many(
        'stock.shipment.shopify_identifier', 'shipment',
        lazy_gettext('web_shop_shopify.msg_shopify_identifiers'))

    def get_shopify(self, sale):
        if self.state != 'done':
            return
        shopify_id = self.get_shopify_identifier(sale)
        if shopify_id:
            # Fulfillment can not be modified
            return
        else:
            fulfillment = FulfillmentV2()
        for shop_warehouse in sale.web_shop.shopify_warehouses:
            if shop_warehouse.warehouse == self.warehouse:
                location_id = int(shop_warehouse.shopify_id)
                break
        else:
            location_id = None
        fulfillment_orders = shopify.FulfillmentOrders.find(
            order_id=sale.shopify_identifier)
        line_items = defaultdict(list)
        for move in self.outgoing_moves:
            if move.sale == sale:
                for order_id, line_item in move.get_shopify(
                        fulfillment_orders, location_id):
                    line_items[order_id].append(line_item)
        if not line_items:
            return
        fulfillment.line_items_by_fulfillment_order = [{
                'fulfillment_order_id': order_id,
                'fulfillment_order_line_items': line_items,
                }
            for order_id, line_items in line_items.items()]
        return fulfillment

    def get_shopify_identifier(self, sale):
        for record in self.shopify_identifiers:
            if record.sale == sale:
                return record.shopify_identifier

    def set_shopify_identifier(self, sale, identifier=None):
        pool = Pool()
        Identifier = pool.get('stock.shipment.shopify_identifier')
        for record in self.shopify_identifiers:
            if record.sale == sale:
                if not identifier:
                    Identifier.delete([record])
                    return
                else:
                    if record.shopify_identifier != identifier:
                        record.shopify_identifier = identifier
                        record.save()
                    return record
        if identifier:
            record = Identifier(shipment=self, sale=sale)
            record.shopify_identifier = identifier
            record.save()
            return record

    @classmethod
    def search_shopify_identifier(cls, sale, identifier):
        records = cls.search([
                ('shopify_identifiers', 'where', [
                        ('sale', '=', sale.id),
                        ('shopify_identifier', '=', identifier),
                        ]),
                ])
        if records:
            record, = records
            return record

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('shopify_identifiers')
        return super().copy(records, default=default)


class ShipmentShopifyIdentifier(IdentifierMixin, ModelSQL, ModelView):
    "Shopify Shipment Identifier"
    __name__ = 'stock.shipment.shopify_identifier'

    shipment = fields.Reference("Shipment", [
            ('stock.shipment.out', "Customer Shipment"),
            ], required=True)
    sale = fields.Many2One('sale.sale', "Sale", required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.shopify_identifier_signed.states = {
            'required': True,
            }
        t = cls.__table__()
        cls._sql_constraints += [
            ('shipment_sale_unique',
                Unique(t, t.shipment, t.sale, t.shopify_identifier_signed),
                'web_shop_shopify.msg_identifier_shipment_sale_unique'),
            ]


class ShipmentOut_PackageShipping(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    def get_shopify(self, sale):
        fulfillment = super().get_shopify(sale)
        if fulfillment and self.packages:
            tracking_info = []
            for package in self.packages:
                tracking_info.append({
                        'number': package.shipping_reference,
                        'url': package.shipping_tracking_url,
                        })
            fulfillment.tracking_info = tracking_info
        return fulfillment


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    def get_shopify(self, fulfillment_orders, location_id):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        Uom = pool.get('product.uom')
        if not isinstance(self.origin, SaleLine):
            return
        identifier = self.origin.shopify_identifier
        quantity = int(Uom.compute_qty(
                self.unit, self.quantity, self.origin.unit))
        for fulfillment_order in fulfillment_orders:
            if fulfillment_order.assigned_location_id != location_id:
                continue
            for line_item in fulfillment_order.line_items:
                if line_item.line_item_id == identifier:
                    qty = min(quantity, line_item.fulfillable_quantity)
                    yield fulfillment_order.id, {
                        'id': line_item.id,
                        'quantity': qty,
                        }
                    quantity -= qty
                    if quantity <= 0:
                        return
        else:
            raise ShopifyError(gettext(
                    'web_shop_shopify.msg_fulfillment_order_line_not_found',
                    quantity=quantity,
                    move=self.rec_name,
                    ))
