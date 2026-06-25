# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from collections import defaultdict

from trytond.i18n import gettext, lazy_gettext
from trytond.model import ModelSQL, ModelView, Unique, Workflow, fields
from trytond.model.exceptions import AccessError
from trytond.pool import Pool, PoolMeta

from . import graphql
from .common import IdentifierMixin, id2gid
from .exceptions import GraphQLException, ShopifyError

QUERY_FULFILLMENT_ORDERS = '''\
query FulfillmentOrders($orderId: ID!) {
    order(id: $orderId) %(fields)s
}'''

MUTATION_FULFILLMENT_ORDER_LINE_ITEMS_PREPARED_FOR_PICKUP = '''\
mutation fulfillmentOrderLineItemsPreparedForPickup(\
        $input: FulfillmentOrderLineItemsPreparedForPickupInput!) {
    fulfillmentOrderLineItemsPreparedForPickup(input: $input) {
        userErrors {
            field
            message
        }
    }
}'''


class ShipmentOut(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    shopify_identifiers = fields.One2Many(
        'stock.shipment.shopify_identifier', 'shipment',
        lazy_gettext('web_shop_shopify.msg_shopify_identifiers'))

    def get_shopify(self, sale, fulfillment_order_fields=None):
        if self.state not in {'shipped', 'done'}:
            return
        shopify_id = self.get_shopify_identifier(sale)
        if shopify_id:
            # Fulfillment can not be modified
            return
        else:
            fulfillment = {}
        for shop_warehouse in sale.web_shop.shopify_warehouses:
            if shop_warehouse.warehouse == self.warehouse:
                location_id = int(shop_warehouse.shopify_id)
                break
        else:
            location_id = None
        fulfillment_order_fields = graphql.deep_merge(
            fulfillment_order_fields or {}, {
                'fulfillmentOrders(first: 250)': {
                    'nodes': {
                        'id': None,
                        'assignedLocation': {
                            'location': {
                                'id': None,
                                },
                            },
                        'lineItems(first: 250)': {
                            'nodes': {
                                'id': None,
                                'lineItem': {
                                    'id': None,
                                    'fulfillableQuantity': None,
                                    },
                                },
                            },
                        'status': None,
                        },
                    },
                })
        order_id = id2gid('Order', sale.shopify_identifier)
        fulfillment_orders = sale.web_shop.shopify_request(
            QUERY_FULFILLMENT_ORDERS % {
                'fields': graphql.selection(fulfillment_order_fields),
                }, {'orderId': order_id}).data['order']['fulfillmentOrders']
        order_line_items = defaultdict(lambda: defaultdict(int))
        for move in self.outgoing_moves:
            if move.sale == sale:
                for order_id, line_item in move.get_shopify(
                        fulfillment_orders, location_id):
                    order_line_items[order_id][line_item['id']] += (
                        line_item['quantity'])
        if not order_line_items:
            return
        fulfillment['lineItemsByFulfillmentOrder'] = [{
                'fulfillmentOrderId': order_id,
                'fulfillmentOrderLineItems': [{
                        'id': id,
                        'quantity': quantity,
                        }
                    for id, quantity in line_items.items()],
                }
            for order_id, line_items in order_line_items.items()]
        fulfillment['notifyCustomer'] = bool(
            sale.web_shop.shopify_fulfillment_notify_customer)
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

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, shipments):
        for shipment in shipments:
            if shipment.state == 'cancelled' and shipment.shopify_identifiers:
                raise AccessError(
                    gettext(
                        'web_shop_shopify.'
                        'msg_shipment_cancelled_draft_shopify',
                        shipment=shipment.rec_name))
        super().draft(shipments)

    @classmethod
    @ModelView.button
    @Workflow.transition('packed')
    def pack(cls, shipments):
        super().pack(shipments)
        if pickup := [
                s for s in shipments
                if s.delivery_address == s.warehouse.address]:
            cls.__queue__._shopify_prepared_for_pickup(pickup)

    @classmethod
    def _shopify_prepared_for_pickup(cls, shipments):
        mutation = MUTATION_FULFILLMENT_ORDER_LINE_ITEMS_PREPARED_FOR_PICKUP
        output = 'fulfillmentOrderLineItemsPreparedForPickup'
        fullfilments = defaultdict(set)
        for shipment in shipments:
            if shipment.state == 'packed':
                for record in shipment.shopify_identifiers:
                    fullfilments[record.sale.web_shop].add(record)
        for shop, records in fullfilments.items():
            with shop.shopify_session():
                fullfilment_ids = list({
                        id2gid('FulfillmentOrder', r.shopify_identifier)
                        for r in records})
                try:
                    shop.shopify_request(
                        mutation, {
                            'input': list(fullfilment_ids),
                            },
                        user_errors=f'{output}.userErrors')
                except GraphQLException as e:
                    shipments = ", ".join(
                        r.shipment.rec_name for r in records[:5])
                    sales = ", ".join(r.sale.rec_name for r in records[:5])
                    if len(records) > 5:
                        shipments += "..."
                        sales += "..."
                    raise ShopifyError(gettext(
                            'web_shop_shopify'
                            '.msg_fulfillment_prepared_for_pickup_fail',
                            shipments=shipments,
                            sales=sales,
                            error=e.message)) from e


class ShipmentShopifyIdentifier(IdentifierMixin, ModelSQL, ModelView):
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

    def get_shopify(self, sale, fulfillment_order_fields=None):
        fulfillment = super().get_shopify(
            sale, fulfillment_order_fields=fulfillment_order_fields)
        if fulfillment and self.packages:
            numbers, urls = [], []
            fulfillment['trackingInfo'] = {
                'numbers': numbers,
                'urls': urls,
                }
            for package in self.packages:
                if package.shipping_reference:
                    numbers.append(package.shipping_reference)
                if package.shipping_tracking_url:
                    urls.append(package.shipping_tracking_url)
        return fulfillment


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    def get_shopify(self, fulfillment_orders, location_id):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        Uom = pool.get('product.uom')
        if (not isinstance(self.origin, SaleLine)
                or not self.origin.shopify_identifier):
            return
        location_id = id2gid('Location', location_id)
        identifier = id2gid('LineItem', self.origin.shopify_identifier)
        quantity = round(Uom.compute_qty(
                self.unit, self.quantity, self.origin.unit))
        for fulfillment_order in fulfillment_orders['nodes']:
            if fulfillment_order['status'] in {'CANCELLED', 'CLOSED'}:
                continue
            if (fulfillment_order['assignedLocation']['location']['id']
                    != location_id):
                continue
            for line_item in fulfillment_order['lineItems']['nodes']:
                if line_item['lineItem']['id'] == identifier:
                    qty = min(
                        quantity, line_item['lineItem']['fulfillableQuantity'])
                    if qty:
                        yield fulfillment_order['id'], {
                            'id': line_item['id'],
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


class Move_Kit(metaclass=PoolMeta):
    __name__ = 'stock.move'

    def get_shopify(self, fulfillment_orders, location_id):
        pool = Pool()
        SaleLineComponent = pool.get('sale.line.component')
        UoM = pool.get('product.uom')
        yield from super().get_shopify(fulfillment_orders, location_id)
        if not isinstance(self.origin, SaleLineComponent):
            return

        sale_line = self.origin.line

        # Track only the first component
        if min(c.id for c in sale_line.components) != self.origin.id:
            return

        location_id = id2gid('Location', location_id)
        identifier = id2gid('LineItem', sale_line.shopify_identifier)

        c_quantity = UoM.compute_qty(
                self.unit, self.quantity, self.origin.unit, round=False)
        if self.origin.quantity:
            ratio = c_quantity / self.origin.quantity
        else:
            ratio = 1
        quantity = round(sale_line.quantity * ratio)
        for fulfillment_order in fulfillment_orders['nodes']:
            if (fulfillment_order['assignedLocation']['location']['id']
                    != location_id):
                continue
            for line_item in fulfillment_order['lineItems']['nodes']:
                if line_item['lineItem']['id'] == identifier:
                    qty = min(
                        quantity, line_item['lineItem']['fulfillableQuantity'])
                    if qty:
                        yield fulfillment_order['id'], {
                            'id': line_item['id'],
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
